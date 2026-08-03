"""Read-only configured storage adapter."""

from __future__ import annotations

import shutil
from pathlib import Path


def read_storage(data_dir: Path) -> tuple[int, int, int, float]:
    """Return total, used, free bytes and percentage for the configured data root."""
    usage = shutil.disk_usage(data_dir)
    if usage.total <= 0 or usage.used < 0 or usage.free < 0:
        raise ValueError("storage counters invalid")
    used_percent = round(usage.used * 100 / usage.total, 1)
    return usage.total, usage.used, usage.free, used_percent
