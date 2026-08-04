"""calendar events, categories, and reminders

Revision ID: 0012_calendar
Revises: 0011_backup_lifecycle
Create Date: 2026-08-04

Adds user-owned calendar categories, events, and event reminders, plus the
``calendar.read`` and ``calendar.write`` owner permissions.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_calendar"
down_revision: Union[str, None] = "0011_backup_lifecycle"
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
        granted = bind.execute(sa.text("SELECT 1 FROM role_permissions WHERE role_id=:role AND permission_id=:permission"), {"role": owner[0], "permission": permission_id}).first()
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
        "calendar_categories",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("normalized_name", sa.String(64), nullable=False),
        sa.Column("color", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_calendar_categories_user_name"),
    )
    op.create_index("ix_calendar_categories_user_id", "calendar_categories", ["user_id"])
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["calendar_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("ix_calendar_events_user_id", "user_id"),
        ("ix_calendar_events_starts_at", "starts_at"),
        ("ix_calendar_events_deleted_at", "deleted_at"),
        ("ix_calendar_events_updated_at", "updated_at"),
    ):
        op.create_index(name, "calendar_events", [column])
    op.create_table(
        "calendar_event_reminders",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offset_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["calendar_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("ix_calendar_event_reminders_user_id", "user_id"),
        ("ix_calendar_event_reminders_event_id", "event_id"),
        ("ix_calendar_event_reminders_scheduled_for", "scheduled_for"),
        ("ix_calendar_event_reminders_status", "status"),
    ):
        op.create_index(name, "calendar_event_reminders", [column])

    bind = op.get_bind()
    _seed_permission(bind, "calendar.read", "Read calendar events and categories")
    _seed_permission(bind, "calendar.write", "Create, update, and delete calendar events")


def downgrade() -> None:
    for name in (
        "ix_calendar_event_reminders_status",
        "ix_calendar_event_reminders_scheduled_for",
        "ix_calendar_event_reminders_event_id",
        "ix_calendar_event_reminders_user_id",
    ):
        op.drop_index(name, table_name="calendar_event_reminders")
    op.drop_table("calendar_event_reminders")
    for name in (
        "ix_calendar_events_updated_at",
        "ix_calendar_events_deleted_at",
        "ix_calendar_events_starts_at",
        "ix_calendar_events_user_id",
    ):
        op.drop_index(name, table_name="calendar_events")
    op.drop_table("calendar_events")
    op.drop_index("ix_calendar_categories_user_id", table_name="calendar_categories")
    op.drop_table("calendar_categories")
    bind = op.get_bind()
    _unseed_permission(bind, "calendar.read")
    _unseed_permission(bind, "calendar.write")
