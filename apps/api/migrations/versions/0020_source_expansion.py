"""external source expansion: PDF parsing and URL sources

Revision ID: 0020_source_expansion
Revises: 0019_source_sync
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_source_expansion"
down_revision: Union[str, None] = "0019_source_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("source_url", sa.String(512), nullable=True))
    op.create_index("ix_sources_source_url", "sources", ["source_url"])


def downgrade() -> None:
    op.drop_index("ix_sources_source_url", table_name="sources")
    op.drop_column("sources", "source_url")
