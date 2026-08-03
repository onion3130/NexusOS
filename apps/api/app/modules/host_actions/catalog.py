"""Server-owned catalog of permitted host maintenance capabilities."""

from __future__ import annotations

from app.modules.host_actions.schemas import ActionCatalogItem, ActionKey

_CATALOG = {
    "maintenance.create_backup": ActionCatalogItem(key="maintenance.create_backup", title="Create database backup", description="Create and verify a hot SQLite backup on the configured data volume.", risk_level="medium"),
    "maintenance.verify_backup": ActionCatalogItem(key="maintenance.verify_backup", title="Verify a database backup", description="Run a bounded integrity check against one NexusOS-created backup.", risk_level="low"),
    "maintenance.integrity_check": ActionCatalogItem(key="maintenance.integrity_check", title="Check database integrity", description="Run SQLite integrity_check against the live NexusOS database.", risk_level="medium"),
}


def catalog() -> list[ActionCatalogItem]:
    """Return a stable copy of enabled safe actions."""
    return list(_CATALOG.values())


def get_action(action_key: str) -> ActionCatalogItem | None:
    """Resolve only a known action key."""
    return _CATALOG.get(action_key)


def is_valid_input(action_key: ActionKey, value: dict[str, object]) -> bool:
    """Reject dynamic paths, commands, and oversized action payloads."""
    if len(value) > 4:
        return False
    if action_key == "maintenance.verify_backup":
        return set(value) <= {"backup_id"} and isinstance(value.get("backup_id"), str) and bool(value.get("backup_id"))
    return not value
