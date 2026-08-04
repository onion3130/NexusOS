"""out-of-process plugin registry and run history

Revision ID: 0015_plugins
Revises: 0014_media
Create Date: 2026-08-04

Adds the plugin registry (declared capabilities in an operator-approved
plugins directory) and bounded run history, plus the ``plugins.read`` and
``plugins.write`` owner permissions.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_plugins"
down_revision: Union[str, None] = "0014_media"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _seed_permission(bind, key: str, description: str) -> None:
    """Insert one permission and grant it to the owner role idempotently."""
    existing = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
    if existing:
        permission_id = existing[0]
    else:
        import uuid

        permission_id = str(uuid.uuid4())
        bind.execute(
            sa.text("INSERT INTO permissions (id, key, description) VALUES (:id, :key, :description)"),
            {"id": permission_id, "key": key, "description": description},
        )
    owner = bind.execute(sa.text("SELECT id FROM roles WHERE key='owner'")).first()
    if owner:
        granted = bind.execute(sa.text("SELECT id FROM role_permissions WHERE role_id=:role AND permission_id=:permission"), {"role": owner[0], "permission": permission_id}).first()
        if not granted:
            bind.execute(
                sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role, :permission)"),
                {"role": owner[0], "permission": permission_id},
            )


def _unseed_permission(bind, key: str) -> None:
    """Remove a permission and its role grants on downgrade."""
    permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
    if permission:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:permission"), {"permission": permission[0]})
        bind.execute(sa.text("DELETE FROM permissions WHERE id=:permission"), {"permission": permission[0]})


def upgrade() -> None:
    op.create_table(
        "plugins",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("entrypoint", sa.String(256), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("last_error_code", sa.String(96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_plugins_name"),
    )
    for name, column in (
        ("ix_plugins_user_id", "user_id"),
        ("ix_plugins_status", "status"),
        ("ix_plugins_deleted_at", "deleted_at"),
        ("ix_plugins_updated_at", "updated_at"),
    ):
        op.create_index(name, "plugins", [column])
    op.create_table(
        "plugin_runs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("plugin_id", sa.String(36), nullable=False),
        sa.Column("method", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(96), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("ix_plugin_runs_plugin_id", "plugin_id"),
        ("ix_plugin_runs_status", "status"),
        ("ix_plugin_runs_created_at", "created_at"),
    ):
        op.create_index(name, "plugin_runs", [column])

    bind = op.get_bind()
    _seed_permission(bind, "plugins.read", "List installed plugins and their capabilities")
    _seed_permission(bind, "plugins.write", "Invoke plugin methods and manage plugin lifecycle")


def downgrade() -> None:
    for name in (
        "ix_plugin_runs_created_at",
        "ix_plugin_runs_status",
        "ix_plugin_runs_plugin_id",
    ):
        op.drop_index(name, table_name="plugin_runs")
    op.drop_table("plugin_runs")
    for name in (
        "ix_plugins_updated_at",
        "ix_plugins_deleted_at",
        "ix_plugins_status",
        "ix_plugins_user_id",
    ):
        op.drop_index(name, table_name="plugins")
    op.drop_table("plugins")
    bind = op.get_bind()
    _unseed_permission(bind, "plugins.read")
    _unseed_permission(bind, "plugins.write")
