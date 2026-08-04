"""Authenticated read-only Raspberry Pi system routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.modules.identity.dependencies import AuthContext, get_auth_context
from app.modules.identity.dependencies import require_permission
from app.modules.system.admin import collect_admin_status
from app.modules.system.schemas import AdminStatusResponse, AssistantProviderStatus, SystemOverviewResponse
from app.modules.system.service import SystemService

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/overview", response_model=SystemOverviewResponse)
def overview(
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> SystemOverviewResponse:
    """Return bounded read-only telemetry for the configured Nexus host."""
    require_permission("system.read_overview", context)
    return SystemService(settings.data_dir).collect()


@router.get("/assistant/provider", response_model=AssistantProviderStatus)
def assistant_provider(
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> AssistantProviderStatus:
    """Return the configured assistant provider without exposing credentials."""
    require_permission("assistant.task_actions", context)
    from app.modules.system.admin import assistant_provider_status
    return assistant_provider_status(settings)


@router.get("/admin/status", response_model=AdminStatusResponse)
def admin_status(
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> AdminStatusResponse:
    """Return redacted system/provider/storage status for authorized owners."""
    require_permission("admin.manage_users", context)
    return collect_admin_status(settings)
