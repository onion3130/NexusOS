"""Public schemas for task management and in-app notifications."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.notifications.schemas import ChannelDeliveryResponse

TaskStatus = Literal["open", "in_progress", "completed", "archived"]
TaskPriority = Literal["low", "normal", "high", "urgent"]
ReminderStatus = Literal["pending", "processing", "delivered", "cancelled", "failed"]


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone offset")
    return value.astimezone(UTC)


class ReminderInput(BaseModel):
    model_config = {"extra": "forbid"}
    """One absolute or due-date-relative reminder."""

    scheduled_for: datetime | None = None
    offset_minutes: int | None = Field(default=None, ge=0, le=525600)

    @field_validator("scheduled_for")
    @classmethod
    def normalize_schedule(cls, value: datetime | None) -> datetime | None:
        return _utc(value)

    @model_validator(mode="after")
    def validate_one_schedule(self) -> "ReminderInput":
        if (self.scheduled_for is None) == (self.offset_minutes is None):
            raise ValueError("provide exactly one of scheduled_for or offset_minutes")
        return self


class TaskCreate(BaseModel):
    model_config = {"extra": "forbid"}
    """Create a task occurrence or recurring task series."""

    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    due_at: datetime | None = None
    priority: TaskPriority = "normal"
    status: TaskStatus = "open"
    category: str | None = Field(default=None, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=20)
    recurrence: dict[str, object] | None = None
    reminders: list[ReminderInput] = Field(default_factory=list, max_length=8)

    @field_validator("title", "description", "category")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("due_at")
    @classmethod
    def normalize_due_at(cls, value: datetime | None) -> datetime | None:
        return _utc(value)

    @field_validator("status")
    @classmethod
    def prevent_completed_create(cls, value: TaskStatus) -> TaskStatus:
        if value == "completed":
            raise ValueError("new tasks must start open or in_progress")
        return value

    @model_validator(mode="after")
    def validate_recurrence(self) -> "TaskCreate":
        if self.recurrence is not None:
            from app.modules.tasks.recurrence import validate_rule
            validate_rule(self.recurrence)
        return self

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        normalized = [value.strip()[:64] for value in values if value.strip()]
        if len(set(value.casefold() for value in normalized)) != len(normalized):
            raise ValueError("tags must be unique")
        return normalized


class TaskUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    """Partial task mutation payload."""

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    due_at: datetime | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    category: str | None = Field(default=None, max_length=64)
    tags: list[str] | None = Field(default=None, max_length=20)
    recurrence: dict[str, object] | None = None

    @field_validator("title", "description", "category")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("due_at")
    @classmethod
    def normalize_due_at(cls, value: datetime | None) -> datetime | None:
        return _utc(value)

    @field_validator("status")
    @classmethod
    def prevent_direct_completion(cls, value: TaskStatus | None) -> TaskStatus | None:
        if value == "completed":
            raise ValueError("use the complete task action")
        return value

    @model_validator(mode="after")
    def validate_recurrence(self) -> "TaskUpdate":
        if self.recurrence is not None:
            from app.modules.tasks.recurrence import validate_rule
            validate_rule(self.recurrence)
        return self

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = [value.strip()[:64] for value in values if value.strip()]
        if len(set(value.casefold() for value in normalized)) != len(normalized):
            raise ValueError("tags must be unique")
        return normalized


class CategoryResponse(BaseModel):
    id: str
    name: str
    color: str | None


class TagResponse(BaseModel):
    id: str
    name: str


class ReminderUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    scheduled_for: datetime | None = None
    offset_minutes: int | None = Field(default=None, ge=0, le=525600)

    @field_validator("scheduled_for")
    @classmethod
    def normalize_schedule(cls, value: datetime | None) -> datetime | None:
        return _utc(value)

    @model_validator(mode="after")
    def validate_one_schedule(self) -> "ReminderUpdate":
        if (self.scheduled_for is None) == (self.offset_minutes is None):
            raise ValueError("provide exactly one of scheduled_for or offset_minutes")
        return self


class ReminderResponse(BaseModel):
    id: str
    scheduled_for: datetime
    offset_minutes: int | None
    status: ReminderStatus
    delivered_at: datetime | None


class TaskResponse(BaseModel):
    id: str
    series_id: str | None
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    category: CategoryResponse | None
    tags: list[TagResponse]
    recurrence: dict[str, object] | None
    reminders: list[ReminderResponse]


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    next_cursor: str | None = None


class CategoryCreate(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()


class TagCreate(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()


class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    body: str
    task_id: str | None
    created_at: datetime
    read_at: datetime | None
    channels: list[ChannelDeliveryResponse] = []


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int
    next_cursor: str | None = None


class ApprovalResponse(BaseModel):
    tool_call_id: str
    status: str
    task: TaskResponse | None = None
