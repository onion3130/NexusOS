"""Public schemas for notification channel settings and delivery status."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ChannelDeliveryResponse(BaseModel):
    """One channel's bounded delivery state for a persisted notification."""

    channel: str
    status: str
    delivered_at: datetime | None
    error_code: str | None


class NotificationSettingsResponse(BaseModel):
    """Redacted channel configuration; secret values are never returned."""

    email_enabled: bool
    email_configured: bool
    email_smtp_host: str | None
    email_smtp_user: str | None
    email_from: str | None
    email_to: str | None
    email_credentials_set: bool
    push_enabled: bool
    push_configured: bool
    push_url: str | None
    push_topic: str | None
    push_token_set: bool


class TestSendResult(BaseModel):
    """One channel's synchronous test-send outcome."""

    channel: str
    ok: bool
    error_code: str | None = None
