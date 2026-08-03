"""notes, lexical search projection, and retrieval chunks

Revision ID: 0004_notes_search
Revises: 0003_tasks_notifications
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_notes_search"
down_revision: Union[str, None] = "0003_tasks_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create canonical notes and rebuildable derived search/retrieval data."""
    op.create_table(
        "notes",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (("ix_notes_user_id", "user_id"), ("ix_notes_status", "status"), ("ix_notes_updated_at", "updated_at"), ("ix_notes_deleted_at", "deleted_at")):
        op.create_index(name, "notes", [column])
    op.create_table(
        "note_tags",
        sa.Column("note_id", sa.String(36), nullable=False),
        sa.Column("tag_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("note_id", "tag_id"),
    )
    op.create_table(
        "note_search_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("note_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags_text", sa.Text(), nullable=False),
        sa.Column("indexed_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("note_id"),
    )
    op.create_index("ix_note_search_documents_note_id", "note_search_documents", ["note_id"])
    op.create_table(
        "note_chunks",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("note_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("note_id", "source_version", "chunk_index", name="uq_note_chunks_version_index"),
    )
    op.create_index("ix_note_chunks_note_id", "note_chunks", ["note_id"])
    op.create_index("ix_note_chunks_user_id", "note_chunks", ["user_id"])
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.exec_driver_sql("CREATE VIRTUAL TABLE notes_fts USING fts5(title, content, tags, tokenize='unicode61', prefix='2 3 4')")
    else:
        raise RuntimeError("Milestone 7 currently requires SQLite FTS5")
    permissions = (("notes.read", "Read owned notes and search"), ("notes.write", "Create and update owned notes"), ("notes.delete", "Soft-delete owned notes"))
    for key, description in permissions:
        bind.execute(sa.text("INSERT OR IGNORE INTO permissions (id, key, description) VALUES (:id, :key, :description)"), {"id": str(__import__("uuid").uuid4()), "key": key, "description": description})
    owner = bind.execute(sa.text("SELECT id FROM roles WHERE key = 'owner'")).first()
    if owner:
        for key, _ in permissions:
            permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key = :key"), {"key": key}).first()
            if permission:
                bind.execute(sa.text("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (:role, :permission)"), {"role": owner[0], "permission": permission[0]})


def downgrade() -> None:
    """Remove Milestone 7 tables and the SQLite FTS5 index."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.exec_driver_sql("DROP TABLE IF EXISTS notes_fts")
    for key in ("notes.read", "notes.write", "notes.delete"):
        permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
        if permission:
            bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:permission"), {"permission": permission[0]})
            bind.execute(sa.text("DELETE FROM permissions WHERE id=:permission"), {"permission": permission[0]})
    op.drop_index("ix_note_chunks_user_id", table_name="note_chunks")
    op.drop_index("ix_note_chunks_note_id", table_name="note_chunks")
    op.drop_table("note_chunks")
    op.drop_index("ix_note_search_documents_note_id", table_name="note_search_documents")
    op.drop_table("note_search_documents")
    op.drop_table("note_tags")
    for name in ("ix_notes_deleted_at", "ix_notes_updated_at", "ix_notes_status", "ix_notes_user_id"):
        op.drop_index(name, table_name="notes")
    op.drop_table("notes")
