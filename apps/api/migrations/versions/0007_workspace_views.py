"""workspace read-view permission

Revision ID: 0007_workspace_views
Revises: 0006_v1_hardening
Create Date: 2026-08-04
"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "0007_workspace_views"
down_revision: Union[str, None] = "0006_v1_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSION = "workspace_views.read"
_DESCRIPTION = "Read approved files, projects, Git, and Docker metadata"


def upgrade() -> None:
    """Seed the read-only workspace view permission for the owner role."""
    bind = op.get_bind()
    bind.execute(
        sa.text("INSERT OR IGNORE INTO permissions (id, key, description) VALUES (:id, :key, :description)"),
        {"id": str(uuid.uuid4()), "key": _PERMISSION, "description": _DESCRIPTION},
    )
    owner = bind.execute(sa.text("SELECT id FROM roles WHERE key='owner'")).first()
    permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": _PERMISSION}).first()
    if owner and permission:
        bind.execute(
            sa.text("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (:role, :permission)"),
            {"role": owner[0], "permission": permission[0]},
        )


def downgrade() -> None:
    """Remove the workspace view permission and owner assignment."""
    bind = op.get_bind()
    permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key=:key"), {"key": _PERMISSION}).first()
    if permission:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id=:permission"), {"permission": permission[0]})
        bind.execute(sa.text("DELETE FROM permissions WHERE id=:permission"), {"permission": permission[0]})
