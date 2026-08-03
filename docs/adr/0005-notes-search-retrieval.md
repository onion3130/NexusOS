# ADR 0005: Canonical notes with SQLite FTS5 and provenance-preserving retrieval

- **Status:** Accepted
- **Date:** 2026-08-03

## Decision

Milestone 7 adds a user-owned notes module to the existing modular monolith. Canonical notes are stored in SQLite and shared user-owned tags are reused from Milestone 6. A derived search projection feeds SQLite FTS5 for bounded lexical search. Deterministic, versioned note chunks preserve source IDs, offsets, hashes, and provenance for future RAG work.

The source table is authoritative. Search projections and chunks are derived and rebuildable. Assistant integration is read-only through `notes.search` and `notes.read`; embeddings, autonomous memory extraction, external ingestion, and model-written notes remain deferred.

## Rationale

NexusOS targets a Raspberry Pi 5 with an external SSD and must remain useful without an AI provider. SQLite FTS5 provides local search without introducing an always-on search service. Versioned chunks establish a stable retrieval contract before choosing an embedding provider or vector storage design.

## Security consequences

All notes, tags, search results, and chunks are filtered by authenticated user ownership. Search queries are normalized and parameterized rather than exposing raw FTS syntax. Note content is untrusted text: it cannot grant permissions, modify instructions, or trigger assistant tools. Browser mutations retain CSRF, permissions, audit, and idempotency controls.

## Operational consequences

Indexing and chunk generation are synchronous within note mutations to avoid stale visibility and another worker process. SQLite FTS5 must be available in the target Python runtime. Search and chunk data live on the SSD-backed database volume and can be rebuilt after recovery. Runtime FTS5 and ARM64 validation remain deployment checks.
