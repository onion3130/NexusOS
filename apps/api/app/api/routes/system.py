"""Authenticated read-only Raspberry Pi system routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as OrmSession

from app.core.runtime_config import RuntimeNimConfig, delete_runtime_nim, write_runtime_nim

from app.core.config import Settings, get_settings
from app.modules.identity.dependencies import AuthContext, get_auth_context
from app.modules.identity.dependencies import require_permission
from app.db.session import get_db
from app.modules.system.admin import collect_admin_status
from app.modules.system.schemas import AdminStatusResponse, AssistantProviderStatus, NimSetupRequest, SystemOverviewResponse
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


@router.post("/admin/nvidia-nim", response_model=AdminStatusResponse)
def configure_nvidia_nim(
    payload: NimSetupRequest,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
    db: OrmSession = Depends(get_db),
) -> AdminStatusResponse:
    """Encrypt browser-provided NIM settings on the server and reload configuration."""
    from app.modules.identity.dependencies import require_csrf
    from app.modules.identity.service import add_audit_event
    require_csrf(request, context)
    require_permission("admin.manage_users", context)
    try:
        config = RuntimeNimConfig(api_key=payload.api_key, model=payload.model, embeddings_enabled=payload.embeddings_enabled, embedding_model=payload.embedding_model)
        if config.embeddings_enabled and not config.embedding_model:
            raise ValueError("embedding_model is required when embeddings are enabled")
        write_runtime_nim(settings.data_dir, settings.jwt_secret.get_secret_value(), config)
        add_audit_event(db, action="system.nvidia_nim_configure", result="success", actor_user_id=context.user.id)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="nvidia_nim_storage_unavailable") from exc
    get_settings.cache_clear()
    refreshed = get_settings()
    return collect_admin_status(refreshed)


@router.delete("/admin/nvidia-nim", response_model=AdminStatusResponse)
def disable_nvidia_nim(
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
    db: OrmSession = Depends(get_db),
) -> AdminStatusResponse:
    """Disable browser-managed NIM without changing environment configuration."""
    from app.modules.identity.dependencies import require_csrf
    require_csrf(request, context)
    require_permission("admin.manage_users", context)
    delete_runtime_nim(settings.data_dir)
    from app.modules.identity.service import add_audit_event
    add_audit_event(db, action="system.nvidia_nim_disable", result="success", actor_user_id=context.user.id)
    db.commit()
    get_settings.cache_clear()
    return collect_admin_status(get_settings())


@router.get("/admin/status", response_model=AdminStatusResponse)
def admin_status(
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> AdminStatusResponse:
    """Return redacted system/provider/storage status for authorized owners."""
    require_permission("admin.manage_users", context)
    return collect_admin_status(settings)
