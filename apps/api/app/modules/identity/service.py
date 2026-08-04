"""Identity services for owner bootstrap and session-based authentication."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession, selectinload

from app.core.security import (
    PASSWORD_HASHER,
    REFRESH_TOKEN_TTL,
    hash_password,
    hash_token,
    new_opaque_token,
    password_needs_rehash,
    tokens_match,
    verify_password,
)
from app.db.models import AuditEvent, Permission, Role, Session, User

DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash("nexus-invalid-user-dummy-password")

OWNER_PERMISSIONS = (
    ("identity.read_self", "Read the current user profile"),
    ("identity.manage_sessions", "Manage the current user's sessions"),
    ("admin.manage_users", "Manage local user accounts"),
    ("system.read_overview", "Read Raspberry Pi system telemetry"),
    ("tasks.read", "Read owned tasks"),
    ("tasks.write", "Create and update owned tasks"),
    ("tasks.delete", "Soft-delete owned tasks"),
    ("notifications.read", "Read owned notifications"),
    ("notifications.write", "Update owned notification state"),
    ("notifications.settings", "Read notification channel settings and send test messages"),
    ("assistant.task_actions", "Propose and approve assistant task actions"),
    ("notes.read", "Read owned notes and search"),
    ("notes.write", "Create and update owned notes"),
    ("notes.delete", "Soft-delete owned notes"),
    ("notes.semantic", "Use optional semantic and hybrid note retrieval"),
    ("system.host_actions", "Propose and confirm safe host maintenance actions"),
    ("system.backups.read", "Read owned backup metadata"),
    ("system.audit.read", "Read the current user's host-action audit history"),
    ("workspace_views.read", "Read approved files, projects, Git, and Docker metadata"),
    ("calendar.read", "Read calendar events and categories"),
    ("calendar.write", "Create, update, and delete calendar events"),
    ("finance.read", "Read finance accounts and transactions"),
    ("finance.write", "Create, update, and delete finance records"),
    ("media.read", "Browse the indexed media library"),
    ("media.write", "Trigger media library rescans"),
    ("plugins.read", "List installed plugins and their capabilities"),
    ("plugins.write", "Invoke plugin methods and manage plugin lifecycle"),
    ("sources.read", "Read owned external sources"),
    ("sources.write", "Upload and import external sources"),
    ("sources.delete", "Archive and delete external sources"),
)


def _now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    """Treat SQLite's naive UTC values as timezone-aware."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def add_audit_event(
    db: OrmSession,
    *,
    action: str,
    result: str,
    actor_user_id: str | None = None,
    target: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    """Append a bounded audit event without secrets or credentials."""
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            target=target,
            result=result,
            metadata_json=json.dumps(metadata, separators=(",", ":")) if metadata else None,
        )
    )


def get_user(db: OrmSession, user_id: str) -> User | None:
    """Load a user with roles and permissions for a request."""
    statement = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    return db.scalar(statement)


def get_user_by_username(db: OrmSession, username: str) -> User | None:
    """Load an active/inactive user by normalized username."""
    statement = (
        select(User)
        .where(User.username == username)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    return db.scalar(statement)


def get_session(db: OrmSession, session_id: str) -> Session | None:
    """Load one session and its user graph."""
    statement = (
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.user).selectinload(User.roles).selectinload(Role.permissions))
    )
    return db.scalar(statement)


def role_names(user: User) -> list[str]:
    """Return stable role keys for API responses."""
    return sorted(role.key for role in user.roles)


def permission_names(user: User) -> list[str]:
    """Return the union of permissions granted through the user's roles."""
    return sorted({permission.key for role in user.roles for permission in role.permissions})


def ensure_owner_role(db: OrmSession) -> Role:
    """Create the owner role and its baseline permissions idempotently."""
    role = db.scalar(select(Role).where(Role.key == "owner").options(selectinload(Role.permissions)))
    if role is None:
        role = Role(key="owner", description="Full local NexusOS owner")
        db.add(role)
        db.flush()
    existing = {permission.key: permission for permission in role.permissions}
    for key, description in OWNER_PERMISSIONS:
        permission = existing.get(key) or db.scalar(select(Permission).where(Permission.key == key))
        if permission is None:
            permission = Permission(key=key, description=description)
            db.add(permission)
        if permission not in role.permissions:
            role.permissions.append(permission)
    db.flush()
    return role


def bootstrap_owner(db: OrmSession, username: str, password: str) -> User:
    """Create the first owner account, refusing duplicate bootstrap."""
    normalized_username = username.strip().lower()
    if not normalized_username or len(normalized_username) > 64:
        raise ValueError("username must contain 1-64 characters")
    if len(password) < 12:
        raise ValueError("owner password must contain at least 12 characters")
    if db.scalar(select(User.id).limit(1)) is not None:
        raise ValueError("an owner account already exists")

    owner_role = ensure_owner_role(db)
    user = User(username=normalized_username, password_hash=hash_password(password), roles=[owner_role])
    db.add(user)
    db.flush()
    add_audit_event(db, action="identity.owner_bootstrap", result="success", actor_user_id=user.id, target=user.id)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: OrmSession, username: str, password: str) -> User | None:
    """Verify credentials with a generic failure result."""
    user = get_user_by_username(db, username.strip().lower())
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_valid = verify_password(password_hash, password)
    if user is None or not user.is_active or not password_valid:
        add_audit_event(db, action="identity.login", result="failure", metadata={"username": username[:64]})
        db.commit()
        return None
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    add_audit_event(db, action="identity.login", result="success", actor_user_id=user.id, target=user.id)
    db.commit()
    return get_user(db, user.id)


def create_session(db: OrmSession, user: User, user_agent: str | None) -> tuple[Session, str, str]:
    """Create a session and return the entity plus raw refresh/CSRF values."""
    refresh_token = new_opaque_token()
    csrf_token = new_opaque_token()
    session = Session(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        csrf_token_hash=hash_token(csrf_token),
        expires_at=_now() + REFRESH_TOKEN_TTL,
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(session)
    db.flush()
    return session, refresh_token, csrf_token


def rotate_session(db: OrmSession, session: Session) -> tuple[str, str] | None:
    """Rotate refresh and CSRF secrets, refusing expired/revoked sessions."""
    if session.revoked_at is not None or _aware(session.expires_at) <= _now():
        return None
    refresh_token = new_opaque_token()
    csrf_token = new_opaque_token()
    session.refresh_token_hash = hash_token(refresh_token)
    session.csrf_token_hash = hash_token(csrf_token)
    session.last_seen_at = _now()
    db.flush()
    return refresh_token, csrf_token


def find_by_refresh_token(db: OrmSession, refresh_token: str) -> Session | None:
    """Find a session by its hashed refresh token."""
    hashed = hash_token(refresh_token)
    statement = (
        select(Session)
        .where(Session.refresh_token_hash == hashed)
        .options(selectinload(Session.user).selectinload(User.roles).selectinload(Role.permissions))
    )
    session = db.scalar(statement)
    if session is not None and tokens_match(session.refresh_token_hash, refresh_token):
        return session
    return None


def revoke_session(db: OrmSession, session: Session, actor_user_id: str | None = None) -> None:
    """Revoke one session and write an audit event."""
    if session.revoked_at is None:
        session.revoked_at = _now()
    add_audit_event(db, action="identity.logout", result="success", actor_user_id=actor_user_id, target=session.id)
    db.commit()


def list_sessions(db: OrmSession, user_id: str) -> list[Session]:
    """Return a user's sessions newest first."""
    return list(db.scalars(select(Session).where(Session.user_id == user_id).order_by(Session.created_at.desc())))
