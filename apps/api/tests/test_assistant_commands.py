"""Assistant slash-command tests."""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.db.models import Conversation, User
from app.db.session import get_session_factory
from app.modules.assistant.commands import handle_slash_command, parse_slash_command
from app.modules.assistant.schemas import GroundingOptions
from app.modules.assistant.service import send_message
from app.modules.identity.service import bootstrap_owner


def _bootstrap_owner() -> None:
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def test_parse_slash_command() -> None:
    assert parse_slash_command("hello") is None
    assert parse_slash_command("/model") == ("/model", [])
    assert parse_slash_command("/model list") == ("/model", ["list"])
    assert parse_slash_command("/model set meta/llama-3.1-8b-instruct") == ("/model", ["set", "meta/llama-3.1-8b-instruct"])


def test_model_status_command(client) -> None:
    settings = get_settings()
    result = handle_slash_command("/model", settings, set())
    assert result is not None
    assert "Provider" in result.content or "disabled" in result.content.lower() or "Model" in result.content


def test_model_list_command(client) -> None:
    result = handle_slash_command("/model list", get_settings(), set())
    assert result is not None
    assert "llama" in result.content.lower() or "preset" in result.content.lower()
    assert "/model set" in result.content


def test_model_set_requires_owner(client) -> None:
    result = handle_slash_command("/model set meta/llama-3.1-8b-instruct", get_settings(), set())
    assert result is not None
    assert "owner" in result.content.lower()


def test_send_message_handles_model_slash(client, monkeypatch) -> None:
    """Slash commands short-circuit the provider gateway."""
    import app.modules.assistant.service as service_module

    _bootstrap_owner()
    db = get_session_factory()()
    try:
        user = db.query(User).first()
        conversation = Conversation(user_id=user.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        class BoomGateway:
            async def complete(self, messages, tools):
                raise AssertionError("provider must not be called for /model")

        class NoTools:
            def definitions(self, _permissions):
                return []

            def requires_confirmation(self, _key):
                return False

        async def no_grounding(*_a, **_k):
            from app.modules.assistant.context import GroundingContext

            return GroundingContext(message=None, sources=[])

        monkeypatch.setattr(service_module, "build_grounding_context", no_grounding)

        async def run() -> None:
            result = await send_message(
                db,
                get_settings(),
                conversation,
                "/model help",
                BoomGateway(),
                NoTools(),
                {"notes.read"},
                GroundingOptions(enabled=False),
            )
            assert "/model" in result.assistant_message.content
            assert result.model_run.provider == "local"

        asyncio.run(run())
    finally:
        db.close()
