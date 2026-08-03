"""Milestone 5 assistant gateway tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.db.session import get_session_factory
from app.modules.assistant.gateway import DisabledGateway, OpenAICompatibleGateway, _validate_provider_target
from app.modules.assistant.schemas import GatewayCompletion
from app.modules.assistant.schemas import GatewayMessage, ProposedToolCall, ProviderDisabledError, ToolValidationError
from app.modules.assistant.tools.registry import ToolRegistry
from app.modules.identity.service import bootstrap_owner
from app.modules.system.service import SystemService


def _bootstrap_owner(username: str = "owner") -> None:
    """Create one fixture owner through the production bootstrap service."""
    db = get_session_factory()()
    try:
        bootstrap_owner(db, username, "correct horse battery staple")
    finally:
        db.close()


def _login(client, username: str = "owner") -> None:
    """Authenticate the fixture owner."""
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "correct horse battery staple"})
    assert response.status_code == 200


def test_conversations_require_authentication(client) -> None:
    """Conversation collection is never public."""
    assert client.get("/api/v1/conversations").status_code == 401
    assert client.post("/api/v1/conversations", json={}).status_code == 401


def test_conversation_ownership_and_disabled_provider_persistence(client) -> None:
    """Owners can read only their data and disabled AI records a safe run."""
    _bootstrap_owner()
    _login(client)
    created = client.post("/api/v1/conversations", json={"title": "System check"})
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    detail = client.get(f"/api/v1/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert detail.json()["messages"] == []

    response = client.post(f"/api/v1/conversations/{conversation_id}/messages", json={"content": "Check the system"})
    assert response.status_code == 503
    assert response.json()["detail"] == "ai_provider_disabled"
    detail = client.get(f"/api/v1/conversations/{conversation_id}").json()
    assert detail["messages"][0]["role"] == "user"

    client.cookies.clear()
    assert client.get(f"/api/v1/conversations/{conversation_id}").status_code == 401


def test_message_validation_and_missing_conversation(client) -> None:
    """Message size and ownership boundaries use safe API responses."""
    _bootstrap_owner()
    _login(client)
    assert client.get("/api/v1/conversations/not-a-conversation").status_code == 404
    created = client.post("/api/v1/conversations", json={}).json()
    response = client.post(f"/api/v1/conversations/{created['id']}/messages", json={"content": " "})
    assert response.status_code == 422
    response = client.post(f"/api/v1/conversations/{created['id']}/messages", json={"content": "x" * 4001})
    assert response.status_code == 422


def test_disabled_gateway_never_contacts_provider() -> None:
    """The disabled provider fails locally without constructing an HTTP client."""
    async def run() -> None:
        with pytest.raises(ProviderDisabledError):
            await DisabledGateway().complete([GatewayMessage(role="user", content="hello")], [])

    asyncio.run(run())


def test_tool_registry_rejects_unknown_or_argumented_calls(tmp_path: Path) -> None:
    """The only initial tool is fixed and accepts no model-controlled arguments."""
    registry = ToolRegistry(SystemService(tmp_path, tmp_path / "proc", tmp_path / "sys"))
    assert [item.key for item in registry.definitions({"system.read_overview"})] == ["system.get_overview"]
    assert registry.definitions(set()) == []
    with pytest.raises(ToolValidationError):
        registry.execute(ProposedToolCall(provider_id="p", tool_key="os.execute", arguments={}), {"system.read_overview"})
    with pytest.raises(ToolValidationError):
        registry.execute(ProposedToolCall(provider_id="p", tool_key="system.get_overview", arguments={"path": "/etc"}), {"system.read_overview"})
    with pytest.raises(ToolValidationError):
        registry.execute(ProposedToolCall(provider_id="p", tool_key="system.get_overview", arguments={}), set())
    registry.execute(ProposedToolCall(provider_id="p", tool_key="system.get_overview", arguments={}), {"system.read_overview"})


def test_provider_target_rejects_local_addresses() -> None:
    """Provider calls cannot target loopback or metadata addresses."""
    async def run() -> None:
        with pytest.raises(Exception):
            await _validate_provider_target("http://127.0.0.1/v1/chat/completions")
        with pytest.raises(Exception):
            await _validate_provider_target("http://localhost/v1/chat/completions")

    asyncio.run(run())


def test_openai_compatible_normalization_does_not_keep_raw_payload() -> None:
    """Provider normalization returns bounded typed fields and no raw body."""
    settings = Settings(
        NEXUS_ENV="test",
        TZ="UTC",
        DATA_DIR=".",
        DB_TYPE="sqlite",
        DATABASE_URL="sqlite:///./data/nexus.db",
        JWT_SECRET="test-secret-that-is-longer-than-thirty-two-characters",
        SESSION_COOKIE_SECURE=False,
        CORS_ORIGINS="http://localhost:3000",
        AI_PROVIDER="openai_compatible",
        AI_BASE_URL="https://provider.example/v1/chat/completions",
        AI_API_KEY=SecretStr("server-only-key"),
        AI_MODEL="test-model",
    )
    result = OpenAICompatibleGateway(settings)._normalize({"choices": [{"message": {"content": "hello"}}], "secret": "must not be returned"})
    assert result.content == "hello"
    assert not hasattr(result, "secret")
