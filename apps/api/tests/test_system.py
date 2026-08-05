"""Milestone 4 read-only system telemetry tests."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_session_factory
from app.modules.system.admin import _provider_status
from app.core.runtime_config import runtime_path
from app.modules.identity.service import bootstrap_owner
from app.modules.system.adapters.network import read_interfaces
from app.modules.system.adapters.procfs import read_memory, read_uptime
from app.modules.system.adapters.thermal import read_temperature
from app.modules.system.service import SystemService


def _bootstrap_owner() -> None:
    """Create the fixture owner through the existing identity service."""
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _write_proc_fixture(root: Path) -> None:
    """Create deterministic procfs files for adapter tests."""
    (root / "net").mkdir(parents=True)
    (root / "stat").write_text("cpu  100 0 100 800 0 0 0 0 0 0\n", encoding="utf-8")
    (root / "loadavg").write_text("0.42 0.20 0.10 1/100 123\n", encoding="utf-8")
    (root / "meminfo").write_text("MemTotal:       1024 kB\nMemAvailable:    512 kB\n", encoding="utf-8")
    (root / "uptime").write_text("123.4 50.0\n", encoding="utf-8")
    (root / "net" / "dev").write_text("Inter-| Receive | Transmit\n eth0: 100 0 0 0 0 0 0 0 200 0 0 0 0 0 0 0\n", encoding="utf-8")


def test_procfs_adapters_read_bounded_values(tmp_path) -> None:
    """Procfs adapters parse only the expected numeric fields."""
    proc_root = tmp_path / "proc"
    _write_proc_fixture(proc_root)
    assert read_memory(proc_root) == (1024 * 1024, 512 * 1024, 50.0)
    assert read_uptime(proc_root) == 123.4
    interfaces = read_interfaces(proc_root)
    assert interfaces and interfaces[0]["name"] == "eth0"
    assert interfaces[0]["receive_bytes"] == 100
    assert interfaces[0]["transmit_bytes"] == 200


def test_thermal_adapter_skips_invalid_zones(tmp_path) -> None:
    """Thermal discovery ignores malformed zones and returns valid readings."""
    zone = tmp_path / "sys" / "class" / "thermal" / "thermal_zone0"
    zone.mkdir(parents=True)
    (zone / "temp").write_text("47000\n", encoding="utf-8")
    (zone / "type").write_text("cpu-thermal\n", encoding="utf-8")
    assert read_temperature(tmp_path / "sys") == (47.0, "cpu-thermal")


def test_system_service_degrades_without_exposing_paths(tmp_path) -> None:
    """Missing Linux sources produce safe codes and no filesystem path disclosure."""
    result = SystemService(tmp_path / "missing", tmp_path / "proc", tmp_path / "sys").collect()
    assert result.status == "degraded"
    assert result.storage.source.reason == "storage_unavailable"
    assert result.temperature.source.reason == "temperature_unavailable"
    assert result.health.level in {"warning", "critical", "unavailable", "healthy"}
    assert result.temperature.health.level == "unavailable"
    assert str(tmp_path) not in result.model_dump_json()


def test_temperature_health_marks_warm_and_hot() -> None:
    """Pi thermal thresholds auto-detect warm and dangerous ranges."""
    from app.modules.system.health import temperature_health

    assert temperature_health(50.0)[0] == "healthy"
    assert temperature_health(70.5)[0] == "warning"
    assert temperature_health(70.5)[1] == "Warm"
    assert temperature_health(82.0)[0] == "critical"
    assert temperature_health(82.0)[1] == "Hot"


def test_admin_status_is_owner_only_and_redacted(client, monkeypatch) -> None:
    """The owner panel exposes safe status without provider secrets."""
    assert client.get("/api/v1/system/admin/status").status_code == 401
    _bootstrap_owner()
    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    response = client.get("/api/v1/system/admin/status")
    assert response.status_code == 200
    body = response.json()
    assert body["system"]["state"] in {"ready", "degraded"}
    assert body["storage"]["value"] == "SQLite ready"
    assert body["ai_provider"]["state"] == "disabled"
    assert "reachability" not in body["ai_provider"]["detail"]
    assert body["embedding_provider"]["state"] == "disabled"
    assert "test-secret" not in response.text
    assert "database_url" not in response.text
    assert body["migration_head"]


def test_configured_provider_status_is_redacted() -> None:
    """Configured-provider status never includes the server credential or endpoint."""
    settings = Settings(
        NEXUS_ENV="test",
        TZ="UTC",
        DATA_DIR=".",
        DB_TYPE="sqlite",
        DATABASE_URL="sqlite:///./data/nexus.db",
        JWT_SECRET="test-secret-that-is-longer-than-thirty-two-characters",
        SESSION_COOKIE_SECURE=False,
        CORS_ORIGINS="http://localhost:3000",
        AI_PROVIDER="nvidia_nim",
        NVIDIA_API_KEY=SecretStr("server-only-nvidia-key"),
        AI_MODEL="meta/llama-3.1-8b-instruct",
    )
    card = _provider_status(settings)
    assert card.state == "ready"
    assert card.value == "Configured · NVIDIA NIM"
    assert "server-only-nvidia-key" not in card.model_dump_json()
    assert "integrate.api.nvidia.com" not in card.model_dump_json()
    assert "reachability is checked when a message is sent" in card.detail


def test_browser_nvidia_nim_setup_is_encrypted_redacted_and_disableable(client) -> None:
    """Owner setup stores NIM outside the database and never returns the key."""
    _bootstrap_owner()
    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    api_key = "nvapi-" + "s" * 40
    csrf = client.cookies.get("nexus_csrf")
    response = client.post("/api/v1/system/admin/nvidia-nim", headers={"X-CSRF-Token": csrf}, json={"api_key": api_key, "model": "meta/llama-3.1-8b-instruct", "embeddings_enabled": False})
    assert response.status_code == 200, response.text
    assert response.json()["nvidia_nim"] == {"configured": True, "source": "browser", "model": "meta/llama-3.1-8b-instruct", "embeddings_enabled": False, "restart_required": False}
    assert api_key not in response.text
    settings = get_settings()
    get_settings.cache_clear()
    refreshed = client.get("/api/v1/system/admin/status")
    assert refreshed.status_code == 200
    assert refreshed.json()["nvidia_nim"]["restart_required"] is False
    encrypted = runtime_path(settings.data_dir)
    assert encrypted.is_file()
    assert api_key.encode() not in encrypted.read_bytes()
    # Owners can change models without re-entering the saved key.
    updated = client.post("/api/v1/system/admin/nvidia-nim", headers={"X-CSRF-Token": csrf}, json={"model": "meta/llama-3.1-70b-instruct", "embeddings_enabled": True, "embedding_model": "nvidia/nv-embedqa-e5-v5"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["nvidia_nim"]["model"] == "meta/llama-3.1-70b-instruct"
    assert updated.json()["nvidia_nim"]["embeddings_enabled"] is True
    assert api_key not in updated.text
    disabled = client.delete("/api/v1/system/admin/nvidia-nim", headers={"X-CSRF-Token": csrf})
    assert disabled.status_code == 200
    assert disabled.json()["nvidia_nim"]["source"] == "none"
    assert not encrypted.exists()


def test_nvidia_nim_options_and_test_require_admin(client, monkeypatch) -> None:
    """Model presets are owner-readable; connection tests stay CSRF-protected."""
    assert client.get("/api/v1/system/admin/nvidia-nim/options").status_code == 401
    _bootstrap_owner()
    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    options = client.get("/api/v1/system/admin/nvidia-nim/options")
    assert options.status_code == 200
    body = options.json()
    assert body["chat_models"]
    assert body["embedding_models"]
    assert body["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert body["openai_compatible"] is True
    assert "nvapi" not in options.text.lower()
    csrf = client.cookies.get("nexus_csrf")
    missing_csrf = client.post("/api/v1/system/admin/nvidia-nim/test", json={"api_key": "nvapi-" + "s" * 40, "model": "meta/llama-3.1-8b-instruct"})
    assert missing_csrf.status_code == 403

    async def _fake_test(settings, *, api_key=None, model=None):
        from app.modules.system.nim_setup import NimTestResult
        return NimTestResult(ok=True, detail="Connection successful.", model=model or "meta/llama-3.1-8b-instruct")

    monkeypatch.setattr("app.api.routes.system.test_nim_connection", _fake_test)
    tested = client.post("/api/v1/system/admin/nvidia-nim/test", headers={"X-CSRF-Token": csrf}, json={"api_key": "nvapi-" + "s" * 40, "model": "meta/llama-3.1-8b-instruct"})
    assert tested.status_code == 200
    assert tested.json()["ok"] is True
    assert "nvapi" not in tested.text


def test_nvidia_nim_models_lists_live_catalog_without_echoing_key(client, monkeypatch) -> None:
    """Owner can load real NVIDIA models through the OpenAI-compatible /v1/models path."""
    from app.modules.system.schemas import NimChatPreset, NimEmbeddingPreset, NimModelCatalogResponse

    _bootstrap_owner()
    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    csrf = client.cookies.get("nexus_csrf")

    async def _fake_list(settings, *, api_key=None):
        # Catalog may be public; key is optional.
        return NimModelCatalogResponse(
            ok=True,
            base_url="https://integrate.api.nvidia.com/v1",
            models_url="https://integrate.api.nvidia.com/v1/models",
            chat_endpoint="https://integrate.api.nvidia.com/v1/chat/completions",
            embedding_endpoint="https://integrate.api.nvidia.com/v1/embeddings",
            openai_compatible=True,
            source="live",
            chat_models=[NimChatPreset(id="meta/llama-3.1-8b-instruct", label="Llama", description="chat", recommended=True)],
            embedding_models=[NimEmbeddingPreset(id="nvidia/nv-embed-v1", label="Embed", description="embed", recommended=True)],
            detail="Loaded models",
        )

    monkeypatch.setattr("app.api.routes.system.list_nvidia_models", _fake_list)
    missing = client.post("/api/v1/system/admin/nvidia-nim/models", json={"api_key": "nvapi-" + "x" * 40})
    assert missing.status_code == 403
    listed = client.post(
        "/api/v1/system/admin/nvidia-nim/models",
        headers={"X-CSRF-Token": csrf},
        json={"api_key": "nvapi-" + "x" * 40},
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["source"] == "live"
    assert body["openai_compatible"] is True
    assert body["chat_models"][0]["id"] == "meta/llama-3.1-8b-instruct"
    assert "nvapi" not in listed.text


def test_browser_nvidia_nim_setup_requires_csrf_and_admin(client) -> None:
    """Provider setup cannot be called without the cookie CSRF boundary."""
    _bootstrap_owner()
    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    response = client.post("/api/v1/system/admin/nvidia-nim", json={"api_key": "nvapi-" + "s" * 40, "model": "meta/llama-3.1-8b-instruct"}, headers={"X-CSRF-Token": "wrong"})
    assert response.status_code == 403


def test_admin_status_denies_a_user_without_admin_permission(client) -> None:
    """Admin status is not granted by ordinary authenticated access."""
    _bootstrap_owner()
    db = get_session_factory()()
    try:
        user = db.query(User).first()
        user.roles = []
        db.commit()
    finally:
        db.close()
    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    assert client.get("/api/v1/system/admin/status").status_code == 403


def test_assistant_provider_status_is_authenticated_and_redacted(client) -> None:
    """The Assistant receives provider state without credentials or endpoints."""
    assert client.get("/api/v1/system/assistant/provider").status_code == 401
    _bootstrap_owner()
    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    response = client.get("/api/v1/system/assistant/provider")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "disabled"
    assert body["state"] == "disabled"
    assert "NVIDIA_API_KEY" not in response.text
    assert "integrate.api.nvidia.com" not in response.text


def test_assistant_provider_status_reports_configured_nim_without_secrets(client, monkeypatch) -> None:
    """Configured NIM status exposes only the provider label and model."""
    _bootstrap_owner()
    monkeypatch.setenv("AI_PROVIDER", "nvidia_nim")
    monkeypatch.setenv("AI_MODEL", "meta/llama-3.1-8b-instruct")
    monkeypatch.setenv("NVIDIA_API_KEY", "server-only-nvidia-key")
    get_settings.cache_clear()
    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    response = client.get("/api/v1/system/assistant/provider")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "provider": "nvidia_nim",
        "label": "NVIDIA NIM",
        "state": "configured",
        "model": "meta/llama-3.1-8b-instruct",
        "detail": "Server-side configuration is valid; provider reachability is checked when a message is sent",
    }
    assert "server-only-nvidia-key" not in response.text
    assert "integrate.api.nvidia.com" not in response.text


def test_system_overview_requires_authentication(client) -> None:
    """The system overview is not public and does not add write routes."""
    assert client.get("/api/v1/system/overview").status_code == 401
    _bootstrap_owner()
    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    response = client.get("/api/v1/system/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["storage"]["path_label"] == "configured data volume"
    assert "health" in body
    assert body["health"]["level"] in {"healthy", "warning", "critical", "unavailable"}
    assert body["temperature"]["health"]["level"] in {"healthy", "warning", "critical", "unavailable"}
    assert "units" in body["service_status"]
    assert "shutdown" not in body
