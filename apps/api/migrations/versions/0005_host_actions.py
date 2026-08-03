"""safe host actions, backups, and maintenance proposals

Revision ID: 0005_host_actions
Revises: 0004_notes_search
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_host_actions"
down_revision: Union[str, None] = "0004_notes_search"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create durable safe-action proposals and verified backup metadata."""
    op.create_table(
        "host_action_proposals",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("action_key", sa.String(96), nullable=False),
        sa.Column("risk_level", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=True),
        sa.Column("idempotency_key", sa.String(160), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(96), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    for name, column in (("ix_host_action_proposals_user_id", "user_id"), ("ix_host_action_proposals_action_key", "action_key"), ("ix_host_action_proposals_status", "status"), ("ix_host_action_proposals_job_id", "job_id"), ("ix_host_action_proposals_expires_at", "expires_at"), ("ix_host_action_proposals_created_at", "created_at")):
        op.create_index(name, "host_action_proposals", [column])
    op.create_table(
        "backup_records",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("relative_path", sa.String(256), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("integrity_result", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("relative_path"),
    )
    for name, column in (("ix_backup_records_user_id", "user_id"), ("ix_backup_records_status", "status"), ("ix_backup_records_created_at", "created_at")):
        op.create_index(name, "backup_records", [column])
    bind = op.get_bind()
    permissions = (
        ("system.host_actions", "Propose and confirm safe host maintenance actions"),
        ("system.backups.read", "Read owned backup metadata"),
        ("system.audit.read", "Read the current user's host-action audit history"),
    )
    for key, description in permissions:
        bind.execute(sa.text("INSERT OR IGNORE INTO permissions (id, key, description) VALUES (:id, :key, :description)"), {"id": str(__import__("uuid").uuid4()), "key": key, "description": description})
    owner = bind.execute(sa.text("SELECT id FROM roles WHERE key='owner'")).first()
    if owner:
        for key, _ in permissions:
            permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
            if permission:
                bind.execute(sa.text("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (:role, :permission)"), {"role": owner[0], "permission": permission[0]})


def downgrade() -> None:
    """Remove Milestone 8 host-action metadata and permissions."""
    bind = op.get_bind()
    for key in ("system.host_actions", "system.backups.read", "system.audit.read"):
        permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
        if permission:
            bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:permission"), {"permission": permission[0]})
            bind.execute(sa.text("DELETE FROM permissions WHERE id=:permission"), {"permission": permission[0]})
    for name in ("ix_backup_records_created_at", "ix_backup_records_status", "ix_backup_records_user_id"):
        op.drop_index(name, table_name="backup_records")
    op.drop_table("backup_records")
    for name in ("ix_host_action_proposals_created_at", "ix_host_action_proposals_expires_at", "ix_host_action_proposals_job_id", "ix_host_action_proposals_status", "ix_host_action_proposals_action_key", "ix_host_action_proposals_user_id"):
        op.drop_index(name, table_name="host_action_proposals")
    op.drop_table("host_action_proposals")
