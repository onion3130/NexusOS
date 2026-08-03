"""Source-aware retrieval contract tests."""

from app.modules.notes.schemas import RetrievalResult


def test_retrieval_result_preserves_note_provenance():
    result = RetrievalResult(source_type="note", source_id="n1", chunk_id="c1", title="Source", excerpt="Untrusted source text", score=-1.0, source_version=2, updated_at="2026-08-03T00:00:00Z", metadata={"content_hash": "abc"})
    assert result.source_type == "note"
    assert result.metadata["content_hash"] == "abc"
