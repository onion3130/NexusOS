"""Milestone 2 identity and session routes."""

from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings, get_settings
from app.core.rate_limit import clear_login_failures, login_retry_after, record_login_failure
from app.core.security import create_access_token, tokens_match
from app.db.session import get_db
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_csrf
from app.modules.identity.schemas import AuthResponse, LoginRequest, SessionResponse, UserResponse
from app.modules.identity.service import (
    authenticate,
    create_session,
    find_by_refresh_token,
    get_session,
    get_user,
    list_sessions,
    revoke_session,
    role_names,
    permission_names,
    rotate_session,
)

router = APIRouter(prefix="/api/v1/auth", tags=["identity"])
ACCESS_COOKIE = "nexus_access"
REFRESH_COOKIE = "nexus_refresh"
CSRF_COOKIE = "nexus_csrf"


def _user_response(user) -> UserResponse:
    """Convert a user model to a safe response."""
    return UserResponse(
        id=user.id,
        username=user.username,
        roles=role_names(user),
        permissions=permission_names(user),
        is_active=user.is_active,
        created_at=user.created_at,
    )


def _set_auth_cookies(response: Response, settings: Settings, access_token: str, refresh_token: str, csrf_token: str) -> None:
    """Set short-lived access and rotated refresh/CSRF cookies."""
    secure = settings.session_cookie_secure
    common = {"secure": secure, "httponly": True, "samesite": "lax", "path": "/"}
    response.set_cookie(ACCESS_COOKIE, access_token, max_age=15 * 60, **common)
    response.set_cookie(REFRESH_COOKIE, refresh_token, max_age=30 * 24 * 60 * 60, **common)
    response.set_cookie(CSRF_COOKIE, csrf_token, max_age=30 * 24 * 60 * 60, secure=secure, httponly=False, samesite="lax", path="/")


def _clear_auth_cookies(response: Response) -> None:
    """Clear all identity cookies."""
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/")


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: OrmSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> AuthResponse:
    """Authenticate credentials and establish a tracked browser session."""
    retry_after = login_retry_after(payload.username, request.client.host if request.client else None)
    if retry_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts; try again later",
            headers={"Retry-After": str(max(1, int(retry_after + 0.5)))},
        )
    user = authenticate(db, payload.username, payload.password)
    if user is None:
        record_login_failure(payload.username, request.client.host if request.client else None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    clear_login_failures(payload.username, request.client.host if request.client else None)
    session, refresh_token, csrf_token = create_session(db, user, request.headers.get("user-agent"))
    access_token, expires_at = create_access_token(settings, user.id, session.id)
    db.commit()
    _set_auth_cookies(response, settings, access_token, refresh_token, csrf_token)
    return AuthResponse(user=_user_response(user), expires_at=expires_at)


@router.post("/refresh", response_model=AuthResponse)
def refresh(request: Request, response: Response, db: OrmSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> AuthResponse:
    """Rotate a valid refresh session and issue a new access token."""
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    csrf_header = request.headers.get("X-CSRF-Token")
    if not raw_refresh or not csrf_cookie or csrf_cookie != csrf_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    session = find_by_refresh_token(db, raw_refresh)
    if session is None or session.user is None or not tokens_match(session.csrf_token_hash, csrf_cookie):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    rotated = rotate_session(db, session)
    if rotated is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    refresh_token, csrf_token = rotated
    access_token, expires_at = create_access_token(settings, session.user_id, session.id)
    db.commit()
    _set_auth_cookies(response, settings, access_token, refresh_token, csrf_token)
    return AuthResponse(user=_user_response(session.user), expires_at=expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    """Revoke the current session."""
    require_csrf(request, context)
    revoke_session(db, context.session, context.user.id)
    _clear_auth_cookies(response)


@router.get("/me", response_model=UserResponse)
def me(context: AuthContext = Depends(get_auth_context)) -> UserResponse:
    """Return the current authenticated user."""
    return _user_response(context.user)


@router.get("/sessions", response_model=list[SessionResponse])
def sessions(db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[SessionResponse]:
    """List current user's session metadata without token values."""
    return [
        SessionResponse(
            id=item.id,
            created_at=item.created_at,
            last_seen_at=item.last_seen_at,
            expires_at=item.expires_at,
            revoked_at=item.revoked_at,
            user_agent=item.user_agent,
        )
        for item in list_sessions(db, context.user.id)
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    request: Request,
    response: Response,
    db: OrmSession = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
) -> None:
    """Revoke one session owned by the current user."""
    require_csrf(request, context)
    session = get_session(db, session_id)
    if session is None or session.user_id != context.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    revoke_session(db, session, context.user.id)
    if session.id == context.session.id:
        _clear_auth_cookies(response)
