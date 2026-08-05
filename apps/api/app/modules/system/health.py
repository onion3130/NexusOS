"""Auto-detect health levels for Raspberry Pi system telemetry."""

from __future__ import annotations

from typing import Literal

HealthLevel = Literal["healthy", "warning", "critical", "unavailable"]

# Pi 5 oriented defaults — thermal throttling typically begins near 80–85 °C.
CPU_WARNING = 70.0
CPU_CRITICAL = 90.0
MEMORY_WARNING = 75.0
MEMORY_CRITICAL = 90.0
STORAGE_WARNING = 75.0
STORAGE_CRITICAL = 90.0
TEMP_WARNING = 65.0
TEMP_CRITICAL = 80.0
LOAD_PER_CORE_WARNING = 1.0
LOAD_PER_CORE_CRITICAL = 2.0

_RANK = {"healthy": 0, "warning": 1, "critical": 2, "unavailable": 1}


def worse(a: HealthLevel, b: HealthLevel) -> HealthLevel:
    """Return the more severe of two health levels."""
    return a if _RANK[a] >= _RANK[b] else b


def level_from_percent(value: float | None, *, warning: float, critical: float) -> HealthLevel:
    if value is None:
        return "unavailable"
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return "healthy"


def cpu_health(usage: float | None, load_1m: float | None, cpu_count: int | None) -> tuple[HealthLevel, str]:
    usage_level = level_from_percent(usage, warning=CPU_WARNING, critical=CPU_CRITICAL)
    load_level: HealthLevel = "healthy"
    if load_1m is not None and cpu_count and cpu_count > 0:
        per_core = load_1m / cpu_count
        if per_core >= LOAD_PER_CORE_CRITICAL:
            load_level = "critical"
        elif per_core >= LOAD_PER_CORE_WARNING:
            load_level = "warning"
    level = worse(usage_level, load_level)
    labels = {"healthy": "Healthy", "warning": "Elevated", "critical": "Critical", "unavailable": "Unavailable"}
    return level, labels[level]


def memory_health(used_percent: float | None) -> tuple[HealthLevel, str]:
    level = level_from_percent(used_percent, warning=MEMORY_WARNING, critical=MEMORY_CRITICAL)
    labels = {"healthy": "Healthy", "warning": "High", "critical": "Critical", "unavailable": "Unavailable"}
    return level, labels[level]


def storage_health(used_percent: float | None) -> tuple[HealthLevel, str]:
    level = level_from_percent(used_percent, warning=STORAGE_WARNING, critical=STORAGE_CRITICAL)
    labels = {"healthy": "Healthy", "warning": "Filling up", "critical": "Critical", "unavailable": "Unavailable"}
    return level, labels[level]


def temperature_health(celsius: float | None) -> tuple[HealthLevel, str]:
    level = level_from_percent(celsius, warning=TEMP_WARNING, critical=TEMP_CRITICAL)
    labels = {"healthy": "Cool", "warning": "Warm", "critical": "Hot", "unavailable": "Unavailable"}
    return level, labels[level]


def network_health(available: bool, interface_count: int) -> tuple[HealthLevel, str]:
    if not available:
        return "critical", "Offline"
    if interface_count <= 0:
        return "warning", "No interfaces"
    return "healthy", "Online"


def uptime_health(seconds: float | None) -> tuple[HealthLevel, str]:
    if seconds is None:
        return "unavailable", "Unavailable"
    return "healthy", "Online"


def overall_health(levels: list[HealthLevel], *, sources_degraded: bool) -> tuple[HealthLevel, str, list[str]]:
    """Combine metric levels into one system verdict."""
    level: HealthLevel = "healthy"
    for item in levels:
        if item == "unavailable":
            continue
        level = worse(level, item)
    if sources_degraded and level == "healthy":
        level = "warning"
    labels = {
        "healthy": "Healthy",
        "warning": "Needs attention",
        "critical": "Dangerous",
        "unavailable": "Unavailable",
    }
    reasons: list[str] = []
    if "critical" in levels:
        reasons.append("One or more metrics are in a critical range")
    if "warning" in levels:
        reasons.append("One or more metrics are elevated")
    if sources_degraded:
        reasons.append("Some telemetry sources are unavailable")
    if not reasons:
        reasons.append("All monitored signals look normal")
    return level, labels[level], reasons
