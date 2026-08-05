"""Browser-managed NVIDIA NIM setup helpers for the owner admin panel."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.core.runtime_config import RuntimeNimConfig, read_runtime_nim
from app.modules.assistant.gateway import (
    GatewayMessage,
    OpenAICompatibleGateway,
    ProviderDisabledError,
    ProviderRequestError,
    ProviderTimeoutError,
    _PinnedTransport,
    _validate_provider_target,
)
from app.modules.system.schemas import NimChatPreset, NimEmbeddingPreset, NimModelCatalogResponse, NimOptionsResponse

# Hosted NVIDIA API Catalog — OpenAI-compatible base URL.
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_MODELS_URL = f"{NIM_BASE_URL}/models"
NIM_CHAT_ENDPOINT = f"{NIM_BASE_URL}/chat/completions"
NIM_EMBEDDING_ENDPOINT = f"{NIM_BASE_URL}/embeddings"

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
    """Return offline fallback model choices without contacting NVIDIA."""
    return NimOptionsResponse(
        chat_endpoint=NIM_CHAT_ENDPOINT,
        embedding_endpoint=NIM_EMBEDDING_ENDPOINT,
        base_url=NIM_BASE_URL,
        openai_compatible=True,
        chat_models=list(CHAT_PRESETS),
        embedding_models=list(EMBEDDING_PRESETS),
        help_text=(
            "Paste an NVIDIA API Catalog key once. NexusOS loads live models from the OpenAI-compatible "
            "API at integrate.api.nvidia.com/v1/models, encrypts the key on this device, and never stores "
            "it in the browser or database."
        ),
    )


def _resolve_api_key(settings: Settings, api_key: str | None) -> str | None:
    cleaned = (api_key or "").strip()
    if cleaned:
        return cleaned
    runtime = read_runtime_nim(settings.data_dir, settings.jwt_secret.get_secret_value())
    if runtime is not None:
        return runtime.api_key.get_secret_value()
    if settings.ai_provider == "nvidia_nim" and settings.ai_api_key is not None:
        value = settings.ai_api_key.get_secret_value().strip()
        return value or None
    return None


def _humanize_model_id(model_id: str) -> str:
    name = model_id.split("/")[-1] if "/" in model_id else model_id
    return name.replace("-", " ").replace("_", " ").strip().title() or model_id


def _is_embedding_model(model_id: str, owned_by: str | None = None) -> bool:
    haystack = f"{model_id} {owned_by or ''}".lower()
    markers = ("embed", "embedding", "nv-embed", "e5-", "bge-", "retriev")
    return any(marker in haystack for marker in markers)


def _is_likely_chat_model(model_id: str) -> bool:
    lowered = model_id.lower()
    if _is_embedding_model(lowered):
        return False
    # Skip obvious non-chat utility models when possible.
    skip = ("rerank", "guard", "classifier", "tts", "asr", "whisper", "vision-only")
    return not any(token in lowered for token in skip)


def _recommended_chat_id(model_ids: list[str]) -> str | None:
    preferred = (
        "meta/llama-3.1-8b-instruct",
        "meta/llama-3.3-70b-instruct",
        "meta/llama-3.1-70b-instruct",
        "google/gemma-2-9b-it",
    )
    for candidate in preferred:
        if candidate in model_ids:
            return candidate
    return model_ids[0] if model_ids else None


def _recommended_embedding_id(model_ids: list[str]) -> str | None:
    preferred = ("nvidia/nv-embedqa-e5-v5", "nvidia/nv-embed-v1")
    for candidate in preferred:
        if candidate in model_ids:
            return candidate
    return model_ids[0] if model_ids else None


async def _fetch_nvidia_models_payload(api_key: str | None) -> dict[str, Any]:
    """GET the fixed OpenAI-compatible models catalog from NVIDIA."""
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    timeout = httpx.Timeout(30.0)
    # Prefer the same DNS-pinning path as chat, but fall back to plain HTTPS if needed.
    try:
        address = await _validate_provider_target(NIM_MODELS_URL)
        transport = _PinnedTransport(address, max_response_bytes=4_194_304)
        async with httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=False, trust_env=False) as client:
            response = await client.get(NIM_MODELS_URL, headers=headers)
            if response.status_code >= 400:
                raise ValueError(f"nvidia_models_http_{response.status_code}")
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("nvidia_models_invalid")
            return payload
    except ValueError:
        raise
    except (httpx.TimeoutException, ProviderRequestError, httpx.HTTPError, TypeError, OSError):
        pass

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            response = await client.get(NIM_MODELS_URL, headers=headers)
            if response.status_code >= 400:
                raise ValueError(f"nvidia_models_http_{response.status_code}")
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("nvidia_models_invalid")
            return payload
    except httpx.TimeoutException as exc:
        raise ValueError("nvidia_models_timeout") from exc
    except ValueError:
        raise
    except (httpx.HTTPError, TypeError, OSError) as exc:
        raise ValueError("nvidia_models_unavailable") from exc


async def list_nvidia_models(settings: Settings, *, api_key: str | None = None) -> NimModelCatalogResponse:
    """Fetch live models from NVIDIA's OpenAI-compatible /v1/models endpoint.

    The hosted catalog can be listed without a key; a provided/saved key is sent
    when available so key-scoped catalogs still work.
    """
    key = _resolve_api_key(settings, api_key)
    try:
        payload = await _fetch_nvidia_models_payload(key)
    except ValueError:
        # Retry once without Authorization if an invalid key was rejected.
        if key:
            payload = await _fetch_nvidia_models_payload(None)
        else:
            raise

    raw_items = payload.get("data")
    if not isinstance(raw_items, list):
        raise ValueError("nvidia_models_invalid")

    chat_models: list[NimChatPreset] = []
    embedding_models: list[NimEmbeddingPreset] = []
    seen: set[str] = set()
    for item in raw_items[:400]:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id or model_id in seen or len(model_id) > 160:
            continue
        if any(character.isspace() for character in model_id) or any(character in model_id for character in ('"', "'", "\\")):
            continue
        seen.add(model_id)
        owned_by = str(item.get("owned_by") or "").strip() or None
        label = _humanize_model_id(model_id)
        if _is_embedding_model(model_id, owned_by):
            embedding_models.append(
                NimEmbeddingPreset(
                    id=model_id,
                    label=label,
                    description=f"Hosted embedding model from NVIDIA API Catalog{f' · {owned_by}' if owned_by else ''}.",
                    recommended=False,
                )
            )
        elif _is_likely_chat_model(model_id):
            chat_models.append(
                NimChatPreset(
                    id=model_id,
                    label=label,
                    description=f"Hosted chat model from NVIDIA API Catalog{f' · {owned_by}' if owned_by else ''}.",
                    recommended=False,
                )
            )

    chat_models.sort(key=lambda item: item.id.lower())
    embedding_models.sort(key=lambda item: item.id.lower())
    recommended_chat = _recommended_chat_id([item.id for item in chat_models])
    recommended_embedding = _recommended_embedding_id([item.id for item in embedding_models])
    for item in chat_models:
        if item.id == recommended_chat:
            item.recommended = True
            break
    for item in embedding_models:
        if item.id == recommended_embedding:
            item.recommended = True
            break

    if not chat_models and not embedding_models:
        raise ValueError("nvidia_models_empty")

    return NimModelCatalogResponse(
        ok=True,
        base_url=NIM_BASE_URL,
        models_url=NIM_MODELS_URL,
        chat_endpoint=NIM_CHAT_ENDPOINT,
        embedding_endpoint=NIM_EMBEDDING_ENDPOINT,
        openai_compatible=True,
        source="live",
        chat_models=chat_models,
        embedding_models=embedding_models,
        detail=f"Loaded {len(chat_models)} chat and {len(embedding_models)} embedding models from NVIDIA.",
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
