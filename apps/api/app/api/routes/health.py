"""Health endpoints for process and dependency readiness."""

from __future__ import annotations

import shutil
import tempfile
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app import __version__
from app.core.config import Settings, get_settings
from app.db.session import database_status

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/live", summary="Process liveness")
def live() -> dict[str, str]:
    """Report that the API process is alive without checking dependencies."""
    return {"status": "ok", "service": "nexus-api", "version": __version__}


@router.get("/ready", summary="Dependency readiness", response_model=None)
def ready(settings: Settings = Depends(get_settings)) -> JSONResponse | dict:
    """Report storage and database readiness without mutating the schema.

    Migrations are intentionally explicit and are not run by this endpoint.
    """
    data_dir = settings.data_dir
    checked_at = datetime.now(UTC).isoformat()
    storage_check: dict[str, object]

    if not data_dir.is_dir():
        storage_check = {"status": "not_ready", "reason": "data_dir_missing"}
    else:
        try:
            free_bytes = shutil.disk_usage(data_dir).free
            with tempfile.NamedTemporaryFile(dir=data_dir, prefix=".nexus-ready-", delete=True):
                pass
            storage_check = {"status": "ok", "free_bytes": free_bytes}
        except OSError:
            storage_check = {"status": "not_ready", "reason": "storage_unavailable"}

    database_ok, database_reason = database_status(settings)
    database_check: dict[str, object] = {"status": "ok" if database_ok else "not_ready"}
    if database_reason:
        database_check["reason"] = database_reason

    is_ready = storage_check["status"] == "ok" and database_ok
    body = {
        "status": "ready" if is_ready else "not_ready",
        "checks": {"storage": storage_check, "database": database_check},
        "checked_at": checked_at,
    }
    if not is_ready:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body)
    return body
