"""Authenticated out-of-process plugin routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as OrmSession

from app.db.models import Plugin
from app.db.session import get_db
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_csrf, require_permission
from app.modules.plugins.schemas import PluginInvokeRequest, PluginManifest, PluginResponse, PluginRunResponse
from app.modules.plugins.service import get_plugin, list_plugin_runs, list_plugins, plugin_run_count

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])



def _plugin_response(item: Plugin, db: OrmSession) -> PluginResponse:
    try:
        manifest = PluginManifest.model_validate_json(item.manifest_json)
    except Exception:
        manifest = None
    capabilities = [{"method": c.method, "description": c.description, "risk": c.risk} for c in manifest.capabilities] if manifest else []
    description = manifest.description if manifest else ""
    return PluginResponse(id=item.id, name=item.name, version=item.version, description=description, entrypoint=item.entrypoint, capabilities=capabilities, status=item.status, last_error_code=item.last_error_code, updated_at=item.updated_at, run_count=plugin_run_count(db, item.id))


def _run_response(run) -> PluginRunResponse:
    return PluginRunResponse(id=run.id, plugin_id=run.plugin_id, method=run.method, status=run.status, error_code=run.error_code, duration_ms=run.duration_ms, created_at=run.created_at)


@router.get("", response_model=list[PluginResponse])
def plugins(db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[PluginResponse]:
    require_permission("plugins.read", context)
    return [_plugin_response(item, db) for item in list_plugins(db)]


@router.get("/{name}", response_model=PluginResponse)
def plugin(name: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> PluginResponse:
    require_permission("plugins.read", context)
    item = get_plugin(db, name)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    return _plugin_response(item, db)


@router.get("/{name}/runs", response_model=list[PluginRunResponse])
def runs(name: str, limit: int = 20, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[PluginRunResponse]:
    require_permission("plugins.read", context)
    item = get_plugin(db, name)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    return [_run_response(run) for run in list_plugin_runs(db, item.id, limit=limit)]


@router.post("/{name}/invoke", response_model=dict[str, object])
def invoke(name: str, payload: PluginInvokeRequest, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> dict[str, object]:
    """Reject direct execution; every plugin call must use assistant confirmation."""
    require_csrf(request, context)
    require_permission("plugins.write", context)
    raise HTTPException(status_code=422, detail="requires_assistant_confirmation")
