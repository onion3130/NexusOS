"""Redacted administrative and assistant provider status collection."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from app import __version__
from app.core.config import Settings
from app.db.session import CURRENT_MIGRATION_HEAD, database_status
from app.modules.system.schemas import AdminStatusCard, AdminStatusResponse, AssistantProviderStatus


def assistant_provider_status(settings: Settings) -> AssistantProviderStatus:
    """Return the selected chat provider and model without credentials or endpoints."""
    if settings.ai_provider == "disabled":
        return AssistantProviderStatus(
            provider="disabled",
            label="AI disabled",
            state="disabled",
            model=None,
            detail="Configure NVIDIA NIM on the server to enable the Assistant",
        )
    label = {
        "nvidia_nim": "NVIDIA NIM",
        "openai": "OpenAI",
        "openai_compatible": "OpenAI-compatible",
    }.get(settings.ai_provider, "Configured provider")
    return AssistantProviderStatus(
        provider=settings.ai_provider,
        label=label,
        state="configured",
        model=settings.ai_model,
        detail="Server-side configuration is valid; provider reachability is checked when a message is sent",
    )


def _storage_status(settings: Settings, database_ready: bool, database_reason: str | None) -> tuple[AdminStatusCard, bool]:
    """Report storage and database readiness without exposing host paths."""
    data_dir = settings.data_dir
    if not data_dir.is_dir():
        return AdminStatusCard(state="degraded", value="Unavailable", detail="Configured data volume is not mounted"), False
    try:
        free_bytes = shutil.disk_usage(data_dir).free
    except OSError:
        return AdminStatusCard(state="degraded", value="Unavailable", detail="Storage cannot be read"), False
    if not database_ready:
        detail = {
            "migration_required": "Run the pending database migrations",
            "search_unavailable": "SQLite search index is unavailable",
            "database_unavailable": "SQLite cannot be opened",
        }.get(database_reason or "", "Database is not ready")
        return AdminStatusCard(state="degraded", value="SQLite attention needed", detail=detail), False
    return AdminStatusCard(state="ready", value="SQLite ready", detail=f"Database online · {free_bytes // (1024 ** 3)} GB free"), True


def _provider_status(settings: Settings) -> AdminStatusCard:
    """Report provider selection/configuration without returning credentials or URLs."""
    provider = assistant_provider_status(settings)
    if provider.state == "disabled":
        return AdminStatusCard(state="disabled", value="Disabled", detail=provider.detail)
    return AdminStatusCard(state="ready", value="Configured · " + provider.label, detail=provider.detail)


def _embedding_status(settings: Settings) -> AdminStatusCard:
    """Report optional embedding configuration without exposing credentials."""
    if settings.embedding_provider == "disabled":
        return AdminStatusCard(state="disabled", value="Disabled", detail="Lexical retrieval remains available")
    label = {"nvidia_nim": "NVIDIA NIM", "openai": "OpenAI", "openai_compatible": "OpenAI-compatible"}.get(settings.embedding_provider, "Configured provider")
    return AdminStatusCard(state="ready", value="Configured · " + label, detail="Server-side embedding configuration is valid; reachability is checked by retrieval")


def collect_admin_status(settings: Settings) -> AdminStatusResponse:
    """Collect the minimum redacted status needed by the owner admin panel."""
    database_ready, database_reason = database_status(settings)
    storage, storage_ready = _storage_status(settings, database_ready, database_reason)
    system_ready = storage_ready and database_ready
    return AdminStatusResponse(
        version=__version__,
        migration_head=CURRENT_MIGRATION_HEAD,
        checked_at=datetime.now(UTC),
        system=AdminStatusCard(state="ready" if system_ready else "degraded", value="Healthy" if system_ready else "Attention needed", detail="Health and readiness checks are passing" if system_ready else "Review storage or migration readiness"),
        ai_provider=_provider_status(settings),
        storage=storage,
        embedding_provider=_embedding_status(settings),
    )
