"""Authenticated read-only Raspberry Pi system routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.modules.identity.dependencies import AuthContext, get_auth_context
from app.modules.system.schemas import SystemOverviewResponse
from app.modules.system.service import SystemService

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/overview", response_model=SystemOverviewResponse)
def overview(
    _: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> SystemOverviewResponse:
    """Return bounded read-only telemetry for the configured Nexus host."""
    return SystemService(settings.data_dir).collect()
