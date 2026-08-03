"""Deterministic bounded recurrence calculations for task series."""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


class RecurrenceError(ValueError):
    """Raised for unsupported or invalid recurrence definitions."""


def validate_rule(rule: dict[str, object]) -> dict[str, object]:
    """Validate and normalize the supported version-one recurrence shape."""
    if rule.get("version", 1) != 1:
        raise RecurrenceError("unsupported recurrence version")
    frequency = rule.get("frequency")
    if frequency not in {"daily", "weekly", "monthly"}:
        raise RecurrenceError("frequency must be daily, weekly, or monthly")
    interval = rule.get("interval", 1)
    if not isinstance(interval, int) or not 1 <= interval <= 365:
        raise RecurrenceError("interval must be between 1 and 365")
    normalized: dict[str, object] = {"version": 1, "frequency": frequency, "interval": interval}
    if frequency == "weekly":
        weekdays = rule.get("weekdays") or []
        if not isinstance(weekdays, list) or not weekdays or any(day not in {"MO", "TU", "WE", "TH", "FR", "SA", "SU"} for day in weekdays):
            raise RecurrenceError("weekly recurrence requires valid weekdays")
        normalized["weekdays"] = list(dict.fromkeys(weekdays))
    if frequency == "monthly":
        day = rule.get("day_of_month")
        if not isinstance(day, int) or not 1 <= day <= 31:
            raise RecurrenceError("monthly recurrence requires day_of_month 1-31")
        normalized["day_of_month"] = day
    if rule.get("timezone") is not None:
        timezone = rule["timezone"]
        if not isinstance(timezone, str):
            raise RecurrenceError("timezone must be a string")
        try:
            ZoneInfo(timezone)
        except (KeyError, ValueError) as exc:
            raise RecurrenceError("timezone must be a valid IANA timezone") from exc
        normalized["timezone"] = timezone
    if rule.get("ends_at") is not None:
        ends_at = rule["ends_at"]
        if not isinstance(ends_at, str):
            raise RecurrenceError("ends_at must be an ISO timestamp")
        try:
            parsed_end = datetime.fromisoformat(ends_at)
        except ValueError as exc:
            raise RecurrenceError("ends_at must be an ISO timestamp") from exc
        if parsed_end.tzinfo is None:
            raise RecurrenceError("ends_at must include a timezone offset")
        normalized["ends_at"] = parsed_end.astimezone(UTC).isoformat()
    if rule.get("count") is not None:
        count = rule["count"]
        if not isinstance(count, int) or not 1 <= count <= 10000:
            raise RecurrenceError("count must be between 1 and 10000")
        normalized["count"] = count
    return normalized


def _weekday_code(value: int) -> str:
    return ("MO", "TU", "WE", "TH", "FR", "SA", "SU")[value]


def next_occurrence(current: datetime, rule: dict[str, object], *, next_index: int = 1) -> datetime | None:
    """Return the next UTC occurrence using the rule's local timezone and count."""
    normalized = validate_rule(rule)
    if next_index < 1:
        raise RecurrenceError("next occurrence index must be positive")
    count = normalized.get("count")
    if isinstance(count, int) and next_index > count:
        return None
    timezone_name = str(normalized.get("timezone", "UTC"))
    timezone = UTC if timezone_name == "UTC" else ZoneInfo(timezone_name)
    current_local = current.astimezone(timezone)
    frequency = normalized["frequency"]
    interval = int(normalized["interval"])
    if frequency == "daily":
        candidate_local = current_local + timedelta(days=interval)
    elif frequency == "monthly":
        month_index = current_local.year * 12 + current_local.month - 1 + interval
        year, month_index = divmod(month_index, 12)
        month = month_index + 1
        day = min(int(normalized["day_of_month"]), monthrange(year, month)[1])
        candidate_local = current_local.replace(year=year, month=month, day=day)
    else:
        weekdays = set(normalized["weekdays"])
        candidate_local = current_local + timedelta(days=1)
        for _ in range(366 * 2):
            if _weekday_code(candidate_local.weekday()) in weekdays:
                weeks_from_current = (candidate_local.date() - current_local.date()).days // 7
                if weeks_from_current % interval == 0:
                    break
            candidate_local += timedelta(days=1)
        else:
            raise RecurrenceError("unable to calculate weekly occurrence")
    candidate = candidate_local.astimezone(UTC)
    ends_at = normalized.get("ends_at")
    if isinstance(ends_at, str) and candidate > datetime.fromisoformat(ends_at).astimezone(UTC):
        return None
    return candidate
