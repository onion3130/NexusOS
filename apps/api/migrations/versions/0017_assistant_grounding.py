"""assistant grounded-response source provenance

Revision ID: 0017_assistant_grounding
Revises: 0016_embeddings
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_assistant_grounding"
down_revision: Union[str, None] = "0016_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_source_references",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("message_id", sa.String(36), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("source_type", sa.String(24), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("chunk_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("retrieval_mode", sa.String(16), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("lexical_score", sa.Float(), nullable=True),
        sa.Column("semantic_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["note_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "chunk_id", name="uq_assistant_source_message_chunk"),
    )
    for name, column in (
        ("ix_assistant_source_references_message_id", "message_id"),
        ("ix_assistant_source_references_conversation_id", "conversation_id"),
        ("ix_assistant_source_references_user_id", "user_id"),
        ("ix_assistant_source_references_source_id", "source_id"),
        ("ix_assistant_source_references_chunk_id", "chunk_id"),
        ("ix_assistant_source_references_created_at", "created_at"),
    ):
        op.create_index(name, "assistant_source_references", [column])


def downgrade() -> None:
    for name in (
        "ix_assistant_source_references_created_at",
        "ix_assistant_source_references_chunk_id",
        "ix_assistant_source_references_source_id",
        "ix_assistant_source_references_user_id",
        "ix_assistant_source_references_conversation_id",
        "ix_assistant_source_references_message_id",
    ):
        op.drop_index(name, table_name="assistant_source_references")
    op.drop_table("assistant_source_references")
