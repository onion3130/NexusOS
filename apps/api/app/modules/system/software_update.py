"""Browser-requested software update handshake with a host-side agent.

The API never executes shell, git, or Docker commands. It only writes a bounded
request file under the private data volume. A host agent (systemd) must perform
the fixed update steps and write status back to the same directory.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app import __version__
from app.core.config import Settings
from app.db.base import utc_now

UPDATE_DIRNAME = "update"
REQUEST_FILENAME = "request.json"
STATUS_FILENAME = "status.json"
LOG_FILENAME = "log.txt"
MAX_LOG_CHARS = 4000
STALE_QUEUE_SECONDS = 120
COOLDOWN_SECONDS = 60

UpdateAction = Literal["check", "apply"]
UpdateState = Literal["idle", "queued", "running", "succeeded", "failed", "agent_missing"]


class SoftwareUpdateStatus(BaseModel):
    """Redacted update status for the owner Admin panel."""

    state: UpdateState = "idle"
    action: UpdateAction | None = None
    request_id: str | None = None
    message: str = "No update requested."
    agent_available: bool = False
    current_version: str = __version__
    current_commit: str | None = None
    target_commit: str | None = None
    requested_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    log_tail: str | None = None
    can_request: bool = True


class SoftwareUpdateRequestBody(BaseModel):
    """Bounded browser request payload."""

    model_config = {"extra": "forbid"}

    action: UpdateAction = "apply"
    confirm: bool = Field(default=False, description="Must be true for apply.")


def _update_dir(data_dir: Path) -> Path:
    return data_dir.expanduser().resolve() / "runtime" / UPDATE_DIRNAME


def _request_path(data_dir: Path) -> Path:
    return _update_dir(data_dir) / REQUEST_FILENAME


def _status_path(data_dir: Path) -> Path:
    return _update_dir(data_dir) / STATUS_FILENAME


def _log_path(data_dir: Path) -> Path:
    return _update_dir(data_dir) / LOG_FILENAME


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _safe_commit(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or not re.fullmatch(r"[0-9a-fA-F]{7,40}", cleaned):
        return None
    return cleaned.lower()


def _safe_message(value: Any, fallback: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    # Strip control characters and cap length so status is UI-safe.
    cleaned = "".join(ch for ch in value.strip() if ch.isprintable() or ch in "\n\t ")
    return cleaned[:400] or fallback


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, separators=(",", ":"), sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _read_log_tail(data_dir: Path) -> str | None:
    path = _log_path(data_dir)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    cleaned = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t ")
    if len(cleaned) > MAX_LOG_CHARS:
        cleaned = cleaned[-MAX_LOG_CHARS:]
    return cleaned or None


def read_software_update_status(settings: Settings) -> SoftwareUpdateStatus:
    """Return the current update handshake state without host paths."""
    data_dir = settings.data_dir
    status_data = _read_json(_status_path(data_dir)) or {}
    request_data = _read_json(_request_path(data_dir))
    now = utc_now()

    state_raw = status_data.get("state")
    state: UpdateState = state_raw if state_raw in {"idle", "queued", "running", "succeeded", "failed", "agent_missing"} else "idle"
    action_raw = status_data.get("action") or (request_data or {}).get("action")
    action: UpdateAction | None = action_raw if action_raw in {"check", "apply"} else None
    requested_at = _parse_dt(status_data.get("requested_at") or (request_data or {}).get("requested_at"))
    started_at = _parse_dt(status_data.get("started_at"))
    finished_at = _parse_dt(status_data.get("finished_at"))
    agent_heartbeat = _parse_dt(status_data.get("agent_heartbeat_at"))
    agent_available = bool(agent_heartbeat and now - agent_heartbeat <= timedelta(seconds=90))

    if request_data is not None and state in {"idle", "queued", "agent_missing"}:
        state = "queued"
        if requested_at is not None and now - requested_at > timedelta(seconds=STALE_QUEUE_SECONDS) and not agent_available:
            state = "agent_missing"

    if state == "running" and started_at is not None and now - started_at > timedelta(minutes=45):
        # Long builds on Pi are allowed; surface a soft message rather than inventing failure.
        message = _safe_message(status_data.get("message"), "Update is still running on the host agent.")
    else:
        defaults = {
            "idle": "No update requested.",
            "queued": "Update queued. Waiting for the host update agent…",
            "running": "Host agent is updating NexusOS…",
            "succeeded": "Update completed successfully.",
            "failed": "Update failed. Review the log and try again.",
            "agent_missing": "Update is queued, but the host agent has not claimed it. Install or start nexus-update-agent once on the Pi.",
        }
        message = _safe_message(status_data.get("message"), defaults[state])

    can_request = state not in {"queued", "running"}
    if finished_at is not None and now - finished_at < timedelta(seconds=COOLDOWN_SECONDS):
        can_request = False

    return SoftwareUpdateStatus(
        state=state,
        action=action,
        request_id=str(status_data.get("request_id") or (request_data or {}).get("id") or "") or None,
        message=message,
        agent_available=agent_available,
        current_version=str(status_data.get("current_version") or __version__)[:32],
        current_commit=_safe_commit(status_data.get("current_commit")),
        target_commit=_safe_commit(status_data.get("target_commit")),
        requested_at=requested_at,
        started_at=started_at,
        finished_at=finished_at,
        log_tail=_read_log_tail(data_dir) if state in {"running", "succeeded", "failed", "agent_missing"} else None,
        can_request=can_request,
    )


def request_software_update(settings: Settings, *, user_id: str, action: UpdateAction, confirm: bool) -> SoftwareUpdateStatus:
    """Queue a fixed host-side update or check request for the local agent."""
    if action == "apply" and not confirm:
        raise ValueError("confirm_required")
    current = read_software_update_status(settings)
    if not current.can_request:
        raise ValueError("update_busy")

    request_id = str(uuid4())
    now = utc_now()
    payload = {
        "id": request_id,
        "action": action,
        "requested_at": now.isoformat(),
        "requested_by": user_id,
        "schema_version": 1,
    }
    data_dir = settings.data_dir
    _write_json_atomic(_request_path(data_dir), payload)
    _write_json_atomic(
        _status_path(data_dir),
        {
            "state": "queued",
            "action": action,
            "request_id": request_id,
            "message": "Update queued. Waiting for the host update agent…",
            "requested_at": now.isoformat(),
            "current_version": __version__,
            "agent_heartbeat_at": None,
        },
    )
    return read_software_update_status(settings)
