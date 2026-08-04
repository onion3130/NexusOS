"""optional note chunk embeddings for semantic retrieval

Revision ID: 0016_embeddings
Revises: 0015_plugins
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_embeddings"
down_revision: Union[str, None] = "0015_plugins"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _seed_permission(bind, key: str, description: str) -> None:
    existing = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
    if existing:
        permission_id = existing[0]
    else:
        import uuid
        permission_id = str(uuid.uuid4())
        bind.execute(sa.text("INSERT INTO permissions (id, key, description) VALUES (:id, :key, :description)"), {"id": permission_id, "key": key, "description": description})
    owner = bind.execute(sa.text("SELECT id FROM roles WHERE key='owner'")).first()
    if owner:
        granted = bind.execute(sa.text("SELECT 1 FROM role_permissions WHERE role_id=:role AND permission_id=:permission"), {"role": owner[0], "permission": permission_id}).first()
        if not granted:
            bind.execute(sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role, :permission)"), {"role": owner[0], "permission": permission_id})


def _unseed_permission(bind, key: str) -> None:
    permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
    if permission:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:permission"), {"permission": permission[0]})
        bind.execute(sa.text("DELETE FROM permissions WHERE id=:permission"), {"permission": permission[0]})


def upgrade() -> None:
    op.create_table(
        "note_chunk_embeddings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("chunk_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["note_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id", "provider", "model", name="uq_note_chunk_embeddings_provider_model"),
    )
    for name, column in (("ix_note_chunk_embeddings_chunk_id", "chunk_id"), ("ix_note_chunk_embeddings_user_id", "user_id"), ("ix_note_chunk_embeddings_status", "status"), ("ix_note_chunk_embeddings_available_at", "available_at"), ("ix_note_chunk_embeddings_updated_at", "updated_at")):
        op.create_index(name, "note_chunk_embeddings", [column])
    _seed_permission(op.get_bind(), "notes.semantic", "Use optional semantic and hybrid note retrieval")


def downgrade() -> None:
    bind = op.get_bind()
    _unseed_permission(bind, "notes.semantic")
    for name in ("ix_note_chunk_embeddings_updated_at", "ix_note_chunk_embeddings_available_at", "ix_note_chunk_embeddings_status", "ix_note_chunk_embeddings_user_id", "ix_note_chunk_embeddings_chunk_id"):
        op.drop_index(name, table_name="note_chunk_embeddings")
    op.drop_table("note_chunk_embeddings")
