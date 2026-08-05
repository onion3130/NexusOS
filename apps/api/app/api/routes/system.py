"""Authenticated read-only Raspberry Pi system routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as OrmSession

from app.core.runtime_config import delete_runtime_nim, mark_runtime_nim_active, write_runtime_nim

from app.core.config import Settings, get_settings
from app.modules.identity.dependencies import AuthContext, get_auth_context
from app.modules.identity.dependencies import require_permission
from app.db.session import get_db
from app.modules.system.admin import collect_admin_status
from app.modules.system.nim_setup import list_nvidia_models, nim_options, resolve_runtime_config, test_nim_connection
from app.modules.system.schemas import (
    AdminStatusResponse,
    AssistantProviderStatus,
    NimModelCatalogResponse,
    NimModelListRequest,
    NimOptionsResponse,
    NimSetupRequest,
    NimTestRequest,
    NimTestResponse,
    SoftwareUpdateRequest,
    SoftwareUpdateStatusResponse,
    SystemOverviewResponse,
)
from app.modules.system.service import SystemService
from app.modules.system.software_update import read_software_update_status, request_software_update

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/overview", response_model=SystemOverviewResponse)
def overview(
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> SystemOverviewResponse:
    """Return bounded read-only telemetry for the configured Nexus host."""
    require_permission("system.read_overview", context)
    return SystemService.from_settings(settings).collect()


@router.get("/assistant/provider", response_model=AssistantProviderStatus)
def assistant_provider(
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> AssistantProviderStatus:
    """Return the configured assistant provider without exposing credentials."""
    require_permission("assistant.task_actions", context)
    from app.modules.system.admin import assistant_provider_status
    return assistant_provider_status(settings)


@router.get("/admin/nvidia-nim/options", response_model=NimOptionsResponse)
def nvidia_nim_options(context: AuthContext = Depends(get_auth_context)) -> NimOptionsResponse:
    """Return beginner-friendly model presets and setup guidance."""
    require_permission("admin.manage_users", context)
    return nim_options()


@router.post("/admin/nvidia-nim/models", response_model=NimModelCatalogResponse)
async def nvidia_nim_models(
    payload: NimModelListRequest,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> NimModelCatalogResponse:
    """List live NVIDIA hosted models via the OpenAI-compatible /v1/models endpoint."""
    from app.modules.identity.dependencies import require_csrf
    require_csrf(request, context)
    require_permission("admin.manage_users", context)
    try:
        return await list_nvidia_models(settings, api_key=payload.api_key)
    except ValueError as exc:
        code = str(exc)
        detail = {
            "api_key_required": "Add an NVIDIA API key to load models.",
            "nvidia_models_timeout": "NVIDIA model list timed out. Check outbound internet access from the Pi.",
            "nvidia_models_unavailable": "NVIDIA model list is unavailable. Check the API key and network access.",
            "nvidia_models_invalid": "NVIDIA returned an unexpected model list payload.",
            "nvidia_models_empty": "NVIDIA returned no usable models for this key.",
        }.get(code, code)
        raise HTTPException(status_code=422, detail=detail) from exc


@router.post("/admin/nvidia-nim/test", response_model=NimTestResponse)
async def test_nvidia_nim(
    payload: NimTestRequest,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> NimTestResponse:
    """Run one bounded hosted-NIM request without returning credentials."""
    from app.modules.identity.dependencies import require_csrf
    require_csrf(request, context)
    require_permission("admin.manage_users", context)
    result = await test_nim_connection(settings, api_key=payload.api_key, model=payload.model)
    return NimTestResponse(ok=result.ok, detail=result.detail, model=result.model, embeddings_tested=result.embeddings_tested)


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
        config = resolve_runtime_config(
            settings,
            api_key=payload.api_key,
            model=payload.model,
            embeddings_enabled=payload.embeddings_enabled,
            embedding_model=payload.embedding_model,
        )
        write_runtime_nim(settings.data_dir, settings.jwt_secret.get_secret_value(), config)
        mark_runtime_nim_active(settings.data_dir)
        add_audit_event(db, action="system.nvidia_nim_configure", result="success", actor_user_id=context.user.id, metadata={"model": config.model, "embeddings_enabled": config.embeddings_enabled})
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


@router.get("/admin/update", response_model=SoftwareUpdateStatusResponse)
def software_update_status(
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> SoftwareUpdateStatusResponse:
    """Return redacted software-update status for the host update agent handshake."""
    require_permission("admin.manage_users", context)
    return SoftwareUpdateStatusResponse.model_validate(read_software_update_status(settings).model_dump())


@router.post("/admin/update", response_model=SoftwareUpdateStatusResponse)
def software_update_request(
    payload: SoftwareUpdateRequest,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
    db: OrmSession = Depends(get_db),
) -> SoftwareUpdateStatusResponse:
    """Queue a fixed host-side check or apply update without executing shell in-process."""
    from app.modules.identity.dependencies import require_csrf
    from app.modules.identity.service import add_audit_event
    require_csrf(request, context)
    require_permission("admin.manage_users", context)
    try:
        status = request_software_update(settings, user_id=context.user.id, action=payload.action, confirm=payload.confirm)
    except ValueError as exc:
        code = str(exc)
        if code == "confirm_required":
            raise HTTPException(status_code=422, detail="confirm_required") from exc
        if code == "update_busy":
            raise HTTPException(status_code=409, detail="update_busy") from exc
        raise HTTPException(status_code=422, detail=code) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="update_storage_unavailable") from exc
    add_audit_event(
        db,
        action="system.software_update_request",
        result="success",
        actor_user_id=context.user.id,
        target=status.request_id,
        metadata={"action": payload.action},
    )
    db.commit()
    return SoftwareUpdateStatusResponse.model_validate(status.model_dump())
