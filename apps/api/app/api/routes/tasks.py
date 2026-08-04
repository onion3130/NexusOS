"""Authenticated task-management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session as OrmSession

from app.db.models import Task, TaskCategory, Tag
from app.db.session import get_db
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_csrf, require_permission
from app.modules.tasks.schemas import CategoryCreate, CategoryResponse, NotificationListResponse, NotificationResponse, ReminderInput, ReminderResponse, ReminderUpdate, TagCreate, TagResponse, TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from app.modules.tasks.service import add_reminder, complete_task, create_category, create_tag, create_task, delete_category, delete_tag, delete_reminder, delete_task, get_task, list_categories, list_notifications, list_tags, list_tasks, mark_all_notifications_read, mark_notification_read, update_reminder, update_task
from app.modules.notifications.service import delivery_responses

router = APIRouter(prefix="/api/v1", tags=["tasks"])


def _task_response(task: Task) -> TaskResponse:
    return TaskResponse(id=task.id, series_id=task.series_id, title=task.title, description=task.description, status=task.status, priority=task.priority, due_at=task.due_at, completed_at=task.completed_at, created_at=task.created_at, updated_at=task.updated_at, category=CategoryResponse(id=task.category.id, name=task.category.name, color=task.category.color) if task.category else None, tags=[TagResponse(id=tag.id, name=tag.name) for tag in task.tags], recurrence=__import__("json").loads(task.series.recurrence_json) if task.series else None, reminders=[ReminderResponse(id=item.id, scheduled_for=item.scheduled_for, offset_minutes=item.offset_minutes, status=item.status, delivered_at=item.delivered_at) for item in task.reminders])


def _category_response(item: TaskCategory) -> CategoryResponse:
    return CategoryResponse(id=item.id, name=item.name, color=item.color)


def _tag_response(item: Tag) -> TagResponse:
    return TagResponse(id=item.id, name=item.name)


@router.get("/tasks", response_model=TaskListResponse)
def list_all(status_filter: str | None = None, priority: str | None = None, category: str | None = None, tag: str | None = None, include_completed: bool = False, limit: int = 50, cursor: str | None = None, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TaskListResponse:
    require_permission("tasks.read", context)
    items = list_tasks(db, context.user.id, status=status_filter, priority=priority, category=category, tag=tag, include_completed=include_completed, limit=limit, cursor=cursor)
    return TaskListResponse(items=[_task_response(item) for item in items], next_cursor=items[-1].id if len(items) == min(max(limit, 1), 100) else None)


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create(payload: TaskCreate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TaskResponse:
    require_csrf(request, context)
    require_permission("tasks.write", context)
    try:
        return _task_response(create_task(db, context.user.id, payload, request.headers.get("Idempotency-Key")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_one(task_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TaskResponse:
    require_permission("tasks.read", context)
    task = get_task(db, context.user.id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _task_response(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update(task_id: str, payload: TaskUpdate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TaskResponse:
    require_csrf(request, context)
    require_permission("tasks.write", context)
    try:
        task = update_task(db, context.user.id, task_id, payload, request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _task_response(task)


@router.post("/tasks/{task_id}/complete", response_model=TaskResponse)
def complete(task_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TaskResponse:
    require_csrf(request, context)
    require_permission("tasks.write", context)
    task, _ = complete_task(db, context.user.id, task_id, request.headers.get("Idempotency-Key"))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _task_response(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(task_id: str, request: Request, response: Response, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("tasks.delete", context)
    if delete_task(db, context.user.id, task_id, request.headers.get("Idempotency-Key")) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")


@router.get("/tasks/{task_id}/reminders", response_model=list[ReminderResponse])
def reminders(task_id: str, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[ReminderResponse]:
    require_permission("tasks.read", context)
    task = get_task(db, context.user.id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return [ReminderResponse(id=item.id, scheduled_for=item.scheduled_for, offset_minutes=item.offset_minutes, status=item.status, delivered_at=item.delivered_at) for item in task.reminders]


@router.post("/tasks/{task_id}/reminders", response_model=TaskResponse)
def add_task_reminder(task_id: str, payload: ReminderInput, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TaskResponse:
    require_csrf(request, context)
    require_permission("tasks.write", context)
    try:
        task = add_reminder(db, context.user.id, task_id, payload, request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _task_response(task)


@router.patch("/reminders/{reminder_id}", response_model=TaskResponse)
def update_task_reminder(reminder_id: str, payload: ReminderUpdate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TaskResponse:
    require_csrf(request, context)
    require_permission("tasks.write", context)
    try:
        task = update_reminder(db, context.user.id, reminder_id, ReminderInput(scheduled_for=payload.scheduled_for, offset_minutes=payload.offset_minutes), request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return _task_response(task)


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_reminder(reminder_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("tasks.write", context)
    if not delete_reminder(db, context.user.id, reminder_id, request.headers.get("Idempotency-Key")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")


@router.get("/task-categories", response_model=list[CategoryResponse])
def categories(db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[CategoryResponse]:
    require_permission("tasks.read", context)
    return [_category_response(item) for item in list_categories(db, context.user.id)]


@router.post("/task-categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def category_create(payload: CategoryCreate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> CategoryResponse:
    require_csrf(request, context)
    require_permission("tasks.write", context)
    try:
        return _category_response(create_category(db, context.user.id, payload, request.headers.get("Idempotency-Key")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category already exists") from exc


@router.delete("/task-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def category_delete(category_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("tasks.write", context)
    if not delete_category(db, context.user.id, category_id, request.headers.get("Idempotency-Key")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")


@router.get("/tags", response_model=list[TagResponse])
def tags(db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[TagResponse]:
    require_permission("tasks.read", context)
    return [_tag_response(item) for item in list_tags(db, context.user.id)]


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def tag_create(payload: TagCreate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TagResponse:
    require_csrf(request, context)
    require_permission("tasks.write", context)
    try:
        return _tag_response(create_tag(db, context.user.id, payload, request.headers.get("Idempotency-Key")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already exists") from exc


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def tag_delete(tag_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("tasks.write", context)
    if not delete_tag(db, context.user.id, tag_id, request.headers.get("Idempotency-Key")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")


@router.get("/notifications", response_model=NotificationListResponse)
def notification_list(unread_only: bool = False, limit: int = 50, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> NotificationListResponse:
    require_permission("notifications.read", context)
    items, count = list_notifications(db, context.user.id, unread_only, limit)
    return NotificationListResponse(items=[NotificationResponse(id=item.id, type=item.type, title=item.title, body=item.body, task_id=item.task_id, created_at=item.created_at, read_at=item.read_at, channels=delivery_responses(item)) for item in items], unread_count=count)


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def notification_read(notification_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("notifications.write", context)
    if not mark_notification_read(db, context.user.id, notification_id, request.headers.get("Idempotency-Key")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
def notification_read_all(request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    """Mark all current-user notifications read."""
    require_csrf(request, context)
    require_permission("notifications.write", context)
    mark_all_notifications_read(db, context.user.id, request.headers.get("Idempotency-Key"))
