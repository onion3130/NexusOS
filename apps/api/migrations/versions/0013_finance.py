"""finance accounts, categories, and transactions

Revision ID: 0013_finance
Revises: 0012_calendar
Create Date: 2026-08-04

Adds user-owned finance accounts, categories, and integer-cent transactions,
plus the ``finance.read`` and ``finance.write`` owner permissions.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_finance"
down_revision: Union[str, None] = "0012_calendar"
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
        granted = bind.execute(sa.text("SELECT 1 FROM role_permissions WHERE role_id=:role AND permission_id=:permission"), {"role": owner[0], "permission": permission_id}).first()
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
        "finance_accounts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("account_type", sa.String(24), nullable=False),
        sa.Column("color", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("ix_finance_accounts_user_id", "user_id"),
        ("ix_finance_accounts_deleted_at", "deleted_at"),
    ):
        op.create_index(name, "finance_accounts", [column])
    op.create_table(
        "finance_categories",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("normalized_name", sa.String(64), nullable=False),
        sa.Column("color", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_finance_categories_user_name"),
    )
    op.create_index("ix_finance_categories_user_id", "finance_categories", ["user_id"])
    op.create_table(
        "finance_transactions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("note", sa.String(4000), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["finance_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["finance_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("ix_finance_transactions_user_id", "user_id"),
        ("ix_finance_transactions_account_id", "account_id"),
        ("ix_finance_transactions_occurred_at", "occurred_at"),
        ("ix_finance_transactions_deleted_at", "deleted_at"),
        ("ix_finance_transactions_updated_at", "updated_at"),
    ):
        op.create_index(name, "finance_transactions", [column])

    bind = op.get_bind()
    _seed_permission(bind, "finance.read", "Read finance accounts and transactions")
    _seed_permission(bind, "finance.write", "Create, update, and delete finance records")


def downgrade() -> None:
    for name in (
        "ix_finance_transactions_updated_at",
        "ix_finance_transactions_deleted_at",
        "ix_finance_transactions_occurred_at",
        "ix_finance_transactions_account_id",
        "ix_finance_transactions_user_id",
    ):
        op.drop_index(name, table_name="finance_transactions")
    op.drop_table("finance_transactions")
    op.drop_index("ix_finance_categories_user_id", table_name="finance_categories")
    op.drop_table("finance_categories")
    for name in (
        "ix_finance_accounts_deleted_at",
        "ix_finance_accounts_user_id",
    ):
        op.drop_index(name, table_name="finance_accounts")
    op.drop_table("finance_accounts")
    bind = op.get_bind()
    _unseed_permission(bind, "finance.read")
    _unseed_permission(bind, "finance.write")
