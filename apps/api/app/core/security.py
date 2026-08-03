"""Security primitives for Milestone 2 identity flows."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

PASSWORD_HASHER = PasswordHasher()
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)


def hash_password(password: str) -> str:
    """Hash a password with Argon2id using the library's reviewed defaults."""
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password without leaking whether a hash or password was wrong."""
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """Return whether the current Argon2 parameters should be refreshed."""
    try:
        return PASSWORD_HASHER.check_needs_rehash(password_hash)
    except (VerificationError, InvalidHashError):
        return False


def new_opaque_token() -> str:
    """Create high-entropy URL-safe token material."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Hash a refresh or CSRF token before persistence."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(expected_hash: str, raw_token: str) -> bool:
    """Compare token material in constant time."""
    return hmac.compare_digest(expected_hash, hash_token(raw_token))


def create_access_token(settings: Settings, user_id: str, session_id: str) -> tuple[str, datetime]:
    """Create a short-lived HS256 access JWT with an explicit token type."""
    now = datetime.now(UTC)
    expires_at = now + ACCESS_TOKEN_TTL
    payload: dict[str, Any] = {
        "sub": user_id,
        "sid": session_id,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    return token, expires_at


def decode_access_token(settings: Settings, token: str) -> dict[str, Any] | None:
    """Decode an access JWT with an explicit algorithm allowlist."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "sid", "type", "exp", "iat"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload
