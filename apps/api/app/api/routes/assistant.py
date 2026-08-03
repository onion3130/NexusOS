"""Authenticated assistant gateway routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.assistant.gateway import gateway_from_settings
from app.modules.assistant.schemas import AssistantError, ConversationCreate, ConversationResponse, ConversationSummary, SendMessageRequest, SendMessageResponse
from app.modules.assistant.service import approve_tool_call, conversation_response, create_conversation, get_conversation, list_conversations, reject_tool_call, send_message
from app.modules.assistant.tools.registry import ToolRegistry
from app.modules.workspace_views.service import WorkspaceViewService
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_csrf, require_permission
from app.modules.identity.service import permission_names
from app.modules.system.service import SystemService

router = APIRouter(prefix="/api/v1/conversations", tags=["assistant"])
approval_router = APIRouter(prefix="/api/v1/ai", tags=["assistant"])


def _owned_or_404(db: OrmSession, context: AuthContext, conversation_id: str):
    """Resolve a conversation only within the current user's ownership boundary."""
    conversation = get_conversation(db, context.user.id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.post("", response_model=ConversationSummary, status_code=status.HTTP_201_CREATED)
def create(payload: ConversationCreate, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> ConversationSummary:
    """Create an authenticated user's conversation."""
    return create_conversation(db, context.user.id, payload)


@router.get("", response_model=list[ConversationSummary])
def list_all(db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[ConversationSummary]:
    """List the authenticated user's conversations."""
    return list_conversations(db, context.user.id)


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_one(conversation_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> ConversationResponse:
    """Read one owned conversation and its ordered messages."""
    return conversation_response(db, _owned_or_404(db, context, conversation_id))


@router.post("/{conversation_id}/messages", response_model=SendMessageResponse)
async def message(conversation_id: str, payload: SendMessageRequest, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context), settings: Settings = Depends(get_settings)) -> SendMessageResponse:
    """Send one bounded message through the configured assistant gateway."""
    conversation = _owned_or_404(db, context, conversation_id)
    try:
        return await send_message(db, settings, conversation, payload.content, gateway_from_settings(settings), ToolRegistry(SystemService(settings.data_dir), db, context.user.id, WorkspaceViewService(settings)), set(permission_names(context.user)))
    except AssistantError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="assistant_unavailable") from exc


@approval_router.post("/tool-calls/{tool_call_id}/approve")
def approve(tool_call_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context), settings: Settings = Depends(get_settings)):
    """Approve one owned, unexpired assistant task mutation."""
    require_csrf(request, context)
    require_permission("assistant.task_actions", context)
    try:
        tool_call, result = approve_tool_call(db, context.user.id, tool_call_id, set(permission_names(context.user)), ToolRegistry(SystemService(settings.data_dir), db, context.user.id, WorkspaceViewService(settings)), request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if tool_call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool call not found")
    if result is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tool call is expired or unavailable")
    return {"tool_call_id": tool_call.id, "status": tool_call.status, "result": result}


@approval_router.post("/tool-calls/{tool_call_id}/reject")
def reject(tool_call_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)):
    """Reject one owned assistant task mutation without executing it."""
    require_csrf(request, context)
    require_permission("assistant.task_actions", context)
    try:
        tool_call = reject_tool_call(db, context.user.id, tool_call_id, request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if tool_call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool call not found")
    return {"tool_call_id": tool_call.id, "status": tool_call.status}
