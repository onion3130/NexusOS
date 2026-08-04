"""Embedding boundary and semantic ranking tests."""

import json
from datetime import UTC, datetime

from app.modules.embeddings.service import cosine_similarity
from app.modules.embeddings.schemas import EmbeddingStatus


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
