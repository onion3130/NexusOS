"""Plugin lifecycle and bounded invocation service.

Plugins are discovered only beneath the operator-approved PLUGINS_DIR, each in
its own directory whose name matches the manifest ``name``. Lifecycle changes
are confirmation-gated host actions and every mutation is audited. Invocation
runs the entrypoint out-of-process through the broker, never in the API
process, and every call records a bounded PluginRun.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Literal

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.config import get_settings
from app.db.base import utc_now
from app.db.models import Plugin, PluginRun
from app.modules.identity.service import add_audit_event
from app.modules.plugins.broker import BrokerError, PluginBroker, PluginTimeoutError
from app.modules.plugins.schemas import PluginManifest

MANIFEST_FILENAME = "plugin.json"
MAX_MANIFEST_BYTES = 64 * 1024
RUN_HISTORY_LIMIT = 200


class PluginError(Exception):
    """A bounded, user-safe plugin service error."""


def configured_plugins_dir() -> Path | None:
    """Return the operator-approved plugins directory, if configured."""
    return get_settings().plugins_dir


def _active_plugin(db: OrmSession, name: str) -> Plugin | None:
    """Load one non-deleted plugin by name."""
    return db.scalar(select(Plugin).where(Plugin.name == name, Plugin.deleted_at.is_(None)))


def _plugin_dir(root: Path, name: str) -> Path:
    """Resolve and confine a plugin directory strictly beneath the approved root."""
    resolved = (root.resolve() / name).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise PluginError("plugin_dir_escape")
    return resolved


def discover_manifests(plugins_dir: Path) -> dict[str, tuple[Path, PluginManifest]]:
    """Discover valid manifests in approved plugin subdirectories (bounded)."""
    discovered: dict[str, tuple[Path, PluginManifest]] = {}
    root = plugins_dir.resolve()
    children = sorted(child for child in plugins_dir.iterdir() if child.is_dir() and not child.is_symlink())
    for child in children[:100]:
        resolved_child = child.resolve()
        if root not in resolved_child.parents:
            continue
        manifest_path = resolved_child / MANIFEST_FILENAME
        if not manifest_path.is_file():
            continue
        try:
            raw = manifest_path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError):
            continue
        if len(raw.encode("utf-8")) > MAX_MANIFEST_BYTES:
            continue
        try:
            manifest = PluginManifest.model_validate_json(raw)
        except ValidationError:
            continue
        # The directory name must equal the manifest name so entrypoints stay
        # confined and the registry row can resolve its plugin directory.
        if manifest.name != resolved_child.name:
            continue
        discovered[manifest.name] = (resolved_child, manifest)
    return discovered


def rescan_plugins(
    db: OrmSession,
    user_id: str,
    *,
    plugins_dir: Path | None = None,
) -> dict[str, object]:
    """Register new, update changed, and unregister missing auto-discovered plugins."""
    root = plugins_dir or configured_plugins_dir()
    if root is None:
        raise PluginError("plugins_not_configured")
    root = root.resolve()
    if not root.is_dir():
        raise PluginError("plugins_dir_missing")
    discovered = discover_manifests(root)
    existing = {
        row.name: row
        for row in db.scalars(select(Plugin).where(Plugin.name.in_(discovered.keys())))
    }
    active = {
        row.name: row
        for row in db.scalars(select(Plugin).where(Plugin.deleted_at.is_(None)))
    }
    added: list[str] = []
    updated: list[str] = []
    removed: list[str] = []
    for name, (_directory, manifest) in sorted(discovered.items()):
        canonical = manifest.model_dump_json()
        row = existing.get(name)
        if row is None:
            db.add(
                Plugin(
                    user_id=user_id,
                    name=name,
                    version=manifest.version,
                    entrypoint=manifest.entrypoint,
                    manifest_json=canonical,
                    status="enabled",
                )
            )
            added.append(name)
        elif row.deleted_at is not None:
            row.user_id = user_id
            row.version = manifest.version
            row.entrypoint = manifest.entrypoint
            row.manifest_json = canonical
            row.status = "enabled"
            row.deleted_at = None
            row.last_error_code = None
            row.updated_at = utc_now()
            added.append(name)
        elif row.deleted_at is None and (
            row.version != manifest.version
            or row.entrypoint != manifest.entrypoint
            or row.manifest_json != canonical
        ):
            row.version = manifest.version
            row.entrypoint = manifest.entrypoint
            row.manifest_json = canonical
            row.status = "enabled"
            row.last_error_code = None
            row.updated_at = utc_now()
            updated.append(name)
    for name, row in sorted(active.items()):
        if name not in discovered and row.status in {"enabled", "disabled"}:
            row.deleted_at = utc_now()
            row.status = "uninstalled"
            row.updated_at = utc_now()
            removed.append(name)
    add_audit_event(
        db,
        action="plugins.rescan",
        result="success",
        actor_user_id=user_id,
        target="plugins",
        metadata={"added": added, "updated": updated, "removed": removed},
    )
    db.commit()
    return {"added": added, "updated": updated, "removed": removed}


def list_plugins(db: OrmSession) -> list[Plugin]:
    """Return non-deleted plugins with newest first."""
    return list(
        db.scalars(
            select(Plugin)
            .where(Plugin.deleted_at.is_(None))
            .order_by(Plugin.created_at.desc())
        )
    )


def get_plugin(db: OrmSession, name: str) -> Plugin | None:
    """Return one non-deleted plugin by name."""
    return _active_plugin(db, name)


def set_plugin_status(
    db: OrmSession,
    user_id: str,
    name: str,
    status: Literal["enabled", "disabled"],
) -> Plugin:
    """Enable or disable a registered plugin (audited)."""
    row = _active_plugin(db, name)
    if row is None:
        raise PluginError("plugin_not_found")
    row.status = status
    row.last_error_code = None
    row.updated_at = utc_now()
    add_audit_event(
        db,
        action="plugins.set_status",
        result="success",
        actor_user_id=user_id,
        target=row.id,
        metadata={"plugin": row.name, "status": status},
    )
    db.commit()
    return row


def uninstall_plugin(db: OrmSession, user_id: str, name: str) -> Plugin:
    """Soft-delete a registered plugin and disable its capabilities (audited)."""
    row = _active_plugin(db, name)
    if row is None:
        raise PluginError("plugin_not_found")
    row.deleted_at = utc_now()
    row.status = "uninstalled"
    row.updated_at = utc_now()
    for run in db.scalars(select(PluginRun).where(PluginRun.plugin_id == row.id)).all():
        db.delete(run)
    add_audit_event(
        db,
        action="plugins.uninstall",
        result="success",
        actor_user_id=user_id,
        target=row.id,
        metadata={"plugin": row.name},
    )
    db.commit()
    return row


def list_plugin_runs(db: OrmSession, plugin_id: str, limit: int = 20) -> list[PluginRun]:
    """Return bounded run history for one plugin, newest first."""
    return list(
        db.scalars(
            select(PluginRun)
            .where(PluginRun.plugin_id == plugin_id)
            .order_by(PluginRun.created_at.desc())
            .limit(max(1, min(limit, RUN_HISTORY_LIMIT)))
        )
    )


def plugin_run_count(db: OrmSession, plugin_id: str) -> int:
    """Return the total run count for one plugin."""
    return int(db.scalar(select(func.count(PluginRun.id)).where(PluginRun.plugin_id == plugin_id)) or 0)


def invoke_plugin(
    db: OrmSession,
    user_id: str,
    name: str,
    method: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    """Invoke one allowlisted capability out-of-process with bounded run history."""
    row = _active_plugin(db, name)
    if row is None:
        raise PluginError("plugin_not_found")
    if row.status != "enabled":
        raise PluginError("plugin_disabled")
    try:
        manifest = PluginManifest.model_validate_json(row.manifest_json)
    except ValidationError:
        raise PluginError("manifest_invalid") from None
    capability = next((item for item in manifest.capabilities if item.method == method), None)
    if capability is None:
        raise PluginError("capability_not_found")
    root = configured_plugins_dir()
    if root is None:
        raise PluginError("plugins_not_configured")
    plugin_dir = _plugin_dir(root, row.name)
    if not plugin_dir.is_dir():
        raise PluginError("plugin_dir_missing")

    settings = get_settings()
    broker = PluginBroker(plugin_dir, timeout_seconds=settings.plugin_invoke_timeout_seconds)
    started = utc_now()
    try:
        result = broker.invoke(plugin_dir, row.entrypoint, method, arguments)
        status = "success"
        error_code: str | None = None
    except PluginTimeoutError as exc:
        status = "failure"
        error_code = str(exc)
        result = {}
    except BrokerError as exc:
        status = "failure"
        error_code = str(exc)
        result = {}
    duration_ms = max(0, int((utc_now() - started).total_seconds() * 1000))
    db.add(
        PluginRun(
            plugin_id=row.id,
            method=method,
            status=status,
            error_code=error_code,
            duration_ms=duration_ms,
        )
    )
    db.flush()
    stale_runs = db.scalars(
        select(PluginRun)
        .where(PluginRun.plugin_id == row.id)
        .order_by(PluginRun.created_at.desc(), PluginRun.id.desc())
        .offset(RUN_HISTORY_LIMIT)
    ).all()
    for stale_run in stale_runs:
        db.delete(stale_run)
    row.last_error_code = error_code
    row.updated_at = utc_now()
    add_audit_event(
        db,
        action="plugins.invoke",
        result=status,
        actor_user_id=user_id,
        target=row.id,
        metadata={"plugin": row.name, "method": method, "status": status, "duration_ms": duration_ms},
    )
    db.commit()
    if status == "failure":
        raise PluginError(error_code or "plugin_error")
    return result
