"""Server-owned catalog of permitted host maintenance capabilities."""

from __future__ import annotations

from app.modules.host_actions.schemas import ActionCatalogItem, ActionKey

_CATALOG = {
    "maintenance.create_backup": ActionCatalogItem(key="maintenance.create_backup", title="Create database backup", description="Create and verify a hot SQLite backup on the configured data volume.", risk_level="medium"),
    "maintenance.verify_backup": ActionCatalogItem(key="maintenance.verify_backup", title="Verify a database backup", description="Run a bounded integrity check against one NexusOS-created backup.", risk_level="low"),
    "maintenance.integrity_check": ActionCatalogItem(key="maintenance.integrity_check", title="Check database integrity", description="Run SQLite integrity_check against the live NexusOS database.", risk_level="medium"),
    "maintenance.restore_backup": ActionCatalogItem(key="maintenance.restore_backup", title="Restore database from a verified backup", description="Restore the live database from one verified NexusOS backup after creating a safety backup of the current database. NexusOS must be restarted after a successful restore.", risk_level="high"),
    "maintenance.retention_cleanup": ActionCatalogItem(key="maintenance.retention_cleanup", title="Run backup retention cleanup", description="Prune verified backups beyond the configured retention policy (BACKUP_RETENTION_COUNT and BACKUP_RETENTION_DAYS). The newest verified backup is always retained. No individual backup is selected manually.", risk_level="medium"),
    "maintenance.rotate_encryption_key": ActionCatalogItem(key="maintenance.rotate_encryption_key", title="Rotate backup encryption key", description="Re-encrypt every replicated backup artifact from BACKUP_REPLICATION_KEY_PREVIOUS to the current BACKUP_ENCRYPTION_KEY. Configure the previous key in the server environment before confirming; remove it after the rotation completes.", risk_level="high"),
    "plugins.rescan": ActionCatalogItem(key="plugins.rescan", title="Rescan approved plugin directory", description="Re-scan PLUGINS_DIR, register new or changed plugin manifests, and unregister plugins whose directory disappeared. Lifecycle changes require explicit confirmation.", risk_level="medium"),
    "plugins.enable": ActionCatalogItem(key="plugins.enable", title="Enable a plugin", description="Enable a registered plugin so its capabilities can be invoked after confirmation.", risk_level="low"),
    "plugins.disable": ActionCatalogItem(key="plugins.disable", title="Disable a plugin", description="Disable a registered plugin so none of its capabilities can be invoked.", risk_level="low"),
    "plugins.uninstall": ActionCatalogItem(key="plugins.uninstall", title="Uninstall a plugin", description="Uninstall a registered plugin and disable all of its capabilities. Run history is removed with the plugin.", risk_level="high"),
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
    if action_key in {"maintenance.verify_backup", "maintenance.restore_backup"}:
        return set(value) <= {"backup_id"} and isinstance(value.get("backup_id"), str) and bool(value.get("backup_id"))
    if action_key in {"plugins.enable", "plugins.disable", "plugins.uninstall"}:
        name = value.get("name")
        return set(value) <= {"name"} and isinstance(name, str) and bool(name.strip()) and len(name) <= 64
    return not value
