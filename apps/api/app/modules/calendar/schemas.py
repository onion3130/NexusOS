"""Public schemas for calendar events, categories, and reminders."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

ReminderStatus = str


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone offset")
    return value.astimezone(UTC)


class CategoryCreate(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()


class CategoryResponse(BaseModel):
    id: str
    name: str
    color: str | None


class EventReminderInput(BaseModel):
    model_config = {"extra": "forbid"}
    """One absolute or event-relative reminder."""

    scheduled_for: datetime | None = None
    offset_minutes: int | None = Field(default=None, ge=0, le=525600)

    @field_validator("scheduled_for")
    @classmethod
    def normalize_schedule(cls, value: datetime | None) -> datetime | None:
        return _utc(value)

    @model_validator(mode="after")
    def validate_one_schedule(self) -> "EventReminderInput":
        if (self.scheduled_for is None) == (self.offset_minutes is None):
            raise ValueError("provide exactly one of scheduled_for or offset_minutes")
        return self


class EventCreate(BaseModel):
    model_config = {"extra": "forbid"}
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=255)
    starts_at: datetime
    ends_at: datetime
    all_day: bool = False
    category: str | None = Field(default=None, max_length=64)
    reminders: list[EventReminderInput] = Field(default_factory=list, max_length=8)

    @field_validator("title", "description", "location", "category")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetimes(cls, value: datetime) -> datetime:
        return _utc(value)  # type: ignore[return-value]

    @model_validator(mode="after")
    def validate_time_range(self) -> "EventCreate":
        if self.ends_at < self.starts_at:
            raise ValueError("ends_at must not be before starts_at")
        return self


class EventUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=255)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool | None = None
    category: str | None = Field(default=None, max_length=64)

    @field_validator("title", "description", "location", "category")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetimes(cls, value: datetime | None) -> datetime | None:
        return _utc(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> "EventUpdate":
        if self.starts_at is not None and self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("ends_at must not be before starts_at")
        return self


class EventReminderResponse(BaseModel):
    id: str
    scheduled_for: datetime
    offset_minutes: int | None
    status: str
    delivered_at: datetime | None


class EventResponse(BaseModel):
    id: str
    title: str
    description: str | None
    location: str | None
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    category: CategoryResponse | None
    created_at: datetime
    updated_at: datetime
    reminders: list[EventReminderResponse]


class EventListResponse(BaseModel):
    items: list[EventResponse]
    next_cursor: str | None = None
