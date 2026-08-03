"""Pydantic schemas for identity and session endpoints."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials submitted to the local login endpoint."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


class UserResponse(BaseModel):
    """Safe user representation that never contains password material."""

    id: str
    username: str
    roles: list[str]
    permissions: list[str]
    is_active: bool
    created_at: datetime


class SessionResponse(BaseModel):
    """Safe browser session metadata."""

    id: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    user_agent: str | None


class AuthResponse(BaseModel):
    """Login/refresh response containing the current user and expiry."""

    user: UserResponse
    expires_at: datetime


class ErrorResponse(BaseModel):
    """Stable safe error envelope for identity failures."""

    error: dict[str, object]
