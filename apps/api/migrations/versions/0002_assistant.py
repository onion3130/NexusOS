"""assistant conversations, messages, model runs, and tool calls

Revision ID: 0002_assistant
Revises: 0001_identity
Create Date: 2026-08-02
"""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "0002_assistant"
down_revision: Union[str, None] = "0001_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create owned conversation and bounded assistant execution tables."""
    op.create_table("conversations", sa.Column("id", sa.String(length=36), nullable=False), sa.Column("user_id", sa.String(length=36), nullable=False), sa.Column("title", sa.String(length=120), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_conversations_id", "conversations", ["id"], unique=False)
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"], unique=False)
    op.create_index("ix_conversations_updated_at", "conversations", ["updated_at"], unique=False)

    op.create_table("model_runs", sa.Column("id", sa.String(length=36), nullable=False), sa.Column("conversation_id", sa.String(length=36), nullable=False), sa.Column("provider", sa.String(length=64), nullable=False), sa.Column("model", sa.String(length=128), nullable=True), sa.Column("status", sa.String(length=32), nullable=False), sa.Column("input_tokens", sa.Integer(), nullable=True), sa.Column("output_tokens", sa.Integer(), nullable=True), sa.Column("latency_ms", sa.Integer(), nullable=True), sa.Column("error_code", sa.String(length=96), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_model_runs_conversation_id", "model_runs", ["conversation_id"], unique=False)
    op.create_index("ix_model_runs_created_at", "model_runs", ["created_at"], unique=False)

    op.create_table("messages", sa.Column("id", sa.String(length=36), nullable=False), sa.Column("conversation_id", sa.String(length=36), nullable=False), sa.Column("role", sa.String(length=16), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("sequence", sa.Integer(), nullable=False), sa.Column("model_run_id", sa.String(length=36), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["model_run_id"], ["model_runs.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("conversation_id", "sequence", name="uq_messages_conversation_sequence"))
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], unique=False)
    op.create_index("ix_messages_model_run_id", "messages", ["model_run_id"], unique=False)

    op.create_table("tool_calls", sa.Column("id", sa.String(length=36), nullable=False), sa.Column("model_run_id", sa.String(length=36), nullable=False), sa.Column("tool_key", sa.String(length=96), nullable=False), sa.Column("status", sa.String(length=32), nullable=False), sa.Column("input_json", sa.Text(), nullable=False), sa.Column("output_json", sa.Text(), nullable=True), sa.Column("error_code", sa.String(length=96), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.ForeignKeyConstraint(["model_run_id"], ["model_runs.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_tool_calls_model_run_id", "tool_calls", ["model_run_id"], unique=False)

    bind = op.get_bind()
    permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key = 'system.read_overview'")).first()
    permission_id = permission[0] if permission else str(uuid4())
    if permission is None:
        bind.execute(sa.text("INSERT INTO permissions (id, key, description) VALUES (:id, :key, :description)"), {"id": permission_id, "key": "system.read_overview", "description": "Read Raspberry Pi system telemetry"})
    owner_role = bind.execute(sa.text("SELECT id FROM roles WHERE key = 'owner'")).first()
    if owner_role:
        existing_link = bind.execute(sa.text("SELECT 1 FROM role_permissions WHERE role_id = :role_id AND permission_id = :permission_id"), {"role_id": owner_role[0], "permission_id": permission_id}).first()
        if existing_link is None:
            bind.execute(sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :permission_id)"), {"role_id": owner_role[0], "permission_id": permission_id})


def downgrade() -> None:
    """Remove assistant tables in dependency order."""
    op.drop_index("ix_tool_calls_model_run_id", table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_index("ix_messages_model_run_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_model_runs_created_at", table_name="model_runs")
    op.drop_index("ix_model_runs_conversation_id", table_name="model_runs")
    op.drop_table("model_runs")
    # `system.read_overview` is shared identity authorization data. It may have
    # existed before this revision, so the downgrade deliberately preserves it.
    op.drop_index("ix_conversations_updated_at", table_name="conversations")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_index("ix_conversations_id", table_name="conversations")
    op.drop_table("conversations")
