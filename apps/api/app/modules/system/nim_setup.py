"""Browser-managed NVIDIA NIM setup helpers for the owner admin panel."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from pydantic import SecretStr

from app.core.config import Settings
from app.core.runtime_config import RuntimeNimConfig, read_runtime_nim
from app.modules.assistant.gateway import (
    GatewayMessage,
    OpenAICompatibleGateway,
    ProviderDisabledError,
    ProviderRequestError,
    ProviderTimeoutError,
)
from app.modules.system.schemas import NimChatPreset, NimEmbeddingPreset, NimOptionsResponse

NIM_CHAT_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_EMBEDDING_ENDPOINT = "https://integrate.api.nvidia.com/v1/embeddings"

CHAT_PRESETS: tuple[NimChatPreset, ...] = (
    NimChatPreset(
        id="meta/llama-3.1-8b-instruct",
        label="Llama 3.1 8B Instruct",
        description="Fast everyday assistant for tasks, notes, and system questions.",
        recommended=True,
    ),
    NimChatPreset(
        id="meta/llama-3.1-70b-instruct",
        label="Llama 3.1 70B Instruct",
        description="Higher quality answers; usually slower and more expensive.",
    ),
    NimChatPreset(
        id="meta/llama-3.3-70b-instruct",
        label="Llama 3.3 70B Instruct",
        description="Strong general model for deeper reasoning and writing.",
    ),
    NimChatPreset(
        id="mistralai/mistral-nemotron",
        label="Mistral Nemotron",
        description="NVIDIA-hosted Mistral option for general chat.",
    ),
    NimChatPreset(
        id="google/gemma-2-9b-it",
        label="Gemma 2 9B Instruct",
        description="Compact instruction model for lightweight assistant use.",
    ),
)

EMBEDDING_PRESETS: tuple[NimEmbeddingPreset, ...] = (
    NimEmbeddingPreset(
        id="nvidia/nv-embedqa-e5-v5",
        label="NV-EmbedQA E5 v5",
        description="Recommended for semantic note search and hybrid retrieval.",
        recommended=True,
    ),
    NimEmbeddingPreset(
        id="nvidia/nv-embed-v1",
        label="NV-Embed v1",
        description="General NVIDIA embedding model for private note retrieval.",
    ),
)


def nim_options() -> NimOptionsResponse:
    """Return beginner-safe model choices without contacting NVIDIA."""
    return NimOptionsResponse(
        chat_endpoint=NIM_CHAT_ENDPOINT,
        embedding_endpoint=NIM_EMBEDDING_ENDPOINT,
        chat_models=list(CHAT_PRESETS),
        embedding_models=list(EMBEDDING_PRESETS),
        help_text=(
            "Create an NVIDIA API Catalog key at build.nvidia.com, then paste it here. "
            "NexusOS encrypts the key on this device, never stores it in the browser or database, "
            "and never requires SSH for normal NIM setup."
        ),
    )


def resolve_runtime_config(
    settings: Settings,
    *,
    api_key: str | None,
    model: str,
    embeddings_enabled: bool,
    embedding_model: str | None,
) -> RuntimeNimConfig:
    """Build a validated runtime config, reusing the stored key when omitted."""
    existing = read_runtime_nim(settings.data_dir, settings.jwt_secret.get_secret_value())
    cleaned_key = (api_key or "").strip()
    if cleaned_key:
        secret = SecretStr(cleaned_key)
    elif existing is not None:
        secret = existing.api_key
    else:
        raise ValueError("api_key is required for the first NVIDIA NIM setup")
    if embeddings_enabled and not (embedding_model or "").strip():
        raise ValueError("embedding_model is required when embeddings are enabled")
    return RuntimeNimConfig(
        api_key=secret,
        model=model,
        embeddings_enabled=embeddings_enabled,
        embedding_model=embedding_model if embeddings_enabled else None,
    )


@dataclass(frozen=True)
class NimTestResult:
    """Bounded connection-test outcome without secrets."""

    ok: bool
    detail: str
    model: str | None = None
    embeddings_tested: bool = False


def _test_settings(*, api_key: str, model: str) -> SimpleNamespace:
    """Minimal settings surface for a one-shot hosted NIM connectivity check."""
    return SimpleNamespace(
        ai_provider="nvidia_nim",
        ai_base_url=NIM_CHAT_ENDPOINT,
        ai_api_key=SecretStr(api_key),
        ai_model=model,
        ai_timeout_seconds=20,
        ai_max_output_tokens=8,
        ai_max_response_bytes=65_536,
    )


async def test_nim_connection(
    settings: Settings,
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> NimTestResult:
    """Send one bounded completion to verify the key and model without echoing secrets."""
    runtime = read_runtime_nim(settings.data_dir, settings.jwt_secret.get_secret_value())
    cleaned_key = (api_key or "").strip()
    if cleaned_key:
        key = cleaned_key
    elif runtime is not None:
        key = runtime.api_key.get_secret_value()
    elif settings.ai_provider == "nvidia_nim" and settings.ai_api_key is not None:
        key = settings.ai_api_key.get_secret_value()
    else:
        return NimTestResult(ok=False, detail="Add an NVIDIA API key before testing the connection.")

    chosen_model = (model or "").strip() or (runtime.model if runtime is not None else None) or settings.ai_model
    if not chosen_model:
        return NimTestResult(ok=False, detail="Choose a chat model before testing the connection.")

    gateway = OpenAICompatibleGateway(_test_settings(api_key=key, model=chosen_model))  # type: ignore[arg-type]
    try:
        await gateway.complete(
            [GatewayMessage(role="user", content="Reply with the single word OK.")],
            tools=[],
        )
    except ProviderTimeoutError:
        return NimTestResult(ok=False, detail="NVIDIA NIM timed out. Check outbound internet access from the Pi.", model=chosen_model)
    except ProviderDisabledError:
        return NimTestResult(ok=False, detail="AI is currently disabled.", model=chosen_model)
    except ProviderRequestError:
        return NimTestResult(
            ok=False,
            detail="NVIDIA NIM rejected the request. Check the API key, model name, and NVIDIA account access.",
            model=chosen_model,
        )
    return NimTestResult(
        ok=True,
        detail="Connection successful. The Assistant can use this NVIDIA NIM model.",
        model=chosen_model,
    )
