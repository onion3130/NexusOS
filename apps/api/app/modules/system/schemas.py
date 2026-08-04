"""Public schemas for the read-only system overview."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Availability(BaseModel):
    """Describe whether a metric source was readable."""

    available: bool
    reason: str | None = None


class CpuTelemetry(BaseModel):
    """CPU load and utilization information."""

    usage_percent: float | None = Field(default=None, ge=0, le=100)
    load_1m: float | None = Field(default=None, ge=0)
    cpu_count: int | None = Field(default=None, ge=1)
    source: Availability


class MemoryTelemetry(BaseModel):
    """Memory capacity and usage information in bytes."""

    total_bytes: int | None = Field(default=None, ge=0)
    available_bytes: int | None = Field(default=None, ge=0)
    used_percent: float | None = Field(default=None, ge=0, le=100)
    source: Availability


class StorageTelemetry(BaseModel):
    """Configured data-volume capacity and usage information."""

    path_label: str
    total_bytes: int | None = Field(default=None, ge=0)
    used_bytes: int | None = Field(default=None, ge=0)
    free_bytes: int | None = Field(default=None, ge=0)
    used_percent: float | None = Field(default=None, ge=0, le=100)
    source: Availability


class TemperatureTelemetry(BaseModel):
    """CPU/system thermal reading."""

    celsius: float | None = None
    source_name: str | None = None
    source: Availability


class UptimeTelemetry(BaseModel):
    """System uptime."""

    seconds: float | None = Field(default=None, ge=0)
    source: Availability


class NetworkInterfaceTelemetry(BaseModel):
    """Safe read-only counters for one network interface."""

    name: str
    state: str | None = None
    receive_bytes: int = Field(ge=0)
    transmit_bytes: int = Field(ge=0)


class NetworkTelemetry(BaseModel):
    """Network interface counters."""

    interfaces: list[NetworkInterfaceTelemetry]
    source: Availability


class ServiceStatusTelemetry(BaseModel):
    """Status boundary for service/container data not yet safely exposed."""

    services_available: bool
    containers_available: bool
    reason: str | None = None
    source: Availability


class AssistantProviderStatus(BaseModel):
    """Safe provider status for authenticated assistant users."""

    provider: Literal["disabled", "openai", "openai_compatible", "nvidia_nim"]
    label: str
    state: Literal["configured", "disabled"]
    model: str | None = None
    detail: str


class AdminStatusCard(BaseModel):
    """One redacted status card for the authenticated owner dashboard."""

    state: Literal["ready", "degraded", "disabled"]
    value: str
    detail: str


class AdminStatusResponse(BaseModel):
    """Redacted administrative status without secrets or host paths."""

    version: str
    migration_head: str
    checked_at: datetime
    system: AdminStatusCard
    ai_provider: AdminStatusCard
    storage: AdminStatusCard
    embedding_provider: AdminStatusCard


class SystemOverviewResponse(BaseModel):
    """Authenticated read-only Raspberry Pi system overview."""

    status: Literal["ok", "degraded"]
    checked_at: datetime
    cpu: CpuTelemetry
    memory: MemoryTelemetry
    storage: StorageTelemetry
    temperature: TemperatureTelemetry
    uptime: UptimeTelemetry
    network: NetworkTelemetry
    service_status: ServiceStatusTelemetry
