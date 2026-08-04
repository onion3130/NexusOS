"""outbound notification channel deliveries

Revision ID: 0009_notification_channels
Revises: 0008_deployment_hardening
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_notification_channels"
down_revision: Union[str, None] = "0008_deployment_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create per-channel delivery rows and seed the notification settings permission."""
    op.create_table(
        "notification_channel_deliveries",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("notification_id", sa.String(36), nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(96), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_id", "channel", name="uq_notification_deliveries_notification_channel"),
    )
    for name, column in (
        ("ix_notification_deliveries_notification_id", "notification_id"),
        ("ix_notification_deliveries_status", "status"),
        ("ix_notification_deliveries_available_at", "available_at"),
    ):
        op.create_index(name, "notification_channel_deliveries", [column])
    bind = op.get_bind()
    permission = ("notifications.settings", "Read notification channel settings and send test messages")
    bind.execute(
        sa.text("INSERT INTO permissions (id, key, description) VALUES (:id, :key, :description)"),
        {"id": str(__import__("uuid").uuid4()), "key": permission[0], "description": permission[1]},
    )
    owner = bind.execute(sa.text("SELECT id FROM roles WHERE key='owner'")).first()
    if owner:
        granted = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": permission[0]}).first()
        if granted:
            bind.execute(
                sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role, :permission)"),
                {"role": owner[0], "permission": granted[0]},
            )


def downgrade() -> None:
    """Remove the delivery table and the notification settings permission."""
    for name in (
        "ix_notification_deliveries_available_at",
        "ix_notification_deliveries_status",
        "ix_notification_deliveries_notification_id",
    ):
        op.drop_index(name, table_name="notification_channel_deliveries")
    op.drop_table("notification_channel_deliveries")
    bind = op.get_bind()
    permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": "notifications.settings"}).first()
    if permission:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:permission"), {"permission": permission[0]})
        bind.execute(sa.text("DELETE FROM permissions WHERE id=:permission"), {"permission": permission[0]})
