"""media item index

Revision ID: 0014_media
Revises: 0013_finance
Create Date: 2026-08-04

Adds the derived media item index over operator-approved media roots, plus the
``media.read`` and ``media.write`` owner permissions.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_media"
down_revision: Union[str, None] = "0013_finance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _seed_permission(bind, key: str, description: str) -> None:
    """Insert one permission and grant it to the owner role idempotently."""
    existing = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
    if existing:
        permission_id = existing[0]
    else:
        import uuid

        permission_id = str(uuid.uuid4())
        bind.execute(
            sa.text("INSERT INTO permissions (id, key, description) VALUES (:id, :key, :description)"),
            {"id": permission_id, "key": key, "description": description},
        )
    owner = bind.execute(sa.text("SELECT id FROM roles WHERE key='owner'")).first()
    if owner:
        granted = bind.execute(sa.text("SELECT id FROM role_permissions WHERE role_id=:role AND permission_id=:permission"), {"role": owner[0], "permission": permission_id}).first()
        if not granted:
            bind.execute(
                sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role, :permission)"),
                {"role": owner[0], "permission": permission_id},
            )


def _unseed_permission(bind, key: str) -> None:
    """Remove a permission and its role grants on downgrade."""
    permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": key}).first()
    if permission:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:permission"), {"permission": permission[0]})
        bind.execute(sa.text("DELETE FROM permissions WHERE id=:permission"), {"permission": permission[0]})


def upgrade() -> None:
    op.create_table(
        "media_items",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("root_key", sa.String(24), nullable=False),
        sa.Column("relative_path", sa.String(512), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("extension", sa.String(16), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("thumbnail_path", sa.String(256), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("root_key", "relative_path", name="uq_media_items_root_path"),
    )
    for name, column in (
        ("ix_media_items_user_id", "user_id"),
        ("ix_media_items_extension", "extension"),
        ("ix_media_items_mime_type", "mime_type"),
        ("ix_media_items_sha256", "sha256"),
        ("ix_media_items_deleted_at", "deleted_at"),
        ("ix_media_items_updated_at", "updated_at"),
    ):
        op.create_index(name, "media_items", [column])

    bind = op.get_bind()
    _seed_permission(bind, "media.read", "Browse the indexed media library")
    _seed_permission(bind, "media.write", "Trigger media library rescans")


def downgrade() -> None:
    for name in (
        "ix_media_items_updated_at",
        "ix_media_items_deleted_at",
        "ix_media_items_sha256",
        "ix_media_items_mime_type",
        "ix_media_items_extension",
        "ix_media_items_user_id",
    ):
        op.drop_index(name, table_name="media_items")
    op.drop_table("media_items")
    bind = op.get_bind()
    _unseed_permission(bind, "media.read")
    _unseed_permission(bind, "media.write")
