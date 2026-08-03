"""tasks, recurrence, reminders, notifications, jobs, and approvals

Revision ID: 0003_tasks_notifications
Revises: 0002_assistant
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_tasks_notifications"
down_revision: Union[str, None] = "0002_assistant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the productivity schema and seed owner task permissions."""
    op.create_table("task_categories", sa.Column("id", sa.String(36), nullable=False), sa.Column("user_id", sa.String(36), nullable=False), sa.Column("name", sa.String(64), nullable=False), sa.Column("normalized_name", sa.String(64), nullable=False), sa.Column("color", sa.String(32), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "normalized_name", name="uq_task_categories_user_name"))
    op.create_index("ix_task_categories_user_id", "task_categories", ["user_id"])
    op.create_table("tags", sa.Column("id", sa.String(36), nullable=False), sa.Column("user_id", sa.String(36), nullable=False), sa.Column("name", sa.String(64), nullable=False), sa.Column("normalized_name", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "normalized_name", name="uq_tags_user_name"))
    op.create_index("ix_tags_user_id", "tags", ["user_id"])
    op.create_table("task_series", sa.Column("id", sa.String(36), nullable=False), sa.Column("user_id", sa.String(36), nullable=False), sa.Column("recurrence_json", sa.Text(), nullable=False), sa.Column("timezone", sa.String(64), nullable=False), sa.Column("active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_task_series_user_id", "task_series", ["user_id"])
    op.create_table("tasks", sa.Column("id", sa.String(36), nullable=False), sa.Column("user_id", sa.String(36), nullable=False), sa.Column("series_id", sa.String(36), nullable=True), sa.Column("category_id", sa.String(36), nullable=True), sa.Column("title", sa.String(160), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("status", sa.String(24), nullable=False), sa.Column("priority", sa.String(16), nullable=False), sa.Column("due_at", sa.DateTime(timezone=True), nullable=True), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["category_id"], ["task_categories.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["series_id"], ["task_series.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    for name, column in (("ix_tasks_user_id", "user_id"), ("ix_tasks_series_id", "series_id"), ("ix_tasks_category_id", "category_id"), ("ix_tasks_status", "status"), ("ix_tasks_priority", "priority"), ("ix_tasks_due_at", "due_at"), ("ix_tasks_deleted_at", "deleted_at"), ("ix_tasks_updated_at", "updated_at")):
        op.create_index(name, "tasks", [column])
    op.create_table("task_tags", sa.Column("task_id", sa.String(36), nullable=False), sa.Column("tag_id", sa.String(36), nullable=False), sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("task_id", "tag_id"))
    op.create_table("reminders", sa.Column("id", sa.String(36), nullable=False), sa.Column("user_id", sa.String(36), nullable=False), sa.Column("task_id", sa.String(36), nullable=False), sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False), sa.Column("offset_minutes", sa.Integer(), nullable=True), sa.Column("status", sa.String(24), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True), sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True), sa.Column("last_error_code", sa.String(96), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    for name, column in (("ix_reminders_user_id", "user_id"), ("ix_reminders_task_id", "task_id"), ("ix_reminders_scheduled_for", "scheduled_for"), ("ix_reminders_status", "status"), ("ix_reminders_locked_until", "locked_until")):
        op.create_index(name, "reminders", [column])
    op.create_table("notifications", sa.Column("id", sa.String(36), nullable=False), sa.Column("user_id", sa.String(36), nullable=False), sa.Column("type", sa.String(48), nullable=False), sa.Column("title", sa.String(160), nullable=False), sa.Column("body", sa.String(512), nullable=False), sa.Column("task_id", sa.String(36), nullable=True), sa.Column("reminder_id", sa.String(36), nullable=True), sa.Column("dedupe_key", sa.String(160), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("read_at", sa.DateTime(timezone=True), nullable=True), sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True), sa.ForeignKeyConstraint(["reminder_id"], ["reminders.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("dedupe_key"))
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_task_id", "notifications", ["task_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_table("jobs", sa.Column("id", sa.String(36), nullable=False), sa.Column("job_type", sa.String(64), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("payload_json", sa.Text(), nullable=True), sa.Column("available_at", sa.DateTime(timezone=True), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True), sa.Column("idempotency_key", sa.String(160), nullable=True), sa.Column("last_error_code", sa.String(96), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=True), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("idempotency_key"))
    op.create_index("ix_jobs_job_type", "jobs", ["job_type"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_available_at", "jobs", ["available_at"])
    op.add_column("tool_calls", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tool_calls", sa.Column("processing_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tool_calls", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tool_calls", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    bind = op.get_bind()
    permissions = [("tasks.read", "Read owned tasks"), ("tasks.write", "Create and update owned tasks"), ("tasks.delete", "Soft-delete owned tasks"), ("notifications.read", "Read owned notifications"), ("notifications.write", "Update owned notification state"), ("assistant.task_actions", "Propose and approve assistant task actions")]
    for key, description in permissions:
        bind.execute(sa.text("INSERT INTO permissions (id, key, description) VALUES (:id, :key, :description)"), {"id": str(__import__("uuid").uuid4()), "key": key, "description": description})
    owner = bind.execute(sa.text("SELECT id FROM roles WHERE key='owner'")).first()
    if owner:
        for key, _ in permissions:
            permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
            if permission:
                bind.execute(sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role, :permission)"), {"role": owner[0], "permission": permission[0]})


def downgrade() -> None:
    """Remove the Milestone 6 schema and approval columns."""
    op.drop_column("tool_calls", "rejected_at")
    op.drop_column("tool_calls", "approved_at")
    op.drop_column("tool_calls", "processing_until")
    op.drop_column("tool_calls", "expires_at")
    op.drop_index("ix_jobs_available_at", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_job_type", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_task_id", table_name="notifications")
    op.drop_table("notifications")
    for name in ("ix_reminders_locked_until", "ix_reminders_status", "ix_reminders_scheduled_for", "ix_reminders_task_id", "ix_reminders_user_id"):
        op.drop_index(name, table_name="reminders")
    op.drop_table("reminders")
    op.drop_table("task_tags")
    for name in ("ix_tasks_updated_at", "ix_tasks_deleted_at", "ix_tasks_due_at", "ix_tasks_priority", "ix_tasks_status", "ix_tasks_category_id", "ix_tasks_series_id", "ix_tasks_user_id"):
        op.drop_index(name, table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_task_series_user_id", table_name="task_series")
    op.drop_table("task_series")
    op.drop_index("ix_tags_user_id", table_name="tags")
    op.drop_table("tags")
    op.drop_index("ix_task_categories_user_id", table_name="task_categories")
    op.drop_table("task_categories")
    bind = op.get_bind()
    for key in ("tasks.read", "tasks.write", "tasks.delete", "notifications.read", "notifications.write", "assistant.task_actions"):
        permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
        if permission:
            bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:permission"), {"permission": permission[0]})
            bind.execute(sa.text("DELETE FROM permissions WHERE id=:permission"), {"permission": permission[0]})
