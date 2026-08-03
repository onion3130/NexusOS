# NexusOS AI system

**Current milestone:** v1.0 release hardening complete
**Status:** The bounded assistant gateway, conversation storage, provider normalization, read-only system/task/note tools, confirmation-gated task mutations, lexical search, source-aware note chunks, and confirmation-gated maintenance proposals are implemented. Embeddings, autonomous memory, semantic RAG, streaming, and privileged host control remain deferred.
**Last updated:** 2026-08-03

## Current behavior

- `AI_PROVIDER=disabled` remains the safe default.
- Provider credentials stay server-side.
- The gateway normalizes bounded provider requests and responses.
- The registry exposes only tools allowed by the authenticated user's permissions.
- `system.get_overview` remains read-only and argument-free.
- Task mutations and maintenance proposals are persisted and require explicit user approval.

## Implemented note tools

- `notes.search`: bounded search of owned notes with source-aware excerpts
- `notes.read`: bounded read of one owned note as untrusted source material

Note content never grants permissions or triggers tool execution. The tools use the same ownership-scoped notes service as REST routes.

## Implemented task tools

- `tasks.list`: read-only lookup of owned tasks
- `tasks.create`: confirmation-gated task creation
- `tasks.update`: confirmation-gated task update
- `tasks.complete`: confirmation-gated task completion
- `tasks.delete`: confirmation-gated soft deletion

Approval and rejection are authenticated, ownership-scoped, CSRF-protected for cookies, expiry-bounded, permission-checked, typed, and audited. The same task service is used by REST routes and assistant tools.

## Implemented maintenance tool

- `maintenance.request_backup`: creates a user-visible proposal for a database backup; it does not queue or execute the backup. The browser confirmation workflow remains mandatory.

The assistant cannot request arbitrary commands, paths, Docker operations, reboot, shutdown, package management, systemd controls, or restore. Maintenance actions use the same permission and audit boundary as direct API requests.

## Tool-calling lifecycle

```text
user message
  -> validate and persist
  -> assemble authorized context
  -> model proposes typed call
  -> validate schema and permissions
  -> persist proposed call with expiry
  -> show confirmation UI
  -> approve or reject
  -> execute fixed task/maintenance service adapter after confirmation
  -> sanitize result and audit event
```

No tool may execute arbitrary shell text, SQL, Docker commands, filesystem paths, or provider URLs. AI output is untrusted input.

## Retrieval and memory foundation

Milestone 7 introduces lexical, provider-neutral retrieval results containing source type, source ID, chunk ID, title, excerpt, source version, update time, and bounded metadata. Note chunks are deterministic and versioned. No embedding model, vector index, autonomous memory extraction, or model-written note is enabled.

If retrieved note text is later added to model context, it must be explicitly delimited as untrusted user-authored reference material. It cannot alter system instructions or bypass confirmation-gated task actions.

## Deferred AI work

- Streaming responses
- Provider health dashboards
- Semantic source-aware retrieval
- Memory and RAG
- Additional integrations
- Privileged host control, restore, and backup replication

See [`API.md`](API.md), [`DATABASE.md`](DATABASE.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), and [`ROADMAP.md`](ROADMAP.md).
