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


class NimStatus(BaseModel):
    """Redacted NVIDIA NIM setup state for the owner UI."""

    configured: bool
    source: Literal["browser", "environment", "none"]
    model: str | None = None
    embeddings_enabled: bool = False
    restart_required: bool = False


class NimSetupRequest(BaseModel):
    """Bounded browser setup payload; the API never echoes the key.

    ``api_key`` may be omitted when updating an existing browser-managed
    configuration so owners can change models without re-entering secrets.
    """

    api_key: str | None = Field(default=None, min_length=20, max_length=512)
    model: str = Field(min_length=1, max_length=160)
    embeddings_enabled: bool = False
    embedding_model: str | None = Field(default=None, max_length=160)


class NimTestRequest(BaseModel):
    """Optional temporary credentials for a bounded NIM connection test."""

    api_key: str | None = Field(default=None, min_length=20, max_length=512)
    model: str | None = Field(default=None, min_length=1, max_length=160)


class NimTestResponse(BaseModel):
    """Redacted connection-test result for the owner admin panel."""

    ok: bool
    detail: str
    model: str | None = None
    embeddings_tested: bool = False


class NimChatPreset(BaseModel):
    """Beginner-friendly hosted chat model choice."""

    id: str
    label: str
    description: str
    recommended: bool = False


class NimEmbeddingPreset(BaseModel):
    """Beginner-friendly hosted embedding model choice."""

    id: str
    label: str
    description: str
    recommended: bool = False


class NimOptionsResponse(BaseModel):
    """Static setup guidance and model presets for the admin UI."""

    chat_endpoint: str
    embedding_endpoint: str
    chat_models: list[NimChatPreset]
    embedding_models: list[NimEmbeddingPreset]
    help_text: str


class AdminStatusResponse(BaseModel):
    """Redacted administrative status without secrets or host paths."""

    version: str
    migration_head: str
    checked_at: datetime
    system: AdminStatusCard
    ai_provider: AdminStatusCard
    storage: AdminStatusCard
    embedding_provider: AdminStatusCard
    nvidia_nim: NimStatus = Field(default_factory=lambda: NimStatus(configured=False, source="none"))


class SoftwareUpdateRequest(BaseModel):
    """Owner request for a fixed host-side software update or check."""

    model_config = {"extra": "forbid"}

    action: Literal["check", "apply"] = "apply"
    confirm: bool = False


class SoftwareUpdateStatusResponse(BaseModel):
    """Redacted software-update handshake status for the Admin panel."""

    state: Literal["idle", "queued", "running", "succeeded", "failed", "agent_missing"]
    action: Literal["check", "apply"] | None = None
    request_id: str | None = None
    message: str
    agent_available: bool = False
    current_version: str
    current_commit: str | None = None
    target_commit: str | None = None
    requested_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    log_tail: str | None = None
    can_request: bool = True


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
