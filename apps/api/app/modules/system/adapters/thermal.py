"""Read-only Linux thermal-zone adapter."""

from __future__ import annotations

from pathlib import Path


def read_temperature(sys_root: Path = Path("/sys")) -> tuple[float, str]:
    """Return the highest readable thermal-zone temperature in Celsius."""
    readings: list[tuple[float, str]] = []
    thermal_root = sys_root / "class" / "thermal"
    for zone in sorted(thermal_root.glob("thermal_zone*/temp")):
        try:
            raw = zone.read_text(encoding="utf-8").strip()
            millidegrees = int(raw)
            celsius = millidegrees / 1000
            if -50 <= celsius <= 150:
                zone_type = zone.parent / "type"
                name = zone_type.read_text(encoding="utf-8").strip()[:64] if zone_type.is_file() else zone.parent.name
                readings.append((celsius, name))
        except (OSError, ValueError):
            continue
    if not readings:
        raise ValueError("thermal reading unavailable")
    return max(readings, key=lambda reading: reading[0])
