"""Health endpoints for process and dependency readiness."""

from __future__ import annotations

import shutil
import tempfile
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app import __version__
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/live", summary="Process liveness")
def live() -> dict[str, str]:
    """Report that the API process is alive without checking dependencies."""
    return {"status": "ok", "service": "nexus-api", "version": __version__}


@router.get("/ready", summary="Dependency readiness", response_model=None)
def ready(settings: Settings = Depends(get_settings)) -> JSONResponse | dict:
    """Report readiness of the configured storage boundary.

    Database checks are intentionally deferred until the persistence milestone.
    The response shape remains compatible with the architecture contract.
    """
    data_dir = settings.data_dir
    checked_at = datetime.now(UTC).isoformat()

    if not data_dir.is_dir():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "checks": {"storage": {"status": "not_ready", "reason": "data_dir_missing"}},
                "checked_at": checked_at,
            },
        )

    try:
        free_bytes = shutil.disk_usage(data_dir).free
        with tempfile.NamedTemporaryFile(dir=data_dir, prefix=".nexus-ready-", delete=True):
            pass
    except OSError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "checks": {"storage": {"status": "not_ready", "reason": "storage_unavailable"}},
                "checked_at": checked_at,
            },
        )

    return {
        "status": "ready",
        "checks": {"storage": {"status": "ok", "free_bytes": free_bytes}},
        "checked_at": checked_at,
    }
