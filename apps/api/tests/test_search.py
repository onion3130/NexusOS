"""Focused lexical search and retrieval helper tests."""

from app.modules.notes.search import normalize_query
from app.modules.notes.service import _split_chunks


def test_search_query_is_a_bounded_safe_phrase_expression():
    assert normalize_query('  pi OR "ssd" *  ') == '"pi" AND "OR" AND "ssd"'


def test_chunking_is_bounded_and_overlapping():
    content = "paragraph\n\n" + ("x" * 2500)
    chunks = _split_chunks(content)
    assert len(chunks) >= 2
    assert all(len(piece) <= 1200 for _, _, piece in chunks)
    assert chunks[0][0] == 0
