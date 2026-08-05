"""Provision matching Open WebUI accounts when Nexus users are created."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.modules.system.openwebui import openwebui_status, validate_openwebui_url

log = logging.getLogger(__name__)

_EMAIL_LOCAL = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")


@dataclass(frozen=True)
class OpenWebUIProvisionResult:
    """Bounded outcome of one Open WebUI account provision attempt."""

    ok: bool
    status: str
    detail: str
    email: str | None = None
    role: str | None = None


def nexus_username_to_email(username: str) -> str:
    """Map a Nexus username to a stable Open WebUI email identity."""
    local = re.sub(r"[^a-z0-9._-]+", ".", username.strip().lower())
    local = local.strip(".-_") or "user"
    if not _EMAIL_LOCAL.match(local):
        local = "user"
    return f"{local}@nexus.local"


def _resolve_base_url(settings: Settings) -> str | None:
    status = openwebui_status(settings)
    if status.url:
        return status.url.rstrip("/")
    env = (settings.openwebui_url or "").strip()
    if not env:
        return None
    try:
        return validate_openwebui_url(env)
    except ValueError:
        return None


def _admin_api_key(settings: Settings) -> str | None:
    if settings.openwebui_api_key is None:
        return None
    value = settings.openwebui_api_key.get_secret_value().strip()
    return value or None


def _admin_email(settings: Settings) -> str | None:
    value = (settings.openwebui_admin_email or "").strip().lower()
    return value or None


def _admin_password(settings: Settings) -> str | None:
    if settings.openwebui_admin_password is None:
        return None
    value = settings.openwebui_admin_password.get_secret_value()
    return value if value else None


async def _signin_admin_token(base_url: str, email: str, password: str, timeout: float) -> str | None:
    """Exchange Open WebUI admin email/password for a bearer JWT."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            response = await client.post(
                f"{base_url}/api/v1/auths/signin",
                json={"email": email, "password": password},
                headers={"Content-Type": "application/json"},
            )
    except httpx.HTTPError as exc:
        log.warning("openwebui signin failed: %s", type(exc).__name__)
        return None
    if response.status_code >= 400:
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    token = body.get("token") if isinstance(body, dict) else None
    return token if isinstance(token, str) and token.strip() else None


async def _auth_headers(settings: Settings, base_url: str) -> dict[str, str] | None:
    """Build Authorization headers from API key or admin password login."""
    key = _admin_api_key(settings)
    if key:
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    email = _admin_email(settings)
    password = _admin_password(settings)
    if email and password:
        token = await _signin_admin_token(base_url, email, password, settings.openwebui_timeout_seconds)
        if token:
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return None


def provision_configured(settings: Settings) -> bool:
    """Return whether Open WebUI admin credentials are available for provisioning."""
    if not _resolve_base_url(settings):
        return False
    if _admin_api_key(settings):
        return True
    return bool(_admin_email(settings) and _admin_password(settings))


async def provision_openwebui_user(
    settings: Settings,
    *,
    username: str,
    password: str,
    is_owner: bool = False,
    display_name: str | None = None,
) -> OpenWebUIProvisionResult:
    """Create (or confirm) an Open WebUI account matching a Nexus user.

    Uses admin API ``POST /api/v1/auths/add``. Email is ``{username}@nexus.local``.
    Role is ``admin`` for owners and ``user`` otherwise (active, not pending).
    """
    base_url = _resolve_base_url(settings)
    if not base_url:
        return OpenWebUIProvisionResult(ok=False, status="skipped", detail="openwebui_url_not_configured")
    if not provision_configured(settings):
        return OpenWebUIProvisionResult(
            ok=False,
            status="skipped",
            detail="openwebui_admin_credentials_missing",
        )
    if len(password.encode("utf-8")) > 72:
        return OpenWebUIProvisionResult(ok=False, status="failed", detail="openwebui_password_too_long")

    email = nexus_username_to_email(username)
    role = "admin" if is_owner else "user"
    name = (display_name or username).strip() or username
    headers = await _auth_headers(settings, base_url)
    if headers is None:
        return OpenWebUIProvisionResult(ok=False, status="failed", detail="openwebui_admin_auth_failed")

    payload: dict[str, Any] = {
        "name": name[:100],
        "email": email,
        "password": password,
        "role": role,
        "profile_image_url": "/user.png",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.openwebui_timeout_seconds, follow_redirects=False, trust_env=False) as client:
            response = await client.post(f"{base_url}/api/v1/auths/add", json=payload, headers=headers)
            body_text = response.text[:500]
    except httpx.HTTPError as exc:
        log.warning("openwebui provision transport error: %s", type(exc).__name__)
        return OpenWebUIProvisionResult(ok=False, status="failed", detail="openwebui_unreachable", email=email, role=role)

    if response.status_code < 300:
        return OpenWebUIProvisionResult(ok=True, status="created", detail="openwebui_user_created", email=email, role=role)

    # Email already registered → treat as linked (idempotent).
    lowered = body_text.lower()
    if response.status_code == 400 and ("email" in lowered or "taken" in lowered or "exist" in lowered):
        return OpenWebUIProvisionResult(ok=True, status="exists", detail="openwebui_user_exists", email=email, role=role)

    if response.status_code in {401, 403}:
        return OpenWebUIProvisionResult(ok=False, status="failed", detail="openwebui_admin_forbidden", email=email, role=role)

    log.warning("openwebui provision failed status=%s body=%s", response.status_code, body_text[:200])
    return OpenWebUIProvisionResult(ok=False, status="failed", detail=f"openwebui_http_{response.status_code}", email=email, role=role)


def provision_openwebui_user_sync(
    settings: Settings,
    *,
    username: str,
    password: str,
    is_owner: bool = False,
    display_name: str | None = None,
) -> OpenWebUIProvisionResult:
    """Sync wrapper for CLI / non-async bootstrap paths."""
    import asyncio

    try:
        return asyncio.run(
            provision_openwebui_user(
                settings,
                username=username,
                password=password,
                is_owner=is_owner,
                display_name=display_name,
            )
        )
    except RuntimeError:
        # Nested event loop (rare); fail closed without breaking account create.
        return OpenWebUIProvisionResult(ok=False, status="failed", detail="openwebui_async_unavailable")
