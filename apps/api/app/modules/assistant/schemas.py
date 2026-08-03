"""Typed schemas for the Milestone 5 assistant gateway."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic.fields import FieldInfo

MessageRole = Literal["user", "assistant", "tool"]
ModelRunStatus = Literal["started", "succeeded", "failed", "disabled"]
ToolCallStatus = Literal["proposed", "validated", "processing", "executed", "rejected", "failed"]


class ConversationCreate(BaseModel):
    """Validated conversation creation input."""

    title: str | None = Field(default=None, max_length=120)


class ConversationSummary(BaseModel):
    """Conversation metadata safe for the browser."""

    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int


class MessageResponse(BaseModel):
    """A persisted conversation message."""

    id: str
    role: MessageRole
    content: str
    sequence: int
    created_at: datetime


class ToolCallResponse(BaseModel):
    """Sanitized tool execution or confirmation metadata."""

    id: str
    tool_key: str
    status: ToolCallStatus
    error_code: str | None = None
    requires_confirmation: bool = False
    arguments: dict[str, object] = Field(default_factory=dict)


class ModelRunResponse(BaseModel):
    """Safe model-run metadata without provider payloads or secrets."""

    id: str
    provider: str
    model: str | None
    status: ModelRunStatus
    latency_ms: int | None = None
    error_code: str | None = None


class ConversationResponse(ConversationSummary):
    """Conversation metadata plus ordered messages."""

    messages: list[MessageResponse]


class SendMessageRequest(BaseModel):
    """Bounded user message input."""

    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        """Reject blank messages and persist only trimmed content."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank")
        return normalized


class SendMessageResponse(BaseModel):
    """Result of one bounded assistant request."""

    user_message: MessageResponse
    assistant_message: MessageResponse
    model_run: ModelRunResponse
    tool_calls: list[ToolCallResponse] = Field(default_factory=list)


class GatewayMessage(BaseModel):
    """Provider-neutral message input, including tool-call linkage."""

    role: MessageRole
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict[str, object]] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    """Provider-neutral, server-owned tool definition."""

    key: str
    description: str
    parameters: dict[str, object]


class ProposedToolCall(BaseModel):
    model_config = {"extra": "forbid"}
    """A provider-proposed call before registry validation."""

    provider_id: str
    tool_key: str
    arguments: dict[str, object]


class GatewayCompletion(BaseModel):
    """Normalized provider completion."""

    content: str
    tool_calls: list[ProposedToolCall] = Field(default_factory=list)
    provider: str
    model: str | None
    input_tokens: int | None = None
    output_tokens: int | None = None


class AssistantError(Exception):
    """Base class for safe assistant failures."""

    code = "assistant_unavailable"
    status_code = 503


class ProviderDisabledError(AssistantError):
    """Raised when AI is intentionally disabled by configuration."""

    code = "ai_provider_disabled"


class ProviderTimeoutError(AssistantError):
    """Raised when the upstream provider exceeds the bounded timeout."""

    code = "ai_provider_timeout"
    status_code = 504


class ProviderRequestError(AssistantError):
    """Raised for normalized provider/network failures."""

    code = "ai_provider_unavailable"


class ToolValidationError(AssistantError):
    """Raised when a provider proposes an unsupported tool call."""

    code = "ai_tool_not_allowed"
    status_code = 422
