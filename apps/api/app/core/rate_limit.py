"""Small in-process protections for the single-process identity foundation."""

from __future__ import annotations

import threading
import time
from collections import defaultdict

_MAX_TRACKED_KEYS = 10_000
_BASE_DELAY_SECONDS = 0.5
_MAX_DELAY_SECONDS = 30.0

_lock = threading.Lock()
_failures: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))


def _key(username: str, client_host: str | None) -> str:
    """Build a bounded, non-secret login throttle key."""
    return f"{(client_host or 'unknown')[:64]}:{username.strip().lower()[:64]}"


def login_retry_after(username: str, client_host: str | None) -> float:
    """Return remaining backoff seconds for a login key, if any."""
    key = _key(username, client_host)
    now = time.monotonic()
    with _lock:
        _, blocked_until = _failures.get(key, (0, 0.0))
        return max(0.0, blocked_until - now)


def record_login_failure(username: str, client_host: str | None) -> None:
    """Increase bounded exponential backoff after a failed login."""
    key = _key(username, client_host)
    now = time.monotonic()
    with _lock:
        if len(_failures) >= _MAX_TRACKED_KEYS and key not in _failures:
            oldest = min(_failures, key=lambda candidate: _failures[candidate][1])
            _failures.pop(oldest, None)
        failures, _ = _failures.get(key, (0, 0.0))
        failures += 1
        delay = min(_MAX_DELAY_SECONDS, _BASE_DELAY_SECONDS * (2 ** min(failures - 1, 6)))
        _failures[key] = (failures, now + delay)


def clear_login_failures(username: str, client_host: str | None) -> None:
    """Clear backoff after a successful login."""
    with _lock:
        _failures.pop(_key(username, client_host), None)


def reset_login_limits() -> None:
    """Clear throttle state for tests and controlled process resets."""
    with _lock:
        _failures.clear()
