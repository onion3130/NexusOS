"""Milestone 11 outbound notification channel tests."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Notification, NotificationChannelDelivery, User
from app.db.session import get_session_factory
from app.modules.identity.service import bootstrap_owner
from app.modules.notifications.channels.email import EmailDeliveryError, send_email
from app.modules.notifications.channels.push import PushDeliveryError, send_push
from app.modules.notifications.service import enqueue_deliveries, settings_status
from app.modules.notifications.worker import process_notification_deliveries


def _bootstrap_owner() -> None:
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _login(client) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200


_BASE_SETTINGS = {
    "NEXUS_ENV": "test",
    "TZ": "UTC",
    "DATA_DIR": tempfile.gettempdir(),
    "DB_TYPE": "sqlite",
    "DATABASE_URL": f"sqlite:///{tempfile.gettempdir()}/nexus-settings.db",
    "JWT_SECRET": "test-secret-that-is-longer-than-thirty-two-characters",
    "SESSION_COOKIE_SECURE": "false",
    "CORS_ORIGINS": "http://localhost:3000",
    "AI_PROVIDER": "disabled",
}

_NOTIFICATION_DEFAULTS = {
    "NOTIFICATION_EMAIL_ENABLED": "false",
    "NOTIFICATION_EMAIL_SMTP_HOST": "",
    "NOTIFICATION_EMAIL_SMTP_PORT": "587",
    "NOTIFICATION_EMAIL_SMTP_USER": "",
    "NOTIFICATION_EMAIL_SMTP_PASSWORD": "",
    "NOTIFICATION_EMAIL_FROM": "",
    "NOTIFICATION_EMAIL_TO": "",
    "NOTIFICATION_EMAIL_USE_TLS": "true",
    "NOTIFICATION_PUSH_ENABLED": "false",
    "NOTIFICATION_PUSH_URL": "",
    "NOTIFICATION_PUSH_TOPIC": "",
    "NOTIFICATION_PUSH_TOKEN": "",
    "NOTIFICATION_DELIVERY_BATCH_SIZE": "20",
}


def _settings(monkeypatch: pytest.MonkeyPatch, **overrides):
    """Build fresh runtime settings with deterministic channel configuration."""
    for key, value in _BASE_SETTINGS.items():
        if not os.environ.get(key, "").strip():
            monkeypatch.setenv(key, value)
    for key, value in _NOTIFICATION_DEFAULTS.items():
        monkeypatch.setenv(key, value)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    try:
        return get_settings()
    finally:
        get_settings.cache_clear()


EMAIL_OVERRIDES = {
    "NOTIFICATION_EMAIL_ENABLED": "true",
    "NOTIFICATION_EMAIL_SMTP_HOST": "smtp.example.com",
    "NOTIFICATION_EMAIL_SMTP_PORT": "587",
    "NOTIFICATION_EMAIL_SMTP_USER": "nexus",
    "NOTIFICATION_EMAIL_SMTP_PASSWORD": "secret-pass-123",
    "NOTIFICATION_EMAIL_FROM": "nexus@example.com",
    "NOTIFICATION_EMAIL_TO": "owner@example.com",
}

PUSH_OVERRIDES = {
    "NOTIFICATION_PUSH_ENABLED": "true",
    "NOTIFICATION_PUSH_URL": "https://ntfy.example.com",
    "NOTIFICATION_PUSH_TOPIC": "nexus",
    "NOTIFICATION_PUSH_TOKEN": "tok-secret",
}


class _SuccessSMTP:
    def __init__(self, *args, **kwargs):
        self.sent: list[dict[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        self.sent.append({"login": (user, password)})

    def send_message(self, message):
        self.sent.append({"message": message})


class _FailingSMTP:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        raise OSError("connection refused")


class _PushClient:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.posted: dict[str, object] = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, json=None, headers=None):
        self.posted = {"url": url, "json": json, "headers": headers}
        return type("Response", (), {"status_code": self.status_code})()


def _seed_notification(db, user_id: str, dedupe_key: str = "test:channel") -> Notification:
    notification = Notification(user_id=user_id, type="task_reminder", title="Reminder", body="Body", dedupe_key=dedupe_key)
    db.add(notification)
    db.flush()
    return notification


def test_email_channel_sends_bounded_message(monkeypatch) -> None:
    settings = _settings(monkeypatch, **EMAIL_OVERRIDES)
    smtp = _SuccessSMTP()
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: smtp)
    send_email(settings, to="owner@example.com", subject="A very long subject " + "x" * 300, body="Hello " + "y" * 3000)
    message = smtp.sent[-1]["message"]
    assert message["To"] == "owner@example.com"
    assert message["Subject"] == "A very long subject " + "x" * 100
    assert smtp.sent[0]["login"] == ("nexus", "secret-pass-123")


def test_email_channel_reports_failure(monkeypatch) -> None:
    settings = _settings(monkeypatch, **EMAIL_OVERRIDES)
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: _FailingSMTP())
    with pytest.raises(EmailDeliveryError):
        send_email(settings, to="owner@example.com", subject="T", body="B")


def test_push_channel_posts_with_token(monkeypatch) -> None:
    settings = _settings(monkeypatch, **PUSH_OVERRIDES)
    client = _PushClient()
    import httpx

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client)
    send_push(settings, title="Title", body="Body")
    assert client.posted["url"] == "https://ntfy.example.com/nexus"
    assert client.posted["headers"]["Authorization"] == "Bearer tok-secret"
    assert client.posted["json"]["topic"] == "nexus"


def test_push_channel_reports_rejection(monkeypatch) -> None:
    settings = _settings(monkeypatch, **PUSH_OVERRIDES)
    import httpx

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: _PushClient(status_code=500))
    with pytest.raises(PushDeliveryError):
        send_push(settings, title="Title", body="Body")


def test_push_channel_rejects_redirect_without_following(monkeypatch) -> None:
    settings = _settings(monkeypatch, **PUSH_OVERRIDES)
    import httpx

    captured: dict[str, object] = {}

    class _RedirectClient:
        def __init__(self, **kwargs):
            captured["follow_redirects"] = kwargs.get("follow_redirects")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, json=None, headers=None):
            return type("Response", (), {"status_code": 302})()

    monkeypatch.setattr(httpx, "Client", _RedirectClient)
    with pytest.raises(PushDeliveryError):
        send_push(settings, title="Title", body="Body")
    assert captured.get("follow_redirects") is False


def test_email_channel_requires_paired_credentials(monkeypatch) -> None:
    with pytest.raises(RuntimeError):
        _settings(
            monkeypatch,
            NOTIFICATION_EMAIL_ENABLED="true",
            NOTIFICATION_EMAIL_SMTP_HOST="smtp.example.com",
            NOTIFICATION_EMAIL_SMTP_USER="nexus",
            NOTIFICATION_EMAIL_FROM="a@b.c",
            NOTIFICATION_EMAIL_TO="d@e.f",
        )


def test_push_url_rejects_loopback(monkeypatch) -> None:
    with pytest.raises(RuntimeError):
        _settings(monkeypatch, NOTIFICATION_PUSH_ENABLED="true", NOTIFICATION_PUSH_URL="http://localhost:8090", NOTIFICATION_PUSH_TOPIC="nexus")


def test_push_url_allows_private_lan(monkeypatch) -> None:
    settings = _settings(monkeypatch, NOTIFICATION_PUSH_ENABLED="true", NOTIFICATION_PUSH_URL="http://192.168.1.50:8090", NOTIFICATION_PUSH_TOPIC="nexus")
    assert settings.notification_push_topic == "nexus"


def test_settings_status_redacts_secrets(monkeypatch) -> None:
    settings = _settings(monkeypatch, **{**EMAIL_OVERRIDES, **PUSH_OVERRIDES})
    dumped = settings_status(settings).model_dump()
    assert dumped["email_smtp_host"] == "smtp.example.com"
    assert dumped["email_credentials_set"] is True
    assert dumped["push_token_set"] is True
    assert "secret-pass-123" not in json.dumps(dumped)
    assert "tok-secret" not in json.dumps(dumped)


def test_enqueue_respects_configured_channels(configured_app, monkeypatch) -> None:
    settings = _settings(monkeypatch, **{**EMAIL_OVERRIDES, **PUSH_OVERRIDES})
    _bootstrap_owner()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    notification = _seed_notification(db, user.id)
    assert enqueue_deliveries(db, notification, settings) == 2
    assert enqueue_deliveries(db, notification, settings) == 0
    channels = set(db.scalars(select(NotificationChannelDelivery.channel).where(NotificationChannelDelivery.notification_id == notification.id)))
    assert channels == {"email", "push"}
    db.close()


def test_worker_delivers_enabled_channel_once(configured_app, monkeypatch) -> None:
    settings = _settings(monkeypatch, **EMAIL_OVERRIDES)
    smtp = _SuccessSMTP()
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: smtp)
    _bootstrap_owner()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    notification = _seed_notification(db, user.id, "test:worker")
    assert enqueue_deliveries(db, notification, settings) == 1
    db.commit()
    assert process_notification_deliveries(db, settings=settings, now=datetime.now(UTC)) == 1
    delivery = db.scalar(select(NotificationChannelDelivery).where(NotificationChannelDelivery.notification_id == notification.id))
    assert delivery is not None
    assert delivery.status == "delivered"
    assert delivery.delivered_at is not None
    assert smtp.sent[-1]["message"]["To"] == "owner@example.com"
    db.close()


def test_worker_retries_then_fails_after_limit(configured_app, monkeypatch) -> None:
    settings = _settings(monkeypatch, **EMAIL_OVERRIDES)
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: _FailingSMTP())
    _bootstrap_owner()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    notification = _seed_notification(db, user.id, "test:retry")
    assert enqueue_deliveries(db, notification, settings) == 1
    db.commit()
    base = datetime.now(UTC)
    assert process_notification_deliveries(db, settings=settings, now=base) == 1
    assert process_notification_deliveries(db, settings=settings, now=base + timedelta(seconds=31)) == 1
    assert process_notification_deliveries(db, settings=settings, now=base + timedelta(seconds=92)) == 1
    delivery = db.scalar(select(NotificationChannelDelivery).where(NotificationChannelDelivery.notification_id == notification.id))
    assert delivery is not None
    assert delivery.status == "failed"
    assert delivery.attempts == 3
    assert delivery.last_error_code == "email_send_failed"
    db.close()


def test_worker_skips_channel_disabled_at_processing_time(configured_app, monkeypatch) -> None:
    both = _settings(monkeypatch, **{**EMAIL_OVERRIDES, **PUSH_OVERRIDES})
    _bootstrap_owner()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    notification = _seed_notification(db, user.id, "test:skip")
    assert enqueue_deliveries(db, notification, both) == 2
    db.commit()
    email_only = _settings(monkeypatch, **EMAIL_OVERRIDES)
    smtp = _SuccessSMTP()
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: smtp)
    assert process_notification_deliveries(db, settings=email_only, now=datetime.now(UTC)) == 2
    states = {item.channel: item.status for item in db.scalars(select(NotificationChannelDelivery).where(NotificationChannelDelivery.notification_id == notification.id))}
    assert states == {"email": "delivered", "push": "skipped"}
    db.close()


def test_worker_reclaims_expired_processing_lease(configured_app, monkeypatch) -> None:
    settings = _settings(monkeypatch, **EMAIL_OVERRIDES)
    smtp = _SuccessSMTP()
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: smtp)
    _bootstrap_owner()
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    notification = _seed_notification(db, user.id, "test:lease")
    db.add(NotificationChannelDelivery(notification_id=notification.id, channel="email", status="processing", attempts=1, available_at=datetime.now(UTC) - timedelta(minutes=5), locked_until=datetime.now(UTC) - timedelta(minutes=4)))
    db.commit()
    assert process_notification_deliveries(db, settings=settings, now=datetime.now(UTC)) == 1
    delivery = db.scalar(select(NotificationChannelDelivery).where(NotificationChannelDelivery.notification_id == notification.id))
    assert delivery.status == "delivered"
    db.close()


def test_settings_route_requires_auth_and_redacts(client) -> None:
    assert client.get("/api/v1/notifications/settings").status_code == 401
    _bootstrap_owner()
    _login(client)
    response = client.get("/api/v1/notifications/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["email_enabled"] is False
    assert body["push_enabled"] is False
    assert "PASSWORD" not in response.text
    assert client.post("/api/v1/notifications/settings/test").status_code == 403
    csrf = client.cookies.get("nexus_csrf")
    result = client.post("/api/v1/notifications/settings/test", headers={"X-CSRF-Token": csrf})
    assert result.status_code == 200
    assert result.json() == []


def test_resend_route_requires_ownership_and_csrf(client) -> None:
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.username == "owner"))
    notification = Notification(user_id=user.id, type="task_reminder", title="One", body="First", dedupe_key="test:resend")
    db.add(notification)
    db.commit()
    db.close()
    assert client.post(f"/api/v1/notifications/{notification.id}/resend").status_code == 403
    response = client.post(f"/api/v1/notifications/{notification.id}/resend", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert response.json()["channels"] == []
    assert client.post("/api/v1/notifications/does-not-exist/resend", headers={"X-CSRF-Token": csrf}).status_code == 404
