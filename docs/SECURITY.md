# NexusOS security baseline

**Status:** v1.5 external source ingestion is implemented alongside the local-first security boundaries; public-internet deployment remains out of scope.
**Last updated:** 2026-08-04

## Runtime boundaries

- The browser never receives provider keys, database credentials, Docker socket access, or unrestricted host paths. Admin status returns only allowlisted state/value/detail fields and never raw environment values. The owner-only NVIDIA NIM setup form sends the key over the authenticated same-origin API, encrypts it at rest beneath the private data volume using a key derived from the server JWT secret, and never stores or echoes the plaintext key.
- The API is the authorization boundary; frontend visibility is not authorization. The owner-only admin status panel requires `admin.manage_users` server-side, and the frontend condition is only a presentation optimization.
- Task and note services filter every owned entity by the authenticated user.
- FTS5 results are joined back to canonical notes with user and deletion filters; derived chunks carry a direct user boundary.
- The worker has no browser-facing port and performs only bounded database-backed reminder delivery.
- No arbitrary shell text, SQL, Docker arguments, filesystem paths, reboot/shutdown requests, package operations, systemd controls, or provider URLs are accepted from model output or the browser.
- Host-action execution uses fixed Python/SQLite adapters. Plugin execution is the separate, non-privileged JSON-stdio broker: no shell, confined approved entrypoints, a minimal secret-free environment, bounded output/time, and Linux resource limits. Plugins are trusted operator-installed code, not a hostile-code sandbox.

## External source controls

- Uploads accept only bounded UTF-8 `.txt`, `.md`, and `.markdown` content. PDF, executable, credential-like, binary, empty, and oversized files are rejected.
- Uploaded bytes are stored beneath the server-owned `DATA_DIR/sources` directory using generated IDs; client filenames are metadata only and never become storage paths.
- Approved-file imports expose opaque IDs from server-configured roots. The server rechecks root confinement, symlink state, size, digest, and UTF-8 decoding before copying.
- Source records, versions, chunks, and ingestion jobs are user-scoped; source mutations require permissions, cookie CSRF, idempotency conventions, and audit events.
- Worker ingestion verifies the stored SHA-256, uses bounded reads/chunks/retries, and records redacted error codes. Source content is never executed or rendered as trusted HTML.
- External source chunks are treated as untrusted prompt context and cannot authorize tools, permissions, host actions, or policy changes.

## Notes, search, and retrieval controls

- Embeddings are disabled by default and can be enabled only through server configuration.
- Embedding vectors are user-scoped derived data; vector payloads, provider credentials, and raw upstream responses never leave the server or appear in logs.
- Semantic and hybrid retrieval require `notes.semantic`, enforce note/chunk ownership, exclude deleted notes, and fall back to lexical results when the provider or index is unavailable.
- Provider endpoints are validated as HTTP(S) URLs without credentials and are subject to bounded request/response and timeout policies. Browser-managed NIM always uses the hosted NVIDIA API Catalog endpoints; the browser cannot choose an arbitrary provider URL.


- Notes require `notes.read` for reads/search, `notes.write` for create/update/archive/restore, and `notes.delete` for soft deletion.
- Note mutations require CSRF for cookie-authenticated clients, payload-bound idempotency, ownership checks, and audit events.
- Search queries are bounded, parameterized, and normalized; raw FTS5 syntax is not exposed.
- Note content is rendered as text and is never trusted HTML.
- Retrieved note content is untrusted source material, escaped before context assembly, explicitly delimited, bounded by source count and context size, and cannot change system instructions, permissions, or tool authorization.
- Grounding requires `notes.read`; semantic and hybrid modes require `notes.semantic`. Grounding is skipped when chat AI is disabled, so a disabled deployment does not contact an embedding provider unexpectedly.
- Assistant source provenance is derived server-side, user-scoped, and exposes metadata only; the source endpoint verifies conversation/message ownership.

## Task and assistant mutation controls

- Task, category, tag, reminder, and notification mutations require authentication.
- Cookie-authenticated mutations require CSRF headers.
- Task routes require action-specific permissions.
- Assistant task writes require `assistant.task_actions` plus task permissions.
- Assistant proposals expire after a bounded period and require explicit approval.
- Rejection never invokes the task service.
- Task deletion is soft deletion and is audited.
- All task changes, reminder changes, notification state changes, and assistant approvals/rejections create bounded audit events.

## Workspace view controls

- Files, Projects, Git, and Docker routes require `workspace_views.read` server-side.
- `WORKSPACE_ROOTS` is the only source of filesystem/project/repository roots; clients cannot submit paths.
- Files are bounded by depth and item count, exclude symlinks and common credential filenames, and return relative paths only.
- Git uses fixed `git -C` argument lists, `shell=False` behavior, short timeouts, bounded output, and no mutation commands. Remotes and credentials are never returned.
- Docker metadata is unavailable by default. If enabled, it requires an operator-supplied Unix socket boundary and returns only an allowlisted subset of container metadata; environment variables, mounts, commands, and raw inspect output are excluded. A Unix socket `:ro` filesystem mount does not restrict Docker API capabilities, so socket access remains a powerful host-control boundary; use only on a trusted host, preferably through a filtered/rootless proxy.
- Workspace view output is treated as untrusted host metadata and is rendered as text in the browser and assistant context.

## Host-action and recovery controls

- `system.host_actions`, `system.backups.read`, and `system.audit.read` are enforced server-side.
- Proposal creation never executes an operation. Every enabled action requires explicit confirmation, even when proposed by the assistant.
- Proposals expire after ten minutes, are user-scoped, and use idempotency keys to prevent duplicate queues.
- Worker jobs are durable, bounded, claimable, and audited at proposal, confirmation, rejection, success, and failure transitions.
- Backup files are created only beneath `DATA_DIR/backups`; clients cannot supply a path or filename.
- Backup metadata includes a SHA-256 digest and SQLite `integrity_check` result. When configured, off-host artifacts use bounded AES-256-GCM chunks with unique nonces and authenticated sequence/size metadata; backup contents and encryption keys are never returned by the API.
- Restore is enabled only through the same proposal/confirmation pipeline and runs solely in the worker. The source must be an owned backup with `status == "verified"`; the worker creates a verified safety backup of the live database first, stages the source (decrypting off-host artifacts in bounded authenticated chunks), re-verifies SHA-256 and `integrity_check` before replacing anything, and swaps atomically with rollback to the safety backup on failure. Client input is limited to `backup_id`; no paths, commands, or destinations are accepted. A successful restore requires an API/worker restart, which the API and UI surface explicitly.
- Retention cleanup is enabled only through the same proposal/confirmation pipeline and runs solely in the worker. It accepts no input; the policy comes from `BACKUP_RETENTION_COUNT` / `BACKUP_RETENTION_DAYS`, the newest verified backup is always retained, and a local artifact is deleted only when its digest still matches the trusted record (tampered material is reported and kept). Encrypted off-host artifacts are pruned only when the replication destination is configured, and every prune is a soft-delete with an audit row. Manual backup deletion, per-backup selection, and public object-storage upload are not enabled. Directory replication is operator-mounted, opt-in, encrypted, and never accepts a client-selected destination.
- Key rotation is enabled only through a high-risk confirmed action. Both keys are environment-only (`BACKUP_REPLICATION_KEY_PREVIOUS` and `BACKUP_ENCRYPTION_KEY`), must differ, never cross the API or database, and artifacts are re-encrypted in bounded authenticated chunks with atomic replace and staging cleanup; an interrupted rotation is idempotent.
- The worker remains non-root with no published port, no Docker socket, and no privileged host mount.

## Input and data safety

- Titles, descriptions, tags, categories, reminders, notification bodies, list limits, and recurrence structures are bounded.
- Persisted timestamps must include timezone offsets and are normalized to UTC.
- Recurrence supports only the version-one daily, weekly, and monthly structure; arbitrary RRULE text is not accepted.
- Notifications use deterministic deduplication keys to prevent worker restart duplicates.
- Search projections and retrieval chunks are derived from canonical notes and are rebuildable rather than authoritative.
- Task and notification content is rendered as text, not trusted HTML.
- Secrets, tokens, provider keys, raw authorization headers, and raw upstream payloads are never persisted in task records or ordinary logs.

## Authentication and deployment

- Passwords use Argon2id.
- Sessions are tracked, rotated, revocable, and protected by CSRF for cookies.
- Production cookies must be Secure and HttpOnly.
- The worker and API run as non-root ARM64 containers on a private network.
- Ports remain loopback-only in the development topology. The hardened profile publishes only the Caddy proxy, uses a read-only proxy filesystem with minimal capabilities, and requires a private hostname plus trusted internal certificate policy.
- The external SSD is primary storage, not the only backup.

## Remaining hardening

- Idempotency keys cover task, reminder, category, tag, notification, and assistant approval mutations; callers must reuse the same key when retrying a request, and payload mismatches are rejected.
- Standard error envelopes and request IDs remain future hardening.
- Backup-before-migration orchestration, production monitoring, and image pinning remain deployment work. The hardened profile supplies opt-in TLS, systemd startup, resource limits, and encrypted directory replication.

## Change checklist

Before merging a feature:

1. Identify new secrets/configuration and add placeholders only to `.env.example`.
2. Confirm no credential-shaped literals or personal data are present.
3. Confirm authentication, ownership, CSRF, permissions, and audit requirements.
4. Define timeout, retry, lease, deduplication, and redaction behavior.
5. Run backend tests, frontend typecheck/build, Compose validation, secret scanning, and `git diff --check`.
6. Review the complete diff and staged file list.
7. Treat the configured AES-256 key as unrecoverable secret material: rotate only through the confirmed rotation action (set `BACKUP_REPLICATION_KEY_PREVIOUS`, run the action, then remove it) and keep the old key until all artifacts are re-encrypted.
