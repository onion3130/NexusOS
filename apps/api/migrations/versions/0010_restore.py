"""restore metadata for verified backups

Revision ID: 0010_restore
Revises: 0009_notification_channels
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_restore"
down_revision: Union[str, None] = "0009_notification_channels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Track the last restore performed from a verified backup record."""
    with op.batch_alter_table("backup_records") as batch:
        batch.add_column(sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_backup_records_restored_at", ["restored_at"])


def downgrade() -> None:
    """Remove the restore timestamp metadata."""
    with op.batch_alter_table("backup_records") as batch:
        batch.drop_index("ix_backup_records_restored_at")
        batch.drop_column("restored_at")
