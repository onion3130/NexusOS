"""Bounded, text-only Assistant streaming orchestration."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings
from app.db.models import AssistantMessage, AssistantModelRun, AssistantSourceReference, Conversation, Job
from app.modules.assistant.commands import handle_slash_command
from app.modules.assistant.context import GroundingContext, build_grounding_context
from app.modules.assistant.gateway import ModelGateway
from app.modules.assistant.prompts import NEXUS_SYSTEM_PROMPT
from app.modules.assistant.schemas import AssistantError, AssistantIdempotencyError, AssistantInProgressError, GatewayMessage, GroundingOptions, ProviderTimeoutError
from app.modules.assistant.service import _history_for_gateway, _message_response, _utc_datetime


async def stream_message(
    db: OrmSession,
    settings: Settings,
    conversation: Conversation,
    content: str,
    gateway: ModelGateway,
    permissions: set[str],
    grounding_options: GroundingOptions,
    idempotency_key: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield safe stream events and persist the completed assistant message.

    Streaming deliberately does not attach tools. Requests that may need a
    mutation or live local tool continue through the buffered confirmation path;
    this boundary is for fast plain-text responses and read-only grounding.
    """
    clean_content = content.strip()
    stream_job_key = _stream_job_key(conversation.user_id, idempotency_key) if idempotency_key else None
    fingerprint = _fingerprint({"conversation_id": conversation.id, "content": clean_content, "grounding": grounding_options.model_dump(mode="json")})
    existing_user_message: AssistantMessage | None = None
    reservation_lease = datetime.now(UTC) + timedelta(seconds=max(30, settings.ai_timeout_seconds + 30))
    if stream_job_key:
        prior = db.scalar(select(Job).where(Job.idempotency_key == stream_job_key))
        if prior is not None:
            stored = json.loads(prior.payload_json or "{}")
            if stored.get("fingerprint") != fingerprint:
                raise AssistantIdempotencyError()
            if stored.get("status") == "completed":
                async for event in _replay_completed(db, conversation, stored):
                    yield event
                return
            if stored.get("status") == "failed":
                existing_user_message = _find_recoverable_user_message(db, conversation, clean_content, prior)
                claimed = db.execute(
                    update(Job)
                    .where(Job.id == prior.id, Job.status == "failed")
                    .values(status="processing", locked_until=reservation_lease, completed_at=None)
                    .execution_options(synchronize_session=False)
                )
                db.commit()
                if claimed.rowcount != 1:
                    raise AssistantInProgressError()
                prior = db.get(Job, prior.id)
                if prior is None:
                    raise AssistantInProgressError()
                prior.payload_json = json.dumps({"fingerprint": fingerprint, "status": "processing", **({"user_message_id": existing_user_message.id} if existing_user_message else {})}, separators=(",", ":"))
                db.commit()
            elif stored.get("status") == "processing" and prior.locked_until is not None and _utc_datetime(prior.locked_until) <= datetime.now(UTC):
                existing_user_message = _find_recoverable_user_message(db, conversation, clean_content, prior)
                claimed = db.execute(
                    update(Job)
                    .where(Job.id == prior.id, Job.status == "processing", Job.locked_until <= datetime.now(UTC))
                    .values(locked_until=reservation_lease)
                    .execution_options(synchronize_session=False)
                )
                db.commit()
                if claimed.rowcount != 1:
                    raise AssistantInProgressError()
                prior = db.get(Job, prior.id)
                if prior is None:
                    raise AssistantInProgressError()
                stored_payload = json.loads(prior.payload_json or "{}")
                stored_payload.update({"fingerprint": fingerprint, "status": "processing", **({"user_message_id": existing_user_message.id} if existing_user_message else {})})
                prior.payload_json = json.dumps(stored_payload, separators=(",", ":"))
                db.commit()
            else:
                raise AssistantInProgressError()
        else:
            reservation = Job(
                job_type="assistant_stream",
                status="processing",
                available_at=datetime.now(UTC),
                locked_until=reservation_lease,
                idempotency_key=stream_job_key,
                payload_json=json.dumps({"fingerprint": fingerprint, "status": "processing"}, separators=(",", ":")),
            )
            db.add(reservation)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                prior = db.scalar(select(Job).where(Job.idempotency_key == stream_job_key))
                if prior is None:
                    raise AssistantInProgressError()
                stored = json.loads(prior.payload_json or "{}")
                if stored.get("fingerprint") != fingerprint:
                    raise AssistantIdempotencyError()
                if stored.get("status") == "completed":
                    async for event in _replay_completed(db, conversation, stored):
                        yield event
                    return
                if stored.get("status") == "failed":
                    existing_user_message = _find_recoverable_user_message(db, conversation, clean_content, prior)
                    claimed = db.execute(
                        update(Job)
                        .where(Job.id == prior.id, Job.status == "failed")
                        .values(status="processing", locked_until=reservation_lease, completed_at=None)
                        .execution_options(synchronize_session=False)
                    )
                    db.commit()
                    if claimed.rowcount != 1:
                        raise AssistantInProgressError()
                    prior = db.get(Job, prior.id)
                    if prior is None:
                        raise AssistantInProgressError()
                    prior.payload_json = json.dumps({"fingerprint": fingerprint, "status": "processing", **({"user_message_id": existing_user_message.id} if existing_user_message else {})}, separators=(",", ":"))
                    db.commit()
                else:
                    raise AssistantInProgressError()

    previous = db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conversation.id)
        .order_by(AssistantMessage.sequence.desc())
        .limit(settings.ai_max_context_messages)
    ).all()
    if existing_user_message is not None:
        previous = [item for item in previous if item.id != existing_user_message.id]
        user_message = existing_user_message
        next_sequence = user_message.sequence
    else:
        next_sequence = (previous[0].sequence + 1) if previous else 0
        user_message = AssistantMessage(
            conversation_id=conversation.id,
            role="user",
            content=clean_content,
            sequence=next_sequence,
        )
        db.add(user_message)
    conversation.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(user_message)
    if stream_job_key:
        reservation = db.scalar(select(Job).where(Job.idempotency_key == stream_job_key))
        if reservation is not None:
            reservation.locked_until = reservation_lease
            stored_payload = json.loads(reservation.payload_json or "{}")
            stored_payload.update({"fingerprint": fingerprint, "status": "processing", "user_message_id": user_message.id})
            reservation.payload_json = json.dumps(stored_payload, separators=(",", ":"))
            db.commit()

    yield {
        "type": "meta",
        "user_message": _message_response(db, conversation.user_id, user_message).model_dump(mode="json"),
    }

    slash = handle_slash_command(clean_content, settings, permissions)
    if slash is not None and slash.handled:
        model_run = AssistantModelRun(
            conversation_id=conversation.id,
            provider="local",
            model="slash-command",
            status="succeeded",
            latency_ms=0,
            completed_at=datetime.now(UTC),
        )
        db.add(model_run)
        db.flush()
        assistant_message = AssistantMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=slash.content[:16000],
            sequence=next_sequence + 1,
            model_run_id=model_run.id,
        )
        db.add(assistant_message)
        conversation.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(assistant_message)
        yield {"type": "delta", "content": assistant_message.content}
        if stream_job_key:
            reservation = db.scalar(select(Job).where(Job.idempotency_key == stream_job_key))
            if reservation is not None:
                reservation.status = "completed"
                reservation.locked_until = None
                reservation.completed_at = datetime.now(UTC)
                reservation.payload_json = json.dumps({"fingerprint": fingerprint, "status": "completed", "user_message_id": user_message.id, "assistant_message_id": assistant_message.id, "model_run_id": model_run.id}, separators=(",", ":"))
        db.commit()
        db.refresh(assistant_message)
        yield {
            "type": "done",
            "user_message": _message_response(db, conversation.user_id, user_message).model_dump(mode="json"),
            "assistant_message": _message_response(db, conversation.user_id, assistant_message).model_dump(mode="json"),
            "model_run": {
                "id": model_run.id,
                "provider": model_run.provider,
                "model": model_run.model,
                "status": model_run.status,
                "latency_ms": model_run.latency_ms,
                "error_code": None,
            },
            "tool_calls": [],
        }
        return

    started = time.perf_counter()
    grounding = GroundingContext(message=None, sources=[])
    chunks: list[str] = []
    try:
        history = list(reversed(previous)) + [user_message]
        gateway_messages = [
            GatewayMessage(role="system", content=NEXUS_SYSTEM_PROMPT),
            GatewayMessage(
                role="system",
                content=(
                    "Streaming mode is text-only. Do not propose or describe tool calls. "
                    "Answer directly from the conversation and clearly say when you cannot verify local data."
                ),
            ),
            *_history_for_gateway(history),
        ]
        if settings.ai_provider != "disabled":
            grounding = await build_grounding_context(
                db,
                settings,
                conversation.user_id,
                clean_content,
                permissions,
                grounding_options,
            )
        if grounding.message is not None:
            gateway_messages.insert(2, grounding.message)

        async with asyncio.timeout(settings.ai_timeout_seconds):
            async for delta in gateway.stream(gateway_messages):
                if not delta:
                    continue
                chunks.append(delta)
                yield {"type": "delta", "content": delta}
    except asyncio.CancelledError:
        db.rollback()
        _mark_stream_failed(db, stream_job_key, fingerprint, user_message.id)
        raise
    except asyncio.TimeoutError as exc:
        db.rollback()
        _mark_stream_failed(db, stream_job_key, fingerprint, user_message.id)
        model_run = AssistantModelRun(
            conversation_id=conversation.id,
            provider=settings.ai_provider,
            model=settings.ai_model,
            status="failed",
            error_code=ProviderTimeoutError.code,
            latency_ms=int((time.perf_counter() - started) * 1000),
            completed_at=datetime.now(UTC),
        )
        db.add(model_run)
        db.commit()
        raise ProviderTimeoutError() from exc
    except Exception as exc:
        db.rollback()
        _mark_stream_failed(db, stream_job_key, fingerprint, user_message.id)
        model_run = AssistantModelRun(
            conversation_id=conversation.id,
            provider=settings.ai_provider,
            model=settings.ai_model,
            status="disabled" if getattr(exc, "code", "") == "ai_provider_disabled" else "failed",
            error_code=getattr(exc, "code", "assistant_unavailable"),
            latency_ms=int((time.perf_counter() - started) * 1000),
            completed_at=datetime.now(UTC),
        )
        db.add(model_run)
        db.commit()
        raise

    response_content = "".join(chunks).strip()
    if not response_content:
        response_content = "I couldn't generate a reply that time. Try a shorter question."
    model_run = AssistantModelRun(
        conversation_id=conversation.id,
        provider=settings.ai_provider,
        model=settings.ai_model,
        status="succeeded",
        latency_ms=int((time.perf_counter() - started) * 1000),
        completed_at=datetime.now(UTC),
    )
    db.add(model_run)
    db.flush()
    assistant_message = AssistantMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=response_content[:16000],
        sequence=next_sequence + 1,
        model_run_id=model_run.id,
    )
    db.add(assistant_message)
    db.flush()
    for source in grounding.sources:
        db.add(
            AssistantSourceReference(
                message_id=assistant_message.id,
                conversation_id=conversation.id,
                user_id=conversation.user_id,
                source_type=source.source_type,
                source_id=source.source_id if source.source_type == "note" else None,
                chunk_id=source.chunk_id if source.source_type == "note" else None,
                external_source_id=source.source_id if source.source_type == "external_source" else None,
                external_chunk_id=source.chunk_id if source.source_type == "external_source" else None,
                title=source.title,
                source_version=source.source_version,
                retrieval_mode=source.retrieval_mode,
                rank=source.rank,
                content_hash=source.content_hash,
                lexical_score=source.lexical_score,
                semantic_score=source.semantic_score,
            )
        )
    conversation.updated_at = datetime.now(UTC)
    if stream_job_key:
        reservation = db.scalar(select(Job).where(Job.idempotency_key == stream_job_key))
        if reservation is not None:
            reservation.status = "completed"
            reservation.completed_at = datetime.now(UTC)
            reservation.payload_json = json.dumps({"fingerprint": fingerprint, "status": "completed", "user_message_id": user_message.id, "assistant_message_id": assistant_message.id, "model_run_id": model_run.id}, separators=(",", ":"))
    db.commit()
    db.refresh(assistant_message)
    yield {
        "type": "done",
        "user_message": _message_response(db, conversation.user_id, user_message).model_dump(mode="json"),
        "assistant_message": _message_response(db, conversation.user_id, assistant_message).model_dump(mode="json"),
        "model_run": {
            "id": model_run.id,
            "provider": model_run.provider,
            "model": model_run.model,
            "status": model_run.status,
            "latency_ms": model_run.latency_ms,
            "error_code": None,
        },
        "tool_calls": [],
    }


def _fingerprint(value: object) -> str:
    """Create a stable digest for one idempotent stream request."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _stream_job_key(user_id: str, idempotency_key: str) -> str:
    """Scope the browser key to the user and streaming operation."""
    return hashlib.sha256(f"{user_id}:assistant-stream:{idempotency_key}".encode("utf-8")).hexdigest()


def _find_recoverable_user_message(db: OrmSession, conversation: Conversation, content: str, reservation: Job) -> AssistantMessage | None:
    """Recover input committed before a process crashed updating its reservation."""
    created_at = _utc_datetime(reservation.created_at)
    candidates = db.scalars(
        select(AssistantMessage)
        .where(
            AssistantMessage.conversation_id == conversation.id,
            AssistantMessage.role == "user",
            AssistantMessage.content == content,
        )
        .order_by(AssistantMessage.created_at.desc())
        .limit(20)
    ).all()
    for candidate in candidates:
        candidate_created_at = _utc_datetime(candidate.created_at)
        if created_at is None or candidate_created_at is None or candidate_created_at >= created_at:
            return candidate
    return None


def _mark_stream_failed(db: OrmSession, job_key: str | None, fingerprint: str, user_message_id: str | None = None) -> None:
    """Release a failed reservation while retaining the persisted input for retry."""
    if not job_key:
        return
    reservation = db.scalar(select(Job).where(Job.idempotency_key == job_key))
    if reservation is not None:
        reservation.status = "failed"
        reservation.locked_until = None
        stored_payload = json.loads(reservation.payload_json or "{}")
        stored_payload.update({"fingerprint": fingerprint, "status": "failed"})
        if user_message_id:
            stored_payload["user_message_id"] = user_message_id
        reservation.payload_json = json.dumps(stored_payload, separators=(",", ":"))
        db.commit()


async def _replay_completed(db: OrmSession, conversation: Conversation, stored: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """Replay a completed idempotent response without creating another message."""
    user_message = db.get(AssistantMessage, stored.get("user_message_id"))
    assistant_message = db.get(AssistantMessage, stored.get("assistant_message_id"))
    model_run = db.get(AssistantModelRun, stored.get("model_run_id"))
    if user_message is None or assistant_message is None or model_run is None:
        raise AssistantError()
    yield {"type": "meta", "user_message": _message_response(db, conversation.user_id, user_message).model_dump(mode="json")}
    yield {"type": "delta", "content": assistant_message.content}
    yield {
        "type": "done",
        "user_message": _message_response(db, conversation.user_id, user_message).model_dump(mode="json"),
        "assistant_message": _message_response(db, conversation.user_id, assistant_message).model_dump(mode="json"),
        "model_run": {
            "id": model_run.id,
            "provider": model_run.provider,
            "model": model_run.model,
            "status": model_run.status,
            "latency_ms": model_run.latency_ms,
            "error_code": None,
        },
        "tool_calls": [],
    }
