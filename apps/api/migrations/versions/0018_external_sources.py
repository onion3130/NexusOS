"""external text sources and ingestion lifecycle

Revision ID: 0018_external_sources
Revises: 0017_assistant_grounding
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "0018_external_sources"
down_revision: Union[str, None] = "0017_assistant_grounding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _permission(bind, key: str, description: str) -> None:
    row = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
    permission_id = row[0] if row else str(uuid.uuid4())
    if not row:
        bind.execute(sa.text("INSERT INTO permissions (id,key,description) VALUES (:id,:key,:description)"), {"id": permission_id, "key": key, "description": description})
    owner = bind.execute(sa.text("SELECT id FROM roles WHERE key='owner'")).first()
    if owner:
        bind.execute(sa.text("INSERT OR IGNORE INTO role_permissions (role_id,permission_id) VALUES (:role,:permission)"), {"role": owner[0], "permission": permission_id})


def _remove_permission(bind, key: str) -> None:
    row = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
    if row:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:id"), {"id": row[0]})
        bind.execute(sa.text("DELETE FROM permissions WHERE id=:id"), {"id": row[0]})


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(36), nullable=False), sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False), sa.Column("title", sa.String(160), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False), sa.Column("stored_path", sa.String(128), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False), sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(96), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("stored_path", name="uq_sources_stored_path"),
    )
    for name, column in (("user_id","user_id"),("sha256","sha256"),("status","status"),("updated_at","updated_at"),("deleted_at","deleted_at")):
        op.create_index(f"ix_sources_{name}", "sources", [column])
    op.create_table(
        "source_versions",
        sa.Column("id",sa.String(36),nullable=False), sa.Column("source_id",sa.String(36),nullable=False), sa.Column("user_id",sa.String(36),nullable=False),
        sa.Column("version",sa.Integer(),nullable=False), sa.Column("content_hash",sa.String(64),nullable=False), sa.Column("content_length",sa.Integer(),nullable=False),
        sa.Column("parser",sa.String(32),nullable=False), sa.Column("parser_version",sa.String(16),nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(["source_id"],["sources.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("source_id","version",name="uq_source_versions_source_version"),
    )
    for name,column in (("source_id","source_id"),("user_id","user_id")): op.create_index(f"ix_source_versions_{name}","source_versions",[column])
    op.create_table(
        "source_chunks",
        sa.Column("id",sa.String(36),nullable=False), sa.Column("source_id",sa.String(36),nullable=False), sa.Column("source_version_id",sa.String(36),nullable=False), sa.Column("user_id",sa.String(36),nullable=False),
        sa.Column("chunk_index",sa.Integer(),nullable=False), sa.Column("content",sa.Text(),nullable=False), sa.Column("content_hash",sa.String(64),nullable=False), sa.Column("start_offset",sa.Integer(),nullable=False), sa.Column("end_offset",sa.Integer(),nullable=False), sa.Column("source_version",sa.Integer(),nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(["source_id"],["sources.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["source_version_id"],["source_versions.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("source_version_id","chunk_index",name="uq_source_chunks_version_index"),
    )
    for name,column in (("source_id","source_id"),("source_version_id","source_version_id"),("user_id","user_id")): op.create_index(f"ix_source_chunks_{name}","source_chunks",[column])
    # Existing grounded references remain note-compatible while allowing an
    # external source/chunk pair to be recorded in the same provenance table.
    with op.batch_alter_table("assistant_source_references") as batch:
        batch.alter_column("source_id", existing_type=sa.String(36), nullable=True)
        batch.alter_column("chunk_id", existing_type=sa.String(36), nullable=True)
        batch.add_column(sa.Column("external_source_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("external_chunk_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_assistant_source_external_source", "sources", ["external_source_id"], ["id"], ondelete="CASCADE")
        batch.create_foreign_key("fk_assistant_source_external_chunk", "source_chunks", ["external_chunk_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_assistant_source_external_source_id", ["external_source_id"])
        batch.create_index("ix_assistant_source_external_chunk_id", ["external_chunk_id"])
    bind = op.get_bind()
    _permission(bind, "sources.read", "Read owned external sources")
    _permission(bind, "sources.write", "Upload and import external sources")
    _permission(bind, "sources.delete", "Archive and delete external sources")


def downgrade() -> None:
    bind = op.get_bind()
    external_references = bind.execute(sa.text("SELECT COUNT(*) FROM assistant_source_references WHERE source_type='external_source' OR external_source_id IS NOT NULL OR external_chunk_id IS NOT NULL")).scalar() or 0
    source_rows = bind.execute(sa.text("SELECT (SELECT COUNT(*) FROM sources) + (SELECT COUNT(*) FROM source_versions) + (SELECT COUNT(*) FROM source_chunks)")).scalar() or 0
    if external_references or source_rows:
        raise RuntimeError("cannot downgrade 0018_external_sources while external source data exists")
    with op.batch_alter_table("assistant_source_references") as batch:
        batch.drop_index("ix_assistant_source_external_chunk_id")
        batch.drop_index("ix_assistant_source_external_source_id")
        batch.drop_constraint("fk_assistant_source_external_chunk", type_="foreignkey")
        batch.drop_constraint("fk_assistant_source_external_source", type_="foreignkey")
        batch.drop_column("external_chunk_id")
        batch.drop_column("external_source_id")
        batch.alter_column("source_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column("chunk_id", existing_type=sa.String(36), nullable=False)
    for key in ("sources.delete","sources.write","sources.read"): _remove_permission(bind,key)
    for name in ("ix_source_chunks_user_id","ix_source_chunks_source_version_id","ix_source_chunks_source_id"): op.drop_index(name,table_name="source_chunks")
    op.drop_table("source_chunks")
    for name in ("ix_source_versions_user_id","ix_source_versions_source_id"): op.drop_index(name,table_name="source_versions")
    op.drop_table("source_versions")
    for name in ("ix_sources_deleted_at","ix_sources_updated_at","ix_sources_status","ix_sources_sha256","ix_sources_user_id"): op.drop_index(name,table_name="sources")
    op.drop_table("sources")
