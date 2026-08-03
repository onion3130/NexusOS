"""v1.0 worker claim indexes

Revision ID: 0006_v1_hardening
Revises: 0005_host_actions
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006_v1_hardening"
down_revision: Union[str, None] = "0005_host_actions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes for bounded reminder and host-action claims."""
    op.create_index(
        "ix_reminders_due_claim",
        "reminders",
        ["status", "scheduled_for", "locked_until"],
    )
    op.create_index(
        "ix_jobs_host_action_claim",
        "jobs",
        ["job_type", "status", "available_at", "locked_until"],
    )


def downgrade() -> None:
    """Remove the v1.0 worker claim indexes."""
    op.drop_index("ix_jobs_host_action_claim", table_name="jobs")
    op.drop_index("ix_reminders_due_claim", table_name="reminders")
