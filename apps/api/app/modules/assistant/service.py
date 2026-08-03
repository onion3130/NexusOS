"""Conversation persistence and assistant orchestration."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings
from app.db.models import AssistantMessage, AssistantModelRun, AssistantToolCall, Conversation
from app.modules.assistant.gateway import ModelGateway
from app.modules.assistant.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationSummary,
    GatewayMessage,
    MessageResponse,
    ModelRunResponse,
    SendMessageResponse,
    ToolCallResponse,
)
from app.modules.assistant.tools.registry import ToolRegistry


def _message_response(message: AssistantMessage) -> MessageResponse:
    """Convert a persisted message to a safe API response."""
    return MessageResponse(id=message.id, role=message.role, content=message.content, sequence=message.sequence, created_at=message.created_at)


def _summary(db: OrmSession, conversation: Conversation) -> ConversationSummary:
    """Build bounded conversation metadata."""
    count = db.scalar(select(func.count(AssistantMessage.id)).where(AssistantMessage.conversation_id == conversation.id)) or 0
    return ConversationSummary(id=conversation.id, title=conversation.title, created_at=conversation.created_at, updated_at=conversation.updated_at, message_count=count)


def create_conversation(db: OrmSession, user_id: str, payload: ConversationCreate) -> ConversationSummary:
    """Create an owned conversation."""
    conversation = Conversation(user_id=user_id, title=payload.title.strip() if payload.title else None)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return _summary(db, conversation)


def list_conversations(db: OrmSession, user_id: str) -> list[ConversationSummary]:
    """List only conversations owned by the authenticated user."""
    items = db.scalars(select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc()).limit(100)).all()
    return [_summary(db, item) for item in items]


def get_conversation(db: OrmSession, user_id: str, conversation_id: str) -> Conversation | None:
    """Return an owned conversation or no record."""
    return db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))


def conversation_response(db: OrmSession, conversation: Conversation) -> ConversationResponse:
    """Return a conversation with bounded ordered messages."""
    messages = db.scalars(select(AssistantMessage).where(AssistantMessage.conversation_id == conversation.id).order_by(AssistantMessage.sequence).limit(200)).all()
    summary = _summary(db, conversation)
    return ConversationResponse(**summary.model_dump(), messages=[_message_response(item) for item in messages])


async def send_message(
    db: OrmSession,
    settings: Settings,
    conversation: Conversation,
    content: str,
    gateway: ModelGateway,
    tools: ToolRegistry,
    permissions: set[str],
) -> SendMessageResponse:
    """Persist input, call the gateway outside a transaction, and persist results."""
    clean_content = content.strip()
    previous = db.scalars(select(AssistantMessage).where(AssistantMessage.conversation_id == conversation.id).order_by(AssistantMessage.sequence.desc()).limit(settings.ai_max_context_messages)).all()
    next_sequence = (previous[0].sequence + 1) if previous else 0
    user_message = AssistantMessage(conversation_id=conversation.id, role="user", content=clean_content, sequence=next_sequence)
    conversation.updated_at = datetime.now(UTC)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    started = time.perf_counter()
    try:
        history = list(reversed(previous)) + [user_message]
        gateway_messages = [GatewayMessage(role=item.role, content=item.content) for item in history]
        completion = await gateway.complete(gateway_messages, tools.definitions(permissions))
    except Exception as exc:
        db.rollback()
        error_code = getattr(exc, "code", "assistant_unavailable")
        status_name = "disabled" if error_code == "ai_provider_disabled" else "failed"
        model_run = AssistantModelRun(
            conversation_id=conversation.id,
            provider=settings.ai_provider,
            model=settings.ai_model,
            status=status_name,
            error_code=error_code,
            latency_ms=int((time.perf_counter() - started) * 1000),
            completed_at=datetime.now(UTC),
        )
        db.add(model_run)
        db.commit()
        raise

    model_run = AssistantModelRun(
        conversation_id=conversation.id,
        provider=completion.provider,
        model=completion.model,
        status="succeeded",
        latency_ms=int((time.perf_counter() - started) * 1000),
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
        completed_at=datetime.now(UTC),
    )
    db.add(model_run)
    db.flush()
    tool_responses: list[ToolCallResponse] = []
    tool_results: list[GatewayMessage] = []
    provider_tool_calls = [
        {
            "id": proposed.provider_id,
            "type": "function",
            "function": {"name": proposed.tool_key, "arguments": json.dumps(proposed.arguments, separators=(",", ":"))},
        }
        for proposed in completion.tool_calls[:8]
    ]
    for proposed in completion.tool_calls[:8]:
        tool_call = AssistantToolCall(
            model_run_id=model_run.id,
            tool_key=proposed.tool_key[:96],
            status="proposed",
            input_json=json.dumps(proposed.arguments, separators=(",", ":"))[:16000],
        )
        try:
            result = tools.execute(proposed, permissions)
            serialized_result = json.dumps(result, separators=(",", ":"))[:16000]
            tool_call.status = "executed"
            tool_call.output_json = serialized_result
            tool_results.append(GatewayMessage(role="tool", content=serialized_result, tool_call_id=proposed.provider_id))
        except Exception:
            tool_call.status = "failed"
            tool_call.error_code = "ai_tool_not_allowed"
        db.add(tool_call)
        db.flush()
        tool_responses.append(ToolCallResponse(id=tool_call.id, tool_key=tool_call.tool_key, status=tool_call.status, error_code=tool_call.error_code))

    db.commit()
    if tool_results:
        follow_up_messages = gateway_messages + [GatewayMessage(role="assistant", content=completion.content, tool_calls=provider_tool_calls)] + tool_results
        try:
            follow_up = await gateway.complete(follow_up_messages, [])
            if follow_up.content:
                completion.content = follow_up.content
        except Exception:
            # Tool execution already succeeded; preserve a safe initial response.
            pass

    if not completion.content and any(item.status == "executed" for item in tool_responses):
        completion.content = "System telemetry retrieved successfully."
    if not completion.content:
        completion.content = "The assistant returned an empty response."
    assistant_message = AssistantMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=completion.content[:16000],
        sequence=next_sequence + 1,
        model_run_id=model_run.id,
    )
    db.add(assistant_message)
    conversation.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(assistant_message)
    return SendMessageResponse(
        user_message=_message_response(user_message),
        assistant_message=_message_response(assistant_message),
        model_run=ModelRunResponse(id=model_run.id, provider=model_run.provider, model=model_run.model, status=model_run.status, latency_ms=model_run.latency_ms),
        tool_calls=tool_responses,
    )
