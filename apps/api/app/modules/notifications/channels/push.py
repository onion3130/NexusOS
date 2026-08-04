"""Outbound ntfy-compatible push channel for notification delivery."""

from __future__ import annotations

import httpx

from app.core.config import Settings

PUSH_TIMEOUT_SECONDS = 10.0


class PushDeliveryError(ValueError):
    """Raised when a push notification cannot be delivered."""


def send_push(settings: Settings, *, title: str, body: str) -> None:
    """POST one bounded push message to the configured ntfy-compatible endpoint."""
    url = settings.notification_push_url
    topic = settings.notification_push_topic
    if not url or not topic:
        raise PushDeliveryError("push_channel_not_configured")
    endpoint = f"{url.rstrip('/')}/{topic}"
    headers = {"Content-Type": "application/json"}
    token = settings.notification_push_token
    if token and token.get_secret_value():
        headers["Authorization"] = f"Bearer {token.get_secret_value()}"
    try:
        # Redirects are not followed: the configured endpoint is the only
        # permitted outbound target, so a 3xx must not redirect the worker to
        # an internal or loopback address the URL validator never saw.
        with httpx.Client(timeout=PUSH_TIMEOUT_SECONDS, follow_redirects=False) as client:
            response = client.post(
                endpoint,
                json={"topic": topic, "title": title[:120], "message": body[:2000]},
                headers=headers,
            )
        if response.status_code not in {200, 201}:
            raise PushDeliveryError("push_rejected")
    except PushDeliveryError:
        raise
    except httpx.HTTPError as exc:
        raise PushDeliveryError("push_network_failed") from exc
