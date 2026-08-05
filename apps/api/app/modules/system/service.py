"""System telemetry orchestration without host write capabilities."""

from __future__ import annotations

import socket
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
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
from app.modules.system.health import (
    cpu_health,
    memory_health,
    network_health,
    overall_health,
    storage_health,
    temperature_health,
    uptime_health,
    worse,
)
from app.modules.system.schemas import (
    Availability,
    CpuTelemetry,
    MemoryTelemetry,
    MetricHealth,
    NetworkInterfaceTelemetry,
    NetworkTelemetry,
    ServiceStatusTelemetry,
    ServiceUnitStatus,
    StorageTelemetry,
    SystemHealthSummary,
    SystemOverviewResponse,
    TemperatureTelemetry,
    UptimeTelemetry,
)

# Compose service names used by the default NexusOS stack.
_NEXUS_COMPOSE_SERVICES = ("nexus-api", "nexus-web", "nexus-worker", "nexus-proxy")


class SystemService:
    """Collect read-only metrics from fixed Linux/runtime boundaries."""

    def __init__(
        self,
        data_dir: Path,
        proc_root: Path = Path("/proc"),
        sys_root: Path = Path("/sys"),
        docker_socket_path: str = "",
    ) -> None:
        self.data_dir = data_dir
        self.proc_root = proc_root
        self.sys_root = sys_root
        self.docker_socket_path = docker_socket_path.strip()

    @classmethod
    def from_settings(cls, settings: Settings) -> "SystemService":
        """Build a collector from validated application settings."""
        return cls(data_dir=settings.data_dir, docker_socket_path=settings.docker_socket_path)

    @staticmethod
    def _availability(error_code: str | None = None) -> Availability:
        """Create a safe availability result without exposing exception details."""
        return Availability(available=error_code is None, reason=error_code)

    def _collect_service_status(self) -> ServiceStatusTelemetry:
        """Detect Nexus stack units via Docker socket and/or private network DNS."""
        units: list[ServiceUnitStatus] = []
        containers_available = False
        services_available = False
        reason: str | None = None

        socket_path = Path(self.docker_socket_path) if self.docker_socket_path else None
        if socket_path is not None and socket_path.is_socket():
            try:
                from app.modules.workspace_views.adapters.docker import list_containers

                containers = list_containers(socket_path, limit=50)
                containers_available = True
                services_available = True
                for item in containers:
                    name = item.name
                    state = item.state if item.state in {"running", "exited", "restarting", "paused", "created"} else "unknown"
                    if state == "running":
                        health = "healthy"
                    elif state in {"restarting", "paused"}:
                        health = "warning"
                    elif state == "exited":
                        health = "critical"
                    else:
                        health = "warning"
                    detail = item.compose_service or item.image
                    units.append(
                        ServiceUnitStatus(
                            name=name[:96],
                            kind="container",
                            state=state,  # type: ignore[arg-type]
                            health=health,  # type: ignore[arg-type]
                            detail=detail[:160] if detail else None,
                        )
                    )
            except (OSError, ValueError, RuntimeError):
                reason = "docker_socket_unavailable"
                containers_available = False

        if not units:
            # Fall back to private-network DNS for Compose service names (no socket required).
            for service_name in _NEXUS_COMPOSE_SERVICES:
                try:
                    socket.getaddrinfo(service_name, None, type=socket.SOCK_STREAM)
                    services_available = True
                    units.append(
                        ServiceUnitStatus(
                            name=service_name,
                            kind="service",
                            state="running",
                            health="healthy",
                            detail="Reachable on the private Compose network",
                        )
                    )
                except (OSError, socket.gaierror):
                    units.append(
                        ServiceUnitStatus(
                            name=service_name,
                            kind="service",
                            state="unavailable",
                            health="warning",
                            detail="Not resolvable from this container",
                        )
                    )
            if services_available:
                reason = None
            else:
                reason = reason or "service_status_unavailable"

        if not units:
            return ServiceStatusTelemetry(
                services_available=False,
                containers_available=False,
                units=[],
                reason=reason or "service_status_unavailable",
                source=self._availability(reason or "service_status_unavailable"),
                health=MetricHealth(level="unavailable", label="Unavailable"),
            )

        unit_levels = [unit.health for unit in units]
        level = "healthy"
        for item in unit_levels:
            level = worse(level, item)  # type: ignore[arg-type]
        labels = {"healthy": "Healthy", "warning": "Attention", "critical": "Unhealthy", "unavailable": "Unavailable"}
        return ServiceStatusTelemetry(
            services_available=services_available or any(unit.kind == "service" for unit in units),
            containers_available=containers_available,
            units=units[:24],
            reason=reason,
            source=Availability(available=True, reason=None),
            health=MetricHealth(level=level, label=labels[level]),  # type: ignore[index]
        )

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

        cpu_level, cpu_label = cpu_health(cpu_usage, cpu_load, cpu_count if cpu_error is None else None)
        if cpu_error:
            cpu_level, cpu_label = "unavailable", "Unavailable"
        mem_level, mem_label = memory_health(memory_percent if memory_error is None else None)
        store_level, store_label = storage_health(storage_percent if storage_error is None else None)
        temp_level, temp_label = temperature_health(temperature if temperature_error is None else None)
        up_level, up_label = uptime_health(uptime if uptime_error is None else None)
        net_level, net_label = network_health(network_error is None, len(interfaces))

        service_status = self._collect_service_status()
        metric_errors = [error for error in (cpu_error, memory_error, storage_error, temperature_error, uptime_error, network_error) if error]
        levels = [cpu_level, mem_level, store_level, temp_level, up_level, net_level, service_status.health.level]
        health_level, health_label, reasons = overall_health(levels, sources_degraded=bool(metric_errors))

        return SystemOverviewResponse(
            status="degraded" if metric_errors or health_level in {"warning", "critical"} else "ok",
            checked_at=datetime.now(UTC),
            health=SystemHealthSummary(level=health_level, label=health_label, reasons=reasons),
            cpu=CpuTelemetry(
                usage_percent=cpu_usage,
                load_1m=cpu_load,
                cpu_count=cpu_count,
                source=self._availability(cpu_error),
                health=MetricHealth(level=cpu_level, label=cpu_label),
            ),
            memory=MemoryTelemetry(
                total_bytes=total_memory,
                available_bytes=available_memory,
                used_percent=memory_percent,
                source=self._availability(memory_error),
                health=MetricHealth(level=mem_level, label=mem_label),
            ),
            storage=StorageTelemetry(
                path_label="configured data volume",
                total_bytes=total_storage,
                used_bytes=used_storage,
                free_bytes=free_storage,
                used_percent=storage_percent,
                source=self._availability(storage_error),
                health=MetricHealth(level=store_level, label=store_label),
            ),
            temperature=TemperatureTelemetry(
                celsius=temperature,
                source_name=temperature_name,
                source=self._availability(temperature_error),
                health=MetricHealth(level=temp_level, label=temp_label),
            ),
            uptime=UptimeTelemetry(
                seconds=uptime,
                source=self._availability(uptime_error),
                health=MetricHealth(level=up_level, label=up_label),
            ),
            network=NetworkTelemetry(
                interfaces=interfaces,
                source=self._availability(network_error),
                health=MetricHealth(level=net_level, label=net_label),
            ),
            service_status=service_status,
        )
