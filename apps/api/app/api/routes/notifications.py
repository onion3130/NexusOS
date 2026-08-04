"""Authenticated notification channel settings and delivery routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession, selectinload

from app.core.config import Settings, get_settings
from app.db.models import Notification
from app.db.session import get_db
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_csrf, require_permission
from app.modules.notifications.schemas import NotificationSettingsResponse, TestSendResult
from app.modules.notifications.service import delivery_responses, resend_deliveries, send_test, settings_status
from app.modules.tasks.schemas import NotificationResponse

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _notification_response(item: Notification) -> NotificationResponse:
    return NotificationResponse(id=item.id, type=item.type, title=item.title, body=item.body, task_id=item.task_id, created_at=item.created_at, read_at=item.read_at, channels=delivery_responses(item))


@router.get("/settings", response_model=NotificationSettingsResponse)
def read_settings(settings: Settings = Depends(get_settings), context: AuthContext = Depends(get_auth_context)) -> NotificationSettingsResponse:
    """Expose redacted channel configuration; secrets are never returned."""
    require_permission("notifications.settings", context)
    return settings_status(settings)


@router.post("/settings/test", response_model=list[TestSendResult])
def test_settings(request: Request, db: OrmSession = Depends(get_db), settings: Settings = Depends(get_settings), context: AuthContext = Depends(get_auth_context)) -> list[TestSendResult]:
    """Send one bounded test message through every enabled channel."""
    require_csrf(request, context)
    require_permission("notifications.settings", context)
    return send_test(db, settings, user_id=context.user.id)


@router.post("/{notification_id}/resend", response_model=NotificationResponse)
def resend(notification_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> NotificationResponse:
    """Requeue owned channel deliveries for one notification."""
    require_csrf(request, context)
    require_permission("notifications.write", context)
    notification = resend_deliveries(db, context.user.id, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    loaded = db.scalar(
        select(Notification).options(selectinload(Notification.deliveries)).where(Notification.id == notification.id, Notification.user_id == context.user.id)
    )
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return _notification_response(loaded)
