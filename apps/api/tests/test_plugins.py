"""Milestone 11 Phase D plugin boundary tests."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models import AuditEvent, Plugin, PluginRun, User
from app.db.session import get_session_factory
from app.modules.identity.service import bootstrap_owner, get_user
from app.modules.plugins.broker import BrokerError, PluginBroker, PluginTimeoutError
from app.modules.plugins.schemas import PluginManifest
from app.modules.plugins.service import PluginError, invoke_plugin, list_plugins, rescan_plugins, set_plugin_status, uninstall_plugin


def _bootstrap_owner() -> None:
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _login(client) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200


def _owner_id(db) -> str:
    return db.scalar(select(User.id).limit(1))


def _owner(db):
    return get_user(db, _owner_id(db))


def _write_plugin(root: Path, name: str, *, version: str = "1.0.0", capability: str = "greet", risk: str = "read") -> Path:
    """Create an operator-approved plugin directory with a manifest and runnable entrypoint."""
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    capabilities = [{"method": capability, "description": "Echo a greeting", "risk": risk}]
    manifest = {"name": name, "version": version, "description": "Test plugin", "entrypoint": "run.py", "capabilities": capabilities}
    (directory / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "run.py").write_text(
        textwrap.dedent(
            """\
            import json, sys
            line = sys.stdin.readline()
            request = json.loads(line)
            method = request.get("method")
            args = request.get("arguments") or {}
            if method == "greet":
                print(json.dumps({"result": {"greeting": "hello " + str(args.get("name", "world"))}}))
            elif method == "fail":
                print(json.dumps({"error": "plugin_refused"}))
            else:
                print(json.dumps({"error": "unknown_method"}))
            """
        ),
        encoding="utf-8",
    )
    return directory


def _write_slow_plugin(root: Path, name: str) -> Path:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"name": name, "version": "1.0.0", "description": "Slow plugin", "entrypoint": "run.py", "capabilities": [{"method": "hang", "description": "Never answers", "risk": "read"}]}
    (directory / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "run.py").write_text(
        textwrap.dedent(
            """\
            import json, sys, time
            sys.stdin.readline()
            time.sleep(60)
            print(json.dumps({"result": {}}))
            """
        ),
        encoding="utf-8",
    )
    return directory


@pytest.fixture
def plugins_root(tmp_path: Path) -> Path:
    root = tmp_path / "plugins"
    root.mkdir(exist_ok=True)
    _write_plugin(root, "hello")
    return root


def test_manifest_validates_names_methods_and_entrypoints(configured_app) -> None:
    """Manifest validation rejects traversal, reserved names, and unsafe methods."""
    valid = PluginManifest.model_validate({"name": "my_plugin", "version": "1.2.3", "entrypoint": "run.py", "capabilities": [{"method": "greet", "risk": "read"}]})
    assert valid.name == "my_plugin"
    with pytest.raises(Exception):
        PluginManifest.model_validate({"name": "../evil", "version": "1.0.0", "entrypoint": "run.py", "capabilities": [{"method": "x", "risk": "read"}]})
    with pytest.raises(Exception):
        PluginManifest.model_validate({"name": "ok", "version": "1.0.0", "entrypoint": "../../etc/passwd", "capabilities": [{"method": "x", "risk": "read"}]})
    with pytest.raises(Exception):
        PluginManifest.model_validate({"name": "ok", "version": "1.0.0", "entrypoint": "run.py", "capabilities": [{"method": "rm -rf /", "risk": "read"}]})
    with pytest.raises(Exception):
        PluginManifest.model_validate({"name": "ok", "version": "1.0.0", "entrypoint": "run.py", "capabilities": []})


def test_broker_invokes_out_of_process(configured_app, plugins_root) -> None:
    """The broker runs the entrypoint as a subprocess and parses a bounded response."""
    directory = _write_plugin(plugins_root, "echo")
    broker = PluginBroker(plugins_root, timeout_seconds=10)
    result = broker.invoke(directory, "run.py", "greet", {"name": "nexus"})
    assert result == {"greeting": "hello nexus"}


def test_broker_rejects_traversal_and_timeout(configured_app, plugins_root) -> None:
    """Entrypoints may not escape the plugin directory; hung plugins are killed."""
    directory = _write_plugin(plugins_root, "hello")
    broker = PluginBroker(plugins_root, timeout_seconds=10)
    with pytest.raises(BrokerError):
        broker.invoke(directory, "../../../run.py", "greet", {})
    slow = _write_slow_plugin(plugins_root, "slow")
    with pytest.raises(PluginTimeoutError):
        PluginBroker(plugins_root, timeout_seconds=1).invoke(slow, "run.py", "hang", {})


def test_broker_surfaces_plugin_error_codes(configured_app, plugins_root) -> None:
    """Plugin-declared errors are surfaced as bounded codes, not raw output."""
    directory = _write_plugin(plugins_root, "hello", capability="fail")
    broker = PluginBroker(plugins_root, timeout_seconds=10)
    with pytest.raises(BrokerError) as exc:
        broker.invoke(directory, "run.py", "fail", {})
    assert str(exc.value) == "plugin_refused"


def test_broker_does_not_inherit_application_secrets(configured_app, plugins_root, monkeypatch) -> None:
    """Plugin processes receive no JWT, AI, SMTP, or backup key environment values."""
    directory = plugins_root / "envcheck"
    directory.mkdir()
    (directory / "plugin.json").write_text(json.dumps({"name": "envcheck", "version": "1.0.0", "entrypoint": "run.py", "capabilities": [{"method": "inspect", "risk": "read"}]}), encoding="utf-8")
    (directory / "run.py").write_text("import json, os; print(json.dumps({'result': {'jwt': 'JWT_SECRET' in os.environ, 'ai': 'AI_API_KEY' in os.environ, 'smtp': 'NOTIFICATION_EMAIL_SMTP_PASSWORD' in os.environ, 'backup': 'BACKUP_ENCRYPTION_KEY' in os.environ}}))", encoding="utf-8")
    monkeypatch.setenv("JWT_SECRET", "secret-value")
    monkeypatch.setenv("AI_API_KEY", "ai-value")
    monkeypatch.setenv("NOTIFICATION_EMAIL_SMTP_PASSWORD", "smtp-value")
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", "backup-value")
    result = PluginBroker(plugins_root, timeout_seconds=10).invoke(directory, "run.py", "inspect", {})
    assert result == {"jwt": False, "ai": False, "smtp": False, "backup": False}


def test_rescan_registers_updates_and_removes(configured_app, plugins_root) -> None:
    """Rescan adds new plugins, updates changed manifests, and unregisters missing ones."""
    db = get_session_factory()()
    _bootstrap_owner()
    owner = _owner(db)
    summary = rescan_plugins(db, owner.id, plugins_dir=plugins_root)
    db.close()
    assert summary["added"] == ["hello"]
    db = get_session_factory()()
    assert [row.name for row in list_plugins(db)] == ["hello"]
    db.close()

    db = get_session_factory()()
    _write_plugin(plugins_root, "hello", version="2.0.0")
    _write_plugin(plugins_root, "second")
    owner = _owner(db)
    summary = rescan_plugins(db, owner.id, plugins_dir=plugins_root)
    assert summary["updated"] == ["hello"] and summary["added"] == ["second"]
    db.close()

    db = get_session_factory()()
    (plugins_root / "second").rename(plugins_root / "second-gone")
    owner = _owner(db)
    summary = rescan_plugins(db, owner.id, plugins_dir=plugins_root)
    assert summary["removed"] == ["second"]
    # Re-adding the same directory revives the soft-deleted row instead of
    # colliding with the unique plugin name constraint.
    _write_plugin(plugins_root, "second", version="1.0.0")
    summary = rescan_plugins(db, owner.id, plugins_dir=plugins_root)
    assert summary["added"] == ["second"]
    assert len(list_plugins(db)) == 2
    db.close()


def test_lifecycle_status_and_uninstall_are_audited(configured_app, plugins_root) -> None:
    """Enable/disable/uninstall mutate status and write audit events."""
    _bootstrap_owner()
    db = get_session_factory()()
    owner = _owner(db)
    rescan_plugins(db, owner.id, plugins_dir=plugins_root)
    row = set_plugin_status(db, owner.id, "hello", "disabled")
    assert row.status == "disabled"
    row = set_plugin_status(db, owner.id, "hello", "enabled")
    assert row.status == "enabled"
    uninstall_plugin(db, owner.id, "hello")
    assert list_plugins(db) == []
    events = db.scalars(select(AuditEvent).where(AuditEvent.action.in_(["plugins.set_status", "plugins.uninstall"]))).all()
    db.close()
    assert len(events) == 3


def test_invoke_records_runs_and_enforces_capabilities(configured_app, plugins_root) -> None:
    """Invocation records run history and rejects unknown or disabled capabilities."""
    _bootstrap_owner()
    db = get_session_factory()()
    owner = _owner(db)
    rescan_plugins(db, owner.id, plugins_dir=plugins_root)
    result = invoke_plugin(db, owner.id, "hello", "greet", {"name": "pi"})
    assert result == {"greeting": "hello pi"}
    runs = db.scalars(select(PluginRun)).all()
    assert len(runs) == 1 and runs[0].status == "success"
    with pytest.raises(PluginError):
        invoke_plugin(db, owner.id, "hello", "unknown", {})
    with pytest.raises(PluginError):
        invoke_plugin(db, owner.id, "missing", "greet", {})
    set_plugin_status(db, owner.id, "hello", "disabled")
    with pytest.raises(PluginError):
        invoke_plugin(db, owner.id, "hello", "greet", {})
    db.close()


def test_run_history_is_pruned(configured_app, plugins_root, monkeypatch) -> None:
    """Run history keeps only the bounded newest entries per plugin."""
    _bootstrap_owner()
    import app.modules.plugins.service as plugin_service

    monkeypatch.setattr(plugin_service, "RUN_HISTORY_LIMIT", 1)
    db = get_session_factory()()
    owner = _owner(db)
    rescan_plugins(db, owner.id, plugins_dir=plugins_root)
    invoke_plugin(db, owner.id, "hello", "greet", {"name": "one"})
    invoke_plugin(db, owner.id, "hello", "greet", {"name": "two"})
    from sqlalchemy import func
    assert db.scalar(select(func.count(PluginRun.id))) == 1
    db.close()


def test_plugin_routes_require_auth_and_confirmation(client, configured_app, plugins_root) -> None:
    """Listing requires plugins.read; direct invocation never bypasses confirmation."""
    assert client.get("/api/v1/plugins").status_code == 401
    _bootstrap_owner()
    _login(client)
    assert client.get("/api/v1/plugins").status_code == 200
    db = get_session_factory()()
    owner = _owner(db)
    rescan_plugins(db, owner.id, plugins_dir=plugins_root)
    db.close()
    csrf = client.cookies.get("nexus_csrf")
    response = client.post("/api/v1/plugins/hello/invoke", json={"method": "greet", "arguments": {"name": "web"}}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 422
    assert response.json()["detail"] == "requires_assistant_confirmation"
    _write_plugin(plugins_root, "danger", capability="erase", risk="dangerous")
    db = get_session_factory()()
    owner = _owner(db)
    rescan_plugins(db, owner.id, plugins_dir=plugins_root)
    db.close()
    blocked = client.post("/api/v1/plugins/danger/invoke", json={"method": "erase", "arguments": {}}, headers={"X-CSRF-Token": csrf})
    assert blocked.status_code == 422
    assert blocked.json()["detail"] == "requires_assistant_confirmation"


def test_plugin_lifecycle_via_host_action_proposals(client, configured_app, plugins_root) -> None:
    """Plugin lifecycle runs only through confirmed, audited host-action proposals."""
    _bootstrap_owner()
    _login(client)
    db = get_session_factory()()
    owner = _owner(db)
    rescan_plugins(db, owner.id, plugins_dir=plugins_root)
    db.close()
    csrf = client.cookies.get("nexus_csrf")
    headers = {"X-CSRF-Token": csrf}
    proposal = client.post("/api/v1/system/actions/proposals", json={"action_key": "plugins.disable", "input": {"name": "hello"}}, headers=headers)
    assert proposal.status_code == 201
    proposal_id = proposal.json()["id"]
    confirmed = client.post(f"/api/v1/system/actions/proposals/{proposal_id}/confirm", headers=headers)
    assert confirmed.status_code == 200
    from app.core.config import get_settings
    from app.modules.host_actions.worker import process_host_actions

    db = get_session_factory()()
    assert process_host_actions(db, data_dir=get_settings().data_dir, database_url=get_settings().database_url) == 1
    row = db.scalar(select(Plugin).where(Plugin.name == "hello"))
    assert row.status == "disabled"
    db.close()
