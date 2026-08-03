"""FastAPI dependencies for authenticated identity requests."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token, tokens_match
from app.db.models import Session, User
from app.db.session import get_db
from app.modules.identity.service import get_session, get_user

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    """Authenticated user/session pair and whether cookie auth was used."""

    user: User
    session: Session
    used_cookie: bool


def _unauthorized() -> HTTPException:
    """Return a generic authentication failure without resource disclosure."""
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def get_auth_context(
    request: Request,
    db: OrmSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext:
    """Authenticate a bearer token or the HttpOnly access cookie."""
    token = credentials.credentials if credentials else request.cookies.get("nexus_access")
    used_cookie = credentials is None
    if not token:
        raise _unauthorized()
    payload = decode_access_token(settings, token)
    if payload is None:
        raise _unauthorized()
    user_id = str(payload["sub"])
    session_id = str(payload["sid"])
    session = get_session(db, session_id)
    if session is None or session.user_id != user_id or session.revoked_at is not None or not session.user.is_active:
        raise _unauthorized()
    user = get_user(db, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return AuthContext(user=user, session=session, used_cookie=used_cookie)


def require_csrf(request: Request, context: AuthContext) -> None:
    """Require a matching CSRF header for cookie-authenticated mutations."""
    if not context.used_cookie:
        return
    cookie_token = request.cookies.get("nexus_csrf")
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or not tokens_match(context.session.csrf_token_hash, cookie_token) or cookie_token != header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def require_permission(permission: str, context: AuthContext) -> None:
    """Require one server-owned permission without exposing resource existence."""
    from app.modules.identity.service import permission_names

    if permission not in permission_names(context.user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def require_user(context: AuthContext = Depends(get_auth_context)) -> User:
    """Return the authenticated user for route handlers."""
    return context.user
