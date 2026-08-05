"""Browser-managed Open WebUI integration (URL embed, no secrets)."""

from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from app.core.config import Settings
from app.modules.system.schemas import OpenWebUIConfigRequest, OpenWebUIStatusResponse

_CONFIG_NAME = "openwebui.json"
_MAX_URL_LENGTH = 512
_LABEL_RE = re.compile(r"^[\w \-.'/]{1,64}$")


def _config_path(data_dir: Path) -> Path:
    return data_dir.expanduser().resolve() / "runtime" / _CONFIG_NAME


def validate_openwebui_url(url: str) -> str:
    """Accept only absolute http(s) Open WebUI origins suitable for the browser."""
    cleaned = (url or "").strip()
    if not cleaned or len(cleaned) > _MAX_URL_LENGTH:
        raise ValueError("openwebui_url_invalid")
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("openwebui_url_invalid")
    if not parsed.hostname:
        raise ValueError("openwebui_url_invalid")
    if parsed.username or parsed.password:
        raise ValueError("openwebui_url_credentials_forbidden")
    # Disallow fragments and keep path simple; Open WebUI is usually root or a subpath.
    if parsed.fragment or "\\" in cleaned or "\n" in cleaned or "\r" in cleaned:
        raise ValueError("openwebui_url_invalid")
    # Normalize bare "/" and trailing slashes for a stable embed src.
    path = parsed.path or ""
    if path == "/":
        path = ""
    elif path.endswith("/"):
        path = path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{parsed.netloc}{path}{query}"


def _read_file(data_dir: Path) -> dict[str, object] | None:
    target = _config_path(data_dir)
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_openwebui_config(data_dir: Path, payload: OpenWebUIConfigRequest) -> OpenWebUIStatusResponse:
    """Persist Open WebUI integration settings for the Chat workspace."""
    enabled = payload.enabled
    url = validate_openwebui_url(payload.url) if payload.url and payload.url.strip() else None
    if enabled and not url:
        raise ValueError("openwebui_url_required")
    label = (payload.label or "Open WebUI").strip() or "Open WebUI"
    if not _LABEL_RE.match(label):
        raise ValueError("openwebui_label_invalid")
    embed = bool(payload.embed)
    body = {
        "enabled": enabled,
        "url": url,
        "label": label,
        "embed": embed,
    }
    target = _config_path(data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(body, stream, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return OpenWebUIStatusResponse(
        enabled=enabled and bool(url),
        configured=bool(url),
        url=url if enabled else url,
        label=label,
        embed=embed,
        source="browser",
        detail="Open WebUI integration saved." if enabled else "Open WebUI integration disabled.",
    )


def delete_openwebui_config(data_dir: Path) -> None:
    """Remove browser-managed Open WebUI settings."""
    target = _config_path(data_dir)
    try:
        target.unlink()
    except FileNotFoundError:
        return


def openwebui_status(settings: Settings) -> OpenWebUIStatusResponse:
    """Return redacted Open WebUI integration status for the Chat workspace."""
    stored = _read_file(settings.data_dir)
    env_url = (settings.openwebui_url or "").strip() or None
    if stored is not None:
        raw_url = stored.get("url")
        url = None
        if isinstance(raw_url, str) and raw_url.strip():
            try:
                url = validate_openwebui_url(raw_url)
            except ValueError:
                url = None
        enabled = bool(stored.get("enabled", True)) and bool(url)
        label = stored.get("label") if isinstance(stored.get("label"), str) else "Open WebUI"
        label = label.strip() or "Open WebUI"
        embed = bool(stored.get("embed", True))
        return OpenWebUIStatusResponse(
            enabled=enabled,
            configured=bool(url),
            url=url if enabled else url,
            label=label[:64],
            embed=embed,
            source="browser",
            detail="Open WebUI is ready in Chat." if enabled else ("Open WebUI URL saved but embedding is disabled." if url else "Configure Open WebUI in Admin."),
        )

    if env_url:
        try:
            url = validate_openwebui_url(env_url)
        except ValueError:
            url = None
        if url:
            return OpenWebUIStatusResponse(
                enabled=True,
                configured=True,
                url=url,
                label="Open WebUI",
                embed=True,
                source="environment",
                detail="Open WebUI is configured from OPENWEBUI_URL.",
            )

    return OpenWebUIStatusResponse(
        enabled=False,
        configured=False,
        url=None,
        label="Open WebUI",
        embed=True,
        source="none",
        detail="Point Nexus at your local Open WebUI (often http://<pi-ip>:8080).",
    )
