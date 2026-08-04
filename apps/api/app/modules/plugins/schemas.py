"""Public schemas for the out-of-process plugin boundary."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CapabilityRisk = Literal["read", "write", "dangerous"]
PluginStatus = Literal["enabled", "disabled", "uninstalled"]

_METHOD_RE = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")
_NAME_RE = re.compile(r"[a-z0-9_-]{1,64}\Z")
_VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+){0,3}(?:[-+][A-Za-z0-9_.-]+)?\Z")


class Capability(BaseModel):
    """One declared, allowlisted method a plugin may be asked to run."""

    model_config = {"extra": "forbid"}
    method: str
    description: str = Field(default="", max_length=240)
    risk: CapabilityRisk = "read"

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str) -> str:
        """Reject shell-sensitive or reserved method identifiers."""
        normalized = value.strip()
        if not normalized or not _METHOD_RE.fullmatch(normalized):
            raise ValueError("must be a lowercase dotted identifier")
        if normalized in {"status", "error", "result", "method", "arguments", "id"}:
            raise ValueError("reserved method name")
        return normalized


class PluginManifest(BaseModel):
    """Validated plugin.json content from an operator-approved directory."""

    model_config = {"extra": "forbid"}
    name: str
    version: str
    description: str = Field(default="", max_length=240)
    entrypoint: str
    capabilities: list[Capability] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject names that could escape the approved plugins directory."""
        normalized = value.strip().lower()
        if not normalized or not _NAME_RE.fullmatch(normalized):
            raise ValueError("must contain only lowercase letters, numbers, dashes, or underscores")
        if normalized in {"..", ".", "plugin", "plugins"}:
            raise ValueError("reserved name")
        return normalized

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        """Require a bounded semver-like version string."""
        normalized = value.strip()
        if not normalized or len(normalized) > 32 or not _VERSION_RE.fullmatch(normalized):
            raise ValueError("must be a bounded semver-like version")
        return normalized

    @field_validator("entrypoint")
    @classmethod
    def validate_entrypoint(cls, value: str) -> str:
        """Allow only relative confined paths without traversal."""
        normalized = value.strip()
        if not normalized or len(normalized) > 256:
            raise ValueError("must be a relative path")
        if normalized.startswith(("/", "\\")) or ".." in normalized.split("/") or ":" in normalized or "\\" in normalized:
            raise ValueError("must be a relative path inside the plugin directory")
        return normalized

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, value: list[Capability]) -> list[Capability]:
        """Require a non-empty bounded allowlist without duplicate methods."""
        if not value or len(value) > 32:
            raise ValueError("must declare between 1 and 32 capabilities")
        methods = [capability.method for capability in value]
        if len(methods) != len(set(methods)):
            raise ValueError("capability methods must be unique")
        return value


class PluginCapabilityResponse(BaseModel):
    method: str
    description: str
    risk: CapabilityRisk


class PluginResponse(BaseModel):
    id: str
    name: str
    version: str
    description: str
    entrypoint: str
    capabilities: list[PluginCapabilityResponse]
    status: PluginStatus
    last_error_code: str | None
    updated_at: datetime
    run_count: int = 0


class PluginRunResponse(BaseModel):
    id: str
    plugin_id: str
    method: str
    status: Literal["success", "failure"]
    error_code: str | None
    duration_ms: int | None
    created_at: datetime


class PluginInvokeRequest(BaseModel):
    """Bounded invocation request for a read-risk plugin capability."""

    model_config = {"extra": "forbid"}
    method: str = Field(min_length=1, max_length=64)
    arguments: dict[str, object] = Field(default_factory=dict)

    @field_validator("arguments")
    @classmethod
    def validate_arguments(cls, value: dict[str, object]) -> dict[str, object]:
        """Bound the size of a plugin invocation payload."""
        if len(value) > 16:
            raise ValueError("must contain at most 16 arguments")
        return value
