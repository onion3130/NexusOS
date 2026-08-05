"""Assistant confirmation regression tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.db.models import AssistantModelRun, AssistantToolCall, Conversation, User
from app.db.session import get_session_factory
from app.modules.assistant.context import GroundingContext
from app.modules.assistant.gateway import GatewayCompletion
from app.modules.assistant.schemas import GroundingOptions, ProposedToolCall
from app.modules.assistant.service import send_message
from app.modules.assistant.tools.registry import ToolRegistry
from app.modules.identity.service import bootstrap_owner
from app.modules.system.service import SystemService
from app.modules.workspace_views.service import WorkspaceViewService


def _bootstrap_owner() -> None:
    """Create the fixture owner through the production bootstrap service."""
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _login(client) -> None:
    """Authenticate the fixture owner."""
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200


def test_unsupported_assistant_tool_approval_returns_422_not_500(client) -> None:
    """A stale or hallucinated tool proposal fails safely during approval."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    db = get_session_factory()()
    try:
        user = db.query(User).filter(User.username == "owner").one()
        conversation = Conversation(user_id=user.id)
        db.add(conversation)
        db.flush()
        model_run = AssistantModelRun(
            conversation_id=conversation.id,
            provider="nvidia_nim",
            model="test-model",
            status="succeeded",
        )
        db.add(model_run)
        db.flush()
        tool_call = AssistantToolCall(
            model_run_id=model_run.id,
            tool_key="notes.create",
            status="proposed",
            input_json='{"title":"New Note","content":"example"}',
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        db.add(tool_call)
        db.commit()
        tool_call_id = tool_call.id
    finally:
        db.close()

    response = client.post(
        f"/api/v1/ai/tool-calls/{tool_call_id}/approve",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "unsupported-note-create"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "ai_tool_not_allowed"

    db = get_session_factory()()
    try:
        stored = db.get(AssistantToolCall, tool_call_id)
        assert stored is not None
        assert stored.status == "failed"
        assert stored.error_code == "ai_tool_not_allowed"
    finally:
        db.close()


def test_unsupported_assistant_tool_does_not_create_confirmation_card(client, monkeypatch) -> None:
    """Unsupported model calls are failed before the browser receives approval metadata."""
    import app.modules.assistant.service as service_module

    _bootstrap_owner()
    db = get_session_factory()()
    try:
        user = db.query(User).filter(User.username == "owner").one()
        conversation = Conversation(user_id=user.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        settings = get_settings().model_copy(update={"ai_provider": "openai_compatible"})

        async def no_grounding(*_args, **_kwargs):
            return GroundingContext(message=None, sources=[])

        monkeypatch.setattr(service_module, "build_grounding_context", no_grounding)

        class HallucinatingGateway:
            async def complete(self, _messages, _tools):
                return GatewayCompletion(
                    content="I can create that note.",
                    tool_calls=[ProposedToolCall(provider_id="provider-call", tool_key="notes.create", arguments={"title": "New Note", "content": "example"})],
                    provider="openai_compatible",
                    model="test-model",
                )

        async def run():
            return await send_message(
                db,
                settings,
                conversation,
                "Create a new note",
                HallucinatingGateway(),
                ToolRegistry(SystemService(settings.data_dir), db, user.id, WorkspaceViewService(settings), settings),
                {"notes.read", "notes.write", "assistant.task_actions"},
                GroundingOptions(enabled=False),
            )

        result = asyncio.run(run())
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_key == "notes.create"
        assert result.tool_calls[0].status == "failed"
        assert result.tool_calls[0].error_code == "ai_tool_not_allowed"
        assert result.tool_calls[0].requires_confirmation is False
    finally:
        db.close()
