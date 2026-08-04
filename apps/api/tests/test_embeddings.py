"""Embedding boundary and semantic ranking tests."""

import json
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.embeddings.gateway import embedding_gateway_from_settings, OpenAICompatibleEmbeddingGateway
from app.modules.embeddings.service import cosine_similarity
from app.modules.embeddings.schemas import EmbeddingStatus


def test_nvidia_nim_embedding_uses_hosted_defaults_and_shared_server_key():
    """Hosted NIM embeddings reuse NVIDIA_API_KEY without exposing it to clients."""
    settings = Settings(
        NEXUS_ENV="test",
        TZ="UTC",
        DATA_DIR=".",
        DB_TYPE="sqlite",
        DATABASE_URL="sqlite:///./data/nexus.db",
        JWT_SECRET="test-secret-that-is-longer-than-thirty-two-characters",
        SESSION_COOKIE_SECURE=False,
        CORS_ORIGINS="http://localhost:3000",
        AI_PROVIDER="disabled",
        EMBEDDING_PROVIDER="nvidia_nim",
        NVIDIA_API_KEY=SecretStr("nvidia-server-key"),
        EMBEDDING_MODEL="nvidia/nv-embed-v1",
    )
    assert settings.embedding_base_url == "https://integrate.api.nvidia.com/v1/embeddings"
    assert settings.embedding_api_key is not None
    assert settings.embedding_api_key.get_secret_value() == "nvidia-server-key"
    assert isinstance(embedding_gateway_from_settings(settings), OpenAICompatibleEmbeddingGateway)


def test_nvidia_nim_embedding_requires_a_server_key():
    """NIM embeddings cannot start without a server-side NVIDIA credential."""
    with pytest.raises(ValueError):
        Settings(
            NEXUS_ENV="test",
            TZ="UTC",
            DATA_DIR=".",
            DB_TYPE="sqlite",
            DATABASE_URL="sqlite:///./data/nexus.db",
            JWT_SECRET="test-secret-that-is-longer-than-thirty-two-characters",
            SESSION_COOKIE_SECURE=False,
            CORS_ORIGINS="http://localhost:3000",
            AI_PROVIDER="disabled",
            EMBEDDING_PROVIDER="nvidia_nim",
            EMBEDDING_MODEL="nvidia/nv-embed-v1",
        )


def test_cosine_similarity_ranks_equal_vectors_highest():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 0.0]) == -1.0


def test_embedding_status_never_contains_vector_payload():
    status = EmbeddingStatus(enabled=True, provider="openai", model="embed", dimensions=3, pending=1, ready=2, stale=0, failed=0)
    payload = status.model_dump_json()
    assert "vector" not in payload
    assert "api_key" not in payload


def test_vector_json_is_bounded_shape():
    vector = json.dumps([0.1, 0.2, 0.3])
    assert len(vector) < 100
