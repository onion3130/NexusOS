"""Conversation persistence and assistant orchestration."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session as OrmSession, selectinload

from app.core.config import Settings
from app.db.models import AssistantMessage, AssistantModelRun, AssistantSourceReference, AssistantToolCall, Conversation, Job, Note, NoteChunk
from app.modules.identity.service import add_audit_event
from app.modules.assistant.gateway import ModelGateway
from app.modules.assistant.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationSummary,
    GatewayMessage,
    MessageResponse,
    ProposedToolCall,
    ModelRunResponse,
    SendMessageResponse,
    ToolCallResponse,
    SourceReference,
    GroundingOptions,
)
from app.modules.assistant.context import GroundingContext, build_grounding_context
from app.modules.assistant.tools.registry import ToolRegistry


def _approval_key(user_id: str, operation: str, key: str) -> str:
    """Return a bounded user-scoped idempotency key."""
    return hashlib.sha256(f"{user_id}:{operation}:{key}".encode("utf-8")).hexdigest()


def _source_responses(db: OrmSession, message: AssistantMessage, user_id: str) -> list[SourceReference]:
    """Return only provenance whose canonical note and chunk belong together and to the user."""
    rows = db.execute(
        select(AssistantSourceReference)
        .join(Note, Note.id == AssistantSourceReference.source_id)
        .join(NoteChunk, NoteChunk.id == AssistantSourceReference.chunk_id)
        .where(
            AssistantSourceReference.message_id == message.id,
            AssistantSourceReference.user_id == user_id,
            Note.user_id == user_id,
            NoteChunk.user_id == user_id,
            NoteChunk.note_id == Note.id,
            NoteChunk.id == AssistantSourceReference.chunk_id,
        )
        .order_by(AssistantSourceReference.rank)
    ).scalars().all()
    return [SourceReference.model_validate({
        "source_type": item.source_type,
        "source_id": item.source_id,
        "chunk_id": item.chunk_id,
        "title": item.title,
        "source_version": item.source_version,
        "retrieval_mode": item.retrieval_mode,
        "rank": item.rank,
        "content_hash": item.content_hash,
        "lexical_score": item.lexical_score,
        "semantic_score": item.semantic_score,
    }) for item in rows]


def _message_response(db: OrmSession, user_id: str, message: AssistantMessage) -> MessageResponse:
    """Convert a persisted message and ownership-validated sources to a safe response."""
    return MessageResponse(id=message.id, role=message.role, content=message.content, sequence=message.sequence, created_at=message.created_at, sources=_source_responses(db, message, user_id))


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
    messages = db.scalars(select(AssistantMessage).where(AssistantMessage.conversation_id == conversation.id).order_by(AssistantMessage.sequence).limit(200)).unique().all()
    for message in messages:
        _ = message.source_references
    summary = _summary(db, conversation)
    return ConversationResponse(**summary.model_dump(), messages=[_message_response(db, conversation.user_id, item) for item in messages])


async def send_message(
    db: OrmSession,
    settings: Settings,
    conversation: Conversation,
    content: str,
    gateway: ModelGateway,
    tools: ToolRegistry,
    permissions: set[str],
    grounding_options: GroundingOptions,
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
        grounding = await build_grounding_context(db, settings, conversation.user_id, clean_content, permissions, grounding_options) if settings.ai_provider != "disabled" else GroundingContext(message=None, sources=[])
        if grounding.message is not None:
            gateway_messages.insert(0, grounding.message)
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
            if tools.requires_confirmation(proposed.tool_key):
                tool_call.status = "proposed"
                tool_call.expires_at = datetime.now(UTC) + timedelta(minutes=10)
            else:
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
        tool_responses.append(ToolCallResponse(id=tool_call.id, tool_key=tool_call.tool_key, status=tool_call.status, error_code=tool_call.error_code, requires_confirmation=tools.requires_confirmation(proposed.tool_key), arguments=proposed.arguments))

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
    db.flush()
    for source in grounding.sources if 'grounding' in locals() else []:
        db.add(AssistantSourceReference(
            message_id=assistant_message.id,
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            source_type=source.source_type,
            source_id=source.source_id,
            chunk_id=source.chunk_id,
            title=source.title,
            source_version=source.source_version,
            retrieval_mode=source.retrieval_mode,
            rank=source.rank,
            content_hash=source.content_hash,
            lexical_score=source.lexical_score,
            semantic_score=source.semantic_score,
        ))
    conversation.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(assistant_message)
    return SendMessageResponse(
        user_message=_message_response(db, conversation.user_id, user_message),
        assistant_message=_message_response(db, conversation.user_id, assistant_message),
        model_run=ModelRunResponse(id=model_run.id, provider=model_run.provider, model=model_run.model, status=model_run.status, latency_ms=model_run.latency_ms),
        tool_calls=tool_responses,
    )


def message_sources(db: OrmSession, user_id: str, conversation_id: str, message_id: str):
    """Return owned source provenance for one assistant message."""
    from app.modules.assistant.schemas import AssistantSourcesResponse
    message = db.scalar(select(AssistantMessage).where(AssistantMessage.id == message_id, AssistantMessage.conversation_id == conversation_id, AssistantMessage.role == "assistant"))
    if message is None:
        return None
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    if conversation is None:
        return None
    return AssistantSourcesResponse(message_id=message.id, sources=_source_responses(db, message, user_id))


def approve_tool_call(db: OrmSession, user_id: str, tool_call_id: str, permissions: set[str], tools: ToolRegistry, idempotency_key: str | None = None) -> tuple[AssistantToolCall | None, dict[str, object] | None]:
    """Execute one unexpired owned task proposal exactly once."""
    approval_payload = {"tool_call_id": tool_call_id, "operation": "approve"}
    if idempotency_key:
        prior = db.scalar(select(Job).where(Job.idempotency_key == _approval_key(user_id, "assistant-approve", idempotency_key)))
        if prior:
            stored = json.loads(prior.payload_json or "{}")
            if stored.get("fingerprint") != hashlib.sha256(json.dumps(approval_payload, sort_keys=True).encode()).hexdigest():
                raise ValueError("Idempotency-Key was already used for a different operation")
            replay = db.get(AssistantToolCall, stored.get("resource_id"))
            if replay is not None:
                return replay, json.loads(replay.output_json) if replay.output_json else None
    statement = select(AssistantToolCall).join(AssistantModelRun).join(Conversation).where(AssistantToolCall.id == tool_call_id, Conversation.user_id == user_id).options(selectinload(AssistantToolCall.model_run).selectinload(AssistantModelRun.conversation))
    tool_call = db.scalar(statement)
    if tool_call is None:
        return None, None
    if tool_call.status == "executed":
        return tool_call, json.loads(tool_call.output_json) if tool_call.output_json else None
    if tool_call.status == "rejected":
        return tool_call, None
    now = datetime.now(UTC)
    if tool_call.status == "processing" and tool_call.processing_until is not None and tool_call.processing_until > now:
        return tool_call, None
    if tool_call.status not in {"proposed", "processing"} or tool_call.expires_at is None or tool_call.expires_at <= now:
        return tool_call, None
    claim = db.execute(update(AssistantToolCall).where(AssistantToolCall.id == tool_call.id, AssistantToolCall.status.in_(["proposed", "processing"]), AssistantToolCall.expires_at > now, (AssistantToolCall.processing_until.is_(None) | (AssistantToolCall.processing_until <= now))).values(status="processing", processing_until=now + timedelta(minutes=2)))
    db.commit()
    if claim.rowcount != 1:
        return db.get(AssistantToolCall, tool_call.id), None
    tool_call = db.get(AssistantToolCall, tool_call.id)
    if tool_call is None:
        return None, None
    proposed = ProposedToolCall(provider_id=tool_call.id, tool_key=tool_call.tool_key, arguments=json.loads(tool_call.input_json))
    try:
        result = tools.execute(proposed, permissions)
    except Exception:
        tool_call.status = "failed"
        tool_call.error_code = "ai_tool_not_allowed"
        tool_call.processing_until = None
        db.commit()
        raise
    tool_call.status = "executed"
    tool_call.output_json = json.dumps(result, separators=(",", ":"))[:16000]
    tool_call.approved_at = datetime.now(UTC)
    tool_call.completed_at = datetime.now(UTC)
    tool_call.processing_until = None
    if idempotency_key:            db.add(Job(job_type="mutation", status="completed", available_at=datetime.now(UTC), idempotency_key=_approval_key(user_id, "assistant-approve", idempotency_key), payload_json=json.dumps({"resource_id": tool_call.id, "fingerprint": hashlib.sha256(json.dumps(approval_payload, sort_keys=True).encode()).hexdigest()}, separators=(",", ":")), completed_at=datetime.now(UTC)))
    add_audit_event(db, action="assistant.task_action_approve", result="success", actor_user_id=user_id, target=tool_call.id, metadata={"tool": tool_call.tool_key})
    db.commit()
    return tool_call, result


def reject_tool_call(db: OrmSession, user_id: str, tool_call_id: str, idempotency_key: str | None = None) -> AssistantToolCall | None:
    """Reject one owned pending assistant task proposal without executing it."""
    reject_payload = {"tool_call_id": tool_call_id, "operation": "reject"}
    if idempotency_key:
        prior = db.scalar(select(Job).where(Job.idempotency_key == _approval_key(user_id, "assistant-reject", idempotency_key)))
        if prior and prior.payload_json:
            stored = json.loads(prior.payload_json)
            if stored.get("fingerprint") != hashlib.sha256(json.dumps(reject_payload, sort_keys=True).encode()).hexdigest():
                raise ValueError("Idempotency-Key was already used for a different operation")
            replay = db.get(AssistantToolCall, stored.get("resource_id"))
            if replay is not None:
                return replay
    statement = select(AssistantToolCall).join(AssistantModelRun).join(Conversation).where(AssistantToolCall.id == tool_call_id, Conversation.user_id == user_id)
    tool_call = db.scalar(statement)
    if tool_call is None:
        return None
    if tool_call.status == "proposed":
        tool_call.status = "rejected"
        tool_call.rejected_at = datetime.now(UTC)
        if idempotency_key:
            reject_payload = {"tool_call_id": tool_call_id, "operation": "reject"}
            db.add(Job(job_type="mutation", status="completed", available_at=datetime.now(UTC), idempotency_key=_approval_key(user_id, "assistant-reject", idempotency_key), payload_json=json.dumps({"resource_id": tool_call.id, "fingerprint": hashlib.sha256(json.dumps(reject_payload, sort_keys=True).encode()).hexdigest()}, separators=(",", ":")), completed_at=datetime.now(UTC)))
        add_audit_event(db, action="assistant.task_action_reject", result="success", actor_user_id=user_id, target=tool_call.id)
        db.commit()
    return tool_call
