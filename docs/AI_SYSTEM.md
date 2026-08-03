# NexusOS AI system

**Current milestone:** Milestone 6 — task actions implemented
**Status:** The bounded assistant gateway, conversation storage, provider normalization, read-only system tool, task read tool, and confirmation-gated task mutation lifecycle are implemented. Streaming, memory, RAG, and host actions remain deferred.
**Last updated:** 2026-08-03

## Current behavior

- `AI_PROVIDER=disabled` remains the safe default.
- Provider credentials stay server-side.
- The gateway normalizes bounded provider requests and responses.
- The registry exposes only tools allowed by the authenticated user's permissions.
- `system.get_overview` remains read-only and argument-free.
- Task mutations are persisted as proposals and require explicit user approval.

## Implemented task tools

- `tasks.list`: read-only lookup of owned tasks
- `tasks.create`: confirmation-gated task creation
- `tasks.update`: confirmation-gated task update
- `tasks.complete`: confirmation-gated task completion
- `tasks.delete`: confirmation-gated soft deletion

Approval and rejection are authenticated, ownership-scoped, CSRF-protected for cookies, expiry-bounded, permission-checked, typed, and audited. The same task service is used by REST routes and assistant tools.

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
  -> execute fixed task service adapter
  -> sanitize result and audit event
```

No tool may execute arbitrary shell text, SQL, Docker commands, filesystem paths, or provider URLs. AI output is untrusted input.

## Deferred AI work

- Streaming responses
- Provider health dashboards
- Source-aware retrieval
- Memory and RAG
- Additional integrations
- Host actions

See [`API.md`](API.md), [`DATABASE.md`](DATABASE.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), and [`ROADMAP.md`](ROADMAP.md).
