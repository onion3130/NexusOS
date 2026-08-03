"""System telemetry orchestration without host write capabilities."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.modules.system.adapters.network import read_interfaces
from app.modules.system.adapters.procfs import (
    read_cpu_count,
    read_cpu_usage,
    read_load_1m,
    read_memory,
    read_uptime,
)
from app.modules.system.adapters.storage import read_storage
from app.modules.system.adapters.thermal import read_temperature
from app.modules.system.schemas import (
    Availability,
    CpuTelemetry,
    MemoryTelemetry,
    NetworkInterfaceTelemetry,
    NetworkTelemetry,
    ServiceStatusTelemetry,
    StorageTelemetry,
    SystemOverviewResponse,
    TemperatureTelemetry,
    UptimeTelemetry,
)


class SystemService:
    """Collect read-only metrics from fixed Linux/runtime boundaries."""

    def __init__(self, data_dir: Path, proc_root: Path = Path("/proc"), sys_root: Path = Path("/sys")) -> None:
        self.data_dir = data_dir
        self.proc_root = proc_root
        self.sys_root = sys_root

    @staticmethod
    def _availability(error_code: str | None = None) -> Availability:
        """Create a safe availability result without exposing exception details."""
        return Availability(available=error_code is None, reason=error_code)

    def collect(self) -> SystemOverviewResponse:
        """Collect every metric independently so one unavailable source degrades safely."""
        cpu_usage: float | None = None
        cpu_load: float | None = None
        cpu_count: int | None = None
        cpu_error: str | None = None
        try:
            cpu_usage = read_cpu_usage(self.proc_root)
            cpu_load = read_load_1m(self.proc_root)
            cpu_count = read_cpu_count()
        except (OSError, ValueError):
            cpu_error = "cpu_unavailable"

        total_memory: int | None = None
        available_memory: int | None = None
        memory_percent: float | None = None
        memory_error: str | None = None
        try:
            total_memory, available_memory, memory_percent = read_memory(self.proc_root)
        except (OSError, ValueError):
            memory_error = "memory_unavailable"

        total_storage: int | None = None
        used_storage: int | None = None
        free_storage: int | None = None
        storage_percent: float | None = None
        storage_error: str | None = None
        try:
            total_storage, used_storage, free_storage, storage_percent = read_storage(self.data_dir)
        except (OSError, ValueError):
            storage_error = "storage_unavailable"

        temperature: float | None = None
        temperature_name: str | None = None
        temperature_error: str | None = None
        try:
            temperature, temperature_name = read_temperature(self.sys_root)
        except (OSError, ValueError):
            temperature_error = "temperature_unavailable"

        uptime: float | None = None
        uptime_error: str | None = None
        try:
            uptime = read_uptime(self.proc_root)
        except (OSError, ValueError):
            uptime_error = "uptime_unavailable"

        interfaces: list[NetworkInterfaceTelemetry] = []
        network_error: str | None = None
        try:
            interfaces = [NetworkInterfaceTelemetry(**interface) for interface in read_interfaces(self.proc_root, self.sys_root)]
        except (OSError, ValueError):
            network_error = "network_unavailable"

        metric_errors = [error for error in (cpu_error, memory_error, storage_error, temperature_error, uptime_error, network_error) if error]
        return SystemOverviewResponse(
            status="degraded" if metric_errors else "ok",
            checked_at=datetime.now(UTC),
            cpu=CpuTelemetry(usage_percent=cpu_usage, load_1m=cpu_load, cpu_count=cpu_count, source=self._availability(cpu_error)),
            memory=MemoryTelemetry(total_bytes=total_memory, available_bytes=available_memory, used_percent=memory_percent, source=self._availability(memory_error)),
            storage=StorageTelemetry(path_label="configured data volume", total_bytes=total_storage, used_bytes=used_storage, free_bytes=free_storage, used_percent=storage_percent, source=self._availability(storage_error)),
            temperature=TemperatureTelemetry(celsius=temperature, source_name=temperature_name, source=self._availability(temperature_error)),
            uptime=UptimeTelemetry(seconds=uptime, source=self._availability(uptime_error)),
            network=NetworkTelemetry(interfaces=interfaces, source=self._availability(network_error)),
            service_status=ServiceStatusTelemetry(
                services_available=False,
                containers_available=False,
                reason="service_status_unavailable",
                source=Availability(available=False, reason="service_status_unavailable"),
            ),
        )
