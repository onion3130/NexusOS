# NexusOS AI system

**Current milestone:** v1.2 — semantic retrieval foundation
**Status:** The bounded assistant gateway, conversation storage, provider normalization, read-only system/task/note/workspace-view tools, calendar/finance/media services, confirmation-gated task and maintenance mutations, lexical search, source-aware note chunks, optional embeddings, semantic/hybrid retrieval, outbound email/push delivery, and the always-confirmed out-of-process plugin tool are implemented. Autonomous memory, external ingestion, streaming, and privileged host control remain deferred.
**Last updated:** 2026-08-04

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

## Implemented workspace view tools

- `files.recent`: bounded metadata from approved roots
- `projects.list`: safe project metadata
- `git.repositories`: read-only repository status
- `docker.containers`: sanitized container metadata when the optional, trusted socket boundary is available; socket access is not a Docker API sandbox

These tools require `workspace_views.read`, share the REST service layer, return bounded untrusted metadata, and cannot write files, mutate Git, control containers, or execute commands.

## Implemented plugin tool

- `plugins.invoke`: always-confirmed invocation of a declared capability on an enabled plugin. The API verifies the plugin and method against the server-owned manifest, then runs it through the out-of-process broker. Every capability, including read-labeled capabilities, requires explicit confirmation because a manifest label cannot prove that code has no side effects.

Plugin results are bounded and treated as untrusted data. Plugin credentials and application secrets are never passed to the subprocess.

## Implemented maintenance tool

- `maintenance.request_backup`: creates a user-visible proposal for a database backup; it does not queue or execute the backup. The browser confirmation workflow remains mandatory.

The assistant cannot request arbitrary commands, paths, Docker operations, reboot, shutdown, package management, systemd controls, or restore. Restore is a high-risk maintenance action that runs only after an explicit browser/API confirmation; maintenance actions use the same permission and audit boundary as direct API requests.

Outbound notification channel delivery (email/push) is not an assistant tool. The assistant cannot trigger, configure, or test notification channels; delivery is scheduled by the dedicated worker only.

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

Milestone 7 introduced lexical, provider-neutral retrieval results containing source type, source ID, chunk ID, title, excerpt, source version, update time, and bounded metadata. v1.2 adds optional provider-neutral embeddings for those chunks, bounded serialized-vector similarity, hybrid scoring, stale-content detection, and lexical fallback. Semantic retrieval is read-only and disabled unless explicitly configured. No autonomous memory extraction or model-written note is enabled.

If retrieved note text is later added to model context, it must be explicitly delimited as untrusted user-authored reference material. It cannot alter system instructions or bypass confirmation-gated task actions.

## Deferred AI work

- Streaming responses
- Provider health dashboards
- Autonomous semantic memory and model-written notes
- Autonomous memory and model-written notes
- Additional integrations
- Privileged host control, assistant-triggered restore, cloud/object-storage replication, and autonomous memory

See [`API.md`](API.md), [`DATABASE.md`](DATABASE.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), and [`ROADMAP.md`](ROADMAP.md).
