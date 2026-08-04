"""deployment hardening backup metadata

Revision ID: 0008_deployment_hardening
Revises: 0007_workspace_views
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_deployment_hardening"
down_revision: Union[str, None] = "0007_workspace_views"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add encrypted/off-host backup status without changing existing artifacts."""
    with op.batch_alter_table("backup_records") as batch:
        batch.add_column(sa.Column("encryption_status", sa.String(length=24), nullable=True))
        batch.add_column(sa.Column("encrypted_relative_path", sa.String(length=256), nullable=True))
        batch.add_column(sa.Column("encrypted_size_bytes", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("encrypted_sha256", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("replication_status", sa.String(length=24), nullable=True))
        batch.add_column(sa.Column("replicated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("replication_error_code", sa.String(length=96), nullable=True))
        batch.create_index("ix_backup_records_replication_status", ["replication_status"])


def downgrade() -> None:
    """Remove Milestone 10 backup metadata columns."""
    with op.batch_alter_table("backup_records") as batch:
        batch.drop_index("ix_backup_records_replication_status")
        batch.drop_column("replication_error_code")
        batch.drop_column("replicated_at")
        batch.drop_column("replication_status")
        batch.drop_column("encrypted_sha256")
        batch.drop_column("encrypted_size_bytes")
        batch.drop_column("encrypted_relative_path")
        batch.drop_column("encryption_status")
