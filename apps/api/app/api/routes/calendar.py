"""Authenticated calendar routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session as OrmSession

from app.db.models import CalendarCategory, CalendarEvent
from app.db.session import get_db
from app.modules.calendar.schemas import CategoryCreate, CategoryResponse, EventCreate, EventListResponse, EventReminderInput, EventReminderResponse, EventResponse, EventUpdate
from app.modules.calendar.service import add_reminder, create_category, create_event, delete_category, delete_event, delete_reminder, get_event, list_categories, list_events, update_event, update_reminder
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_csrf, require_permission

router = APIRouter(prefix="/api/v1", tags=["calendar"])


def _category_response(item: CalendarCategory) -> CategoryResponse:
    return CategoryResponse(id=item.id, name=item.name, color=item.color)


def _event_response(event: CalendarEvent) -> EventResponse:
    return EventResponse(id=event.id, title=event.title, description=event.description, location=event.location, starts_at=event.starts_at, ends_at=event.ends_at, all_day=event.all_day, category=_category_response(event.category) if event.category else None, created_at=event.created_at, updated_at=event.updated_at, reminders=[EventReminderResponse(id=item.id, scheduled_for=item.scheduled_for, offset_minutes=item.offset_minutes, status=item.status, delivered_at=item.delivered_at) for item in event.reminders])


def _parse_from(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="from must be an ISO-8601 timestamp") from exc
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@router.get("/calendar/events", response_model=EventListResponse)
def list_all(start_from: str | None = Query(default=None, alias="from"), start_to: str | None = Query(default=None, alias="to"), category: str | None = None, limit: int = 100, cursor: str | None = None, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> EventListResponse:
    require_permission("calendar.read", context)
    items = list_events(db, context.user.id, start_from=_parse_from(start_from), start_to=_parse_from(start_to), category=category, limit=limit, cursor=cursor)
    return EventListResponse(items=[_event_response(item) for item in items], next_cursor=items[-1].id if len(items) == min(max(limit, 1), 200) else None)


@router.post("/calendar/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create(payload: EventCreate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> EventResponse:
    require_csrf(request, context)
    require_permission("calendar.write", context)
    try:
        return _event_response(create_event(db, context.user.id, payload, request.headers.get("Idempotency-Key")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/calendar/events/{event_id}", response_model=EventResponse)
def get_one(event_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> EventResponse:
    require_permission("calendar.read", context)
    event = get_event(db, context.user.id, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return _event_response(event)


@router.patch("/calendar/events/{event_id}", response_model=EventResponse)
def update(event_id: str, payload: EventUpdate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> EventResponse:
    require_csrf(request, context)
    require_permission("calendar.write", context)
    try:
        event = update_event(db, context.user.id, event_id, payload, request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return _event_response(event)


@router.delete("/calendar/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(event_id: str, request: Request, response: Response, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("calendar.write", context)
    if delete_event(db, context.user.id, event_id, request.headers.get("Idempotency-Key")) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")


@router.post("/calendar/events/{event_id}/reminders", response_model=EventResponse)
def add_event_reminder(event_id: str, payload: EventReminderInput, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> EventResponse:
    require_csrf(request, context)
    require_permission("calendar.write", context)
    try:
        event = add_reminder(db, context.user.id, event_id, payload, request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return _event_response(event)


@router.patch("/calendar/reminders/{reminder_id}", response_model=EventResponse)
def update_event_reminder(reminder_id: str, payload: EventReminderInput, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> EventResponse:
    require_csrf(request, context)
    require_permission("calendar.write", context)
    try:
        event = update_reminder(db, context.user.id, reminder_id, payload, request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return _event_response(event)


@router.delete("/calendar/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_reminder(reminder_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("calendar.write", context)
    if not delete_reminder(db, context.user.id, reminder_id, request.headers.get("Idempotency-Key")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")


@router.get("/calendar/categories", response_model=list[CategoryResponse])
def categories(db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[CategoryResponse]:
    require_permission("calendar.read", context)
    return [_category_response(item) for item in list_categories(db, context.user.id)]


@router.post("/calendar/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def category_create(payload: CategoryCreate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> CategoryResponse:
    require_csrf(request, context)
    require_permission("calendar.write", context)
    try:
        return _category_response(create_category(db, context.user.id, payload, request.headers.get("Idempotency-Key")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/calendar/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def category_delete(category_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("calendar.write", context)
    if not delete_category(db, context.user.id, category_id, request.headers.get("Idempotency-Key")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
