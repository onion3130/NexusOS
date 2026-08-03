"""Read-only Linux network adapter."""

from __future__ import annotations

import re
from pathlib import Path

_INTERFACE_NAME = re.compile(r"^[A-Za-z0-9_.:-]{1,15}$")


def read_interfaces(proc_root: Path = Path("/proc"), sys_root: Path = Path("/sys")) -> list[dict[str, object]]:
    """Read receive/transmit counters and operational state for interfaces."""
    interfaces: list[dict[str, object]] = []
    lines = (proc_root / "net" / "dev").read_text(encoding="utf-8").splitlines()
    for line in lines:
        if ":" not in line:
            continue
        raw_name, raw_counters = line.split(":", 1)
        name = raw_name.strip()
        if not _INTERFACE_NAME.fullmatch(name):
            continue
        counters = raw_counters.split()
        if len(counters) < 9 or not counters[0].isdigit() or not counters[8].isdigit():
            continue
        state_path = sys_root / "class" / "net" / name / "operstate"
        try:
            state = state_path.read_text(encoding="utf-8").strip()[:32]
        except OSError:
            state = None
        interfaces.append(
            {
                "name": name,
                "state": state,
                "receive_bytes": int(counters[0]),
                "transmit_bytes": int(counters[8]),
            }
        )
    return interfaces
