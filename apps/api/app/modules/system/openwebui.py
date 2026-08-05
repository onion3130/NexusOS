"""Browser-managed Open WebUI integration (Assistant embed + filesystem bridge)."""

from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from app.core.config import Settings
from app.modules.system.schemas import (
    OpenWebUIConfigRequest,
    OpenWebUIFilesystemBridge,
    OpenWebUIStatusResponse,
)

_CONFIG_NAME = "openwebui.json"
_MAX_URL_LENGTH = 512
_LABEL_RE = re.compile(r"^[\w \-.'/]{1,64}$")
_DEFAULT_LABEL = "Nexus Assistant"
_CONTAINER_FS_PATH = "/data/nexus"
_SHARED_DIRNAME = "shared"


def _config_path(data_dir: Path) -> Path:
    return data_dir.expanduser().resolve() / "runtime" / _CONFIG_NAME


def shared_host_path(data_dir: Path) -> Path:
    """Shared folder under DATA_DIR for files both Nexus and Open WebUI can use."""
    return data_dir.expanduser().resolve() / _SHARED_DIRNAME


def ensure_shared_directory(data_dir: Path) -> Path:
    """Create the shared filesystem folder if missing."""
    path = shared_host_path(data_dir)
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass
    return path


def filesystem_bridge_for(data_dir: Path) -> OpenWebUIFilesystemBridge:
    """Describe the Nexus ↔ Open WebUI shared folder (paths only, no contents)."""
    host = shared_host_path(data_dir)
    exists = host.is_dir()
    host_label = str(host)
    if exists:
        detail = (
            f"Shared folder ready. Mount it into Open WebUI as {_CONTAINER_FS_PATH}:ro "
            f"(see scripts/link-openwebui-nexus.sh). Drop files here for Knowledge / chat context."
        )
    else:
        detail = (
            f"Shared folder will be created at {host_label}. "
            f"Link Open WebUI with a read-only mount to {_CONTAINER_FS_PATH}."
        )
    return OpenWebUIFilesystemBridge(
        host_path=host_label,
        container_path=_CONTAINER_FS_PATH,
        linked=exists,
        detail=detail,
    )


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
    if parsed.fragment or "\\" in cleaned or "\n" in cleaned or "\r" in cleaned:
        raise ValueError("openwebui_url_invalid")
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


def _status(
    data_dir: Path,
    *,
    enabled: bool,
    configured: bool,
    url: str | None,
    label: str,
    embed: bool,
    source: str,
    detail: str,
) -> OpenWebUIStatusResponse:
    ensure_shared_directory(data_dir)
    return OpenWebUIStatusResponse(
        enabled=enabled,
        configured=configured,
        url=url,
        label=label[:64],
        embed=embed,
        source=source,  # type: ignore[arg-type]
        detail=detail,
        filesystem=filesystem_bridge_for(data_dir),
    )


def write_openwebui_config(data_dir: Path, payload: OpenWebUIConfigRequest) -> OpenWebUIStatusResponse:
    """Persist Open WebUI integration settings for the Assistant workspace."""
    enabled = payload.enabled
    url = validate_openwebui_url(payload.url) if payload.url and payload.url.strip() else None
    if enabled and not url:
        raise ValueError("openwebui_url_required")
    label = (payload.label or _DEFAULT_LABEL).strip() or _DEFAULT_LABEL
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
    return _status(
        data_dir,
        enabled=enabled and bool(url),
        configured=bool(url),
        url=url if enabled else url,
        label=label,
        embed=embed,
        source="browser",
        detail="Assistant is Open WebUI." if enabled else "Open WebUI assistant disabled.",
    )


def delete_openwebui_config(data_dir: Path) -> None:
    """Remove browser-managed Open WebUI settings."""
    target = _config_path(data_dir)
    try:
        target.unlink()
    except FileNotFoundError:
        return


def openwebui_status(settings: Settings) -> OpenWebUIStatusResponse:
    """Return Open WebUI Assistant status plus shared filesystem bridge metadata."""
    data_dir = settings.data_dir
    ensure_shared_directory(data_dir)
    stored = _read_file(data_dir)
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
        label = stored.get("label") if isinstance(stored.get("label"), str) else _DEFAULT_LABEL
        label = (label or _DEFAULT_LABEL).strip() or _DEFAULT_LABEL
        embed = bool(stored.get("embed", True))
        return _status(
            data_dir,
            enabled=enabled,
            configured=bool(url),
            url=url if enabled else url,
            label=label,
            embed=embed,
            source="browser",
            detail=(
                "Assistant is Open WebUI with a shared Nexus filesystem folder."
                if enabled
                else ("Open WebUI URL saved but disabled." if url else "Configure Open WebUI in Admin.")
            ),
        )

    if env_url:
        try:
            url = validate_openwebui_url(env_url)
        except ValueError:
            url = None
        if url:
            return _status(
                data_dir,
                enabled=True,
                configured=True,
                url=url,
                label=_DEFAULT_LABEL,
                embed=True,
                source="environment",
                detail="Assistant is Open WebUI (OPENWEBUI_URL) with a shared Nexus filesystem folder.",
            )

    return _status(
        data_dir,
        enabled=False,
        configured=False,
        url=None,
        label=_DEFAULT_LABEL,
        embed=True,
        source="none",
        detail="Point Nexus at your local Open WebUI (often http://<pi-ip>:8080) to use it as Assistant.",
    )
