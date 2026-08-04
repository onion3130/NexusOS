"""Public schemas for finance accounts, categories, and transactions."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

ACCOUNT_TYPES = ("checking", "savings", "cash", "credit", "investment")


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone offset")
    return value.astimezone(UTC)


class AccountCreate(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=64)
    account_type: str = Field(default="checking", max_length=24)
    color: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("account_type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value not in ACCOUNT_TYPES:
            raise ValueError(f"account_type must be one of {', '.join(ACCOUNT_TYPES)}")
        return value


class AccountUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, min_length=1, max_length=64)
    account_type: str | None = Field(default=None, max_length=24)
    color: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("account_type")
    @classmethod
    def validate_type(cls, value: str | None) -> str | None:
        if value is not None and value not in ACCOUNT_TYPES:
            raise ValueError(f"account_type must be one of {', '.join(ACCOUNT_TYPES)}")
        return value


class AccountResponse(BaseModel):
    id: str
    name: str
    account_type: str
    color: str | None
    balance_cents: int = 0
    created_at: datetime
    updated_at: datetime


class FinanceCategoryCreate(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()


class FinanceCategoryResponse(BaseModel):
    id: str
    name: str
    color: str | None


class TransactionCreate(BaseModel):
    model_config = {"extra": "forbid"}
    account_id: str = Field(min_length=1, max_length=36)
    amount_cents: int
    description: str = Field(min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=4000)
    category: str | None = Field(default=None, max_length=64)
    occurred_at: datetime | None = None

    @field_validator("description", "note", "category")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("occurred_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return _utc(value)


class TransactionUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    account_id: str | None = Field(default=None, min_length=1, max_length=36)
    amount_cents: int | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=4000)
    category: str | None = Field(default=None, max_length=64)
    occurred_at: datetime | None = None

    @field_validator("description", "note", "category")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("occurred_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return _utc(value)


class TransactionResponse(BaseModel):
    id: str
    account_id: str
    amount_cents: int
    description: str
    note: str | None
    category: FinanceCategoryResponse | None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    next_cursor: str | None = None


class TransactionSummary(BaseModel):
    total_income_cents: int
    total_expense_cents: int
    net_cents: int
    count: int


class CsvImportRequest(BaseModel):
    model_config = {"extra": "forbid"}
    account_id: str = Field(min_length=1, max_length=36)
    csv: str = Field(min_length=1, max_length=1_000_000)


class CsvImportRowError(BaseModel):
    row: int
    error: str


class CsvImportResponse(BaseModel):
    imported: int
    errors: list[CsvImportRowError] = Field(default_factory=list)
