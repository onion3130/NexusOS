"""Milestone 4 read-only system telemetry tests."""

from __future__ import annotations

from pathlib import Path

from app.db.session import get_session_factory
from app.modules.identity.service import bootstrap_owner
from app.modules.system.adapters.network import read_interfaces
from app.modules.system.adapters.procfs import read_memory, read_uptime
from app.modules.system.adapters.thermal import read_temperature
from app.modules.system.service import SystemService


def _bootstrap_owner() -> None:
    """Create the fixture owner through the existing identity service."""
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _write_proc_fixture(root: Path) -> None:
    """Create deterministic procfs files for adapter tests."""
    (root / "net").mkdir(parents=True)
    (root / "stat").write_text("cpu  100 0 100 800 0 0 0 0 0 0\n", encoding="utf-8")
    (root / "loadavg").write_text("0.42 0.20 0.10 1/100 123\n", encoding="utf-8")
    (root / "meminfo").write_text("MemTotal:       1024 kB\nMemAvailable:    512 kB\n", encoding="utf-8")
    (root / "uptime").write_text("123.4 50.0\n", encoding="utf-8")
    (root / "net" / "dev").write_text("Inter-| Receive | Transmit\n eth0: 100 0 0 0 0 0 0 0 200 0 0 0 0 0 0 0\n", encoding="utf-8")


def test_procfs_adapters_read_bounded_values(tmp_path) -> None:
    """Procfs adapters parse only the expected numeric fields."""
    proc_root = tmp_path / "proc"
    _write_proc_fixture(proc_root)
    assert read_memory(proc_root) == (1024 * 1024, 512 * 1024, 50.0)
    assert read_uptime(proc_root) == 123.4
    interfaces = read_interfaces(proc_root)
    assert interfaces and interfaces[0]["name"] == "eth0"
    assert interfaces[0]["receive_bytes"] == 100
    assert interfaces[0]["transmit_bytes"] == 200


def test_thermal_adapter_skips_invalid_zones(tmp_path) -> None:
    """Thermal discovery ignores malformed zones and returns valid readings."""
    zone = tmp_path / "sys" / "class" / "thermal" / "thermal_zone0"
    zone.mkdir(parents=True)
    (zone / "temp").write_text("47000\n", encoding="utf-8")
    (zone / "type").write_text("cpu-thermal\n", encoding="utf-8")
    assert read_temperature(tmp_path / "sys") == (47.0, "cpu-thermal")


def test_system_service_degrades_without_exposing_paths(tmp_path) -> None:
    """Missing Linux sources produce safe codes and no filesystem path disclosure."""
    result = SystemService(tmp_path / "missing", tmp_path / "proc", tmp_path / "sys").collect()
    assert result.status == "degraded"
    assert result.storage.source.reason == "storage_unavailable"
    assert result.temperature.source.reason == "temperature_unavailable"
    assert str(tmp_path) not in result.model_dump_json()


def test_system_overview_requires_authentication(client) -> None:
    """The system overview is not public and does not add write routes."""
    assert client.get("/api/v1/system/overview").status_code == 401
    _bootstrap_owner()
    login = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    response = client.get("/api/v1/system/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["storage"]["path_label"] == "configured data volume"
    assert body["service_status"]["containers_available"] is False
    assert "shutdown" not in body
