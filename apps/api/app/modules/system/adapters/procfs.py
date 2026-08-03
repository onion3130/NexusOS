"""Read-only Linux procfs adapter."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable


def _read(path: Path) -> str:
    """Read a bounded procfs text file."""
    return path.read_text(encoding="utf-8", errors="strict")


def _cpu_times(proc_root: Path) -> tuple[int, ...]:
    """Read aggregate CPU counters from `/proc/stat`."""
    first_line = _read(proc_root / "stat").splitlines()[0]
    fields = first_line.split()
    if not fields or fields[0] != "cpu" or len(fields) < 5:
        raise ValueError("cpu counters unavailable")
    values = tuple(int(value) for value in fields[1:])
    if not values or sum(values) <= 0:
        raise ValueError("cpu counters invalid")
    return values


def read_cpu_usage(
    proc_root: Path = Path("/proc"),
    *,
    sample_seconds: float = 0.05,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    """Calculate aggregate CPU utilization from two short procfs samples."""
    before = _cpu_times(proc_root)
    sleep(max(0.0, sample_seconds))
    after = _cpu_times(proc_root)
    total_delta = sum(after) - sum(before)
    idle_before = before[3] + (before[4] if len(before) > 4 else 0)
    idle_after = after[3] + (after[4] if len(after) > 4 else 0)
    idle_delta = idle_after - idle_before
    if total_delta <= 0:
        raise ValueError("cpu sample interval invalid")
    return round(max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta)), 1)


def read_load_1m(proc_root: Path = Path("/proc")) -> float:
    """Read the one-minute load average."""
    value = float(_read(proc_root / "loadavg").split()[0])
    if value < 0:
        raise ValueError("load average invalid")
    return round(value, 2)


def read_cpu_count() -> int:
    """Return the logical CPU count without touching a host control API."""
    count = os.cpu_count()
    if count is None or count < 1:
        raise ValueError("cpu count unavailable")
    return count


def read_memory(proc_root: Path = Path("/proc")) -> tuple[int, int, float]:
    """Read total and available memory from `/proc/meminfo`."""
    values: dict[str, int] = {}
    for line in _read(proc_root / "meminfo").splitlines():
        key, separator, remainder = line.partition(":")
        if not separator:
            continue
        parts = remainder.strip().split()
        if parts and parts[0].isdigit():
            values[key] = int(parts[0]) * (1024 if len(parts) > 1 and parts[1] == "kB" else 1)
    total = values.get("MemTotal")
    available = values.get("MemAvailable", values.get("MemFree"))
    if total is None or available is None or total <= 0 or not 0 <= available <= total:
        raise ValueError("memory counters unavailable")
    return total, available, round((total - available) * 100 / total, 1)


def read_uptime(proc_root: Path = Path("/proc")) -> float:
    """Read system uptime seconds from `/proc/uptime`."""
    value = float(_read(proc_root / "uptime").split()[0])
    if value < 0:
        raise ValueError("uptime invalid")
    return round(value, 1)
