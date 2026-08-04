# NexusOS roadmap

**Current milestone:** v1.5 — external source ingestion and source lifecycle management (unreleased)
**Next milestone:** v1.6 — source synchronization, richer document parsing, and streaming Assistant responses
**Last updated:** 2026-08-04

This roadmap is the source of truth for sequencing. Do not implement a later milestone because its design appears in another document.

## Checkpoint status — 2026-08-03

Milestone 6 is implemented within its approved scope. NexusOS now has an authenticated task API and frontend workspace, categories, tags, due dates, priorities, constrained recurring tasks, reminders, persistent in-app notifications, a dedicated SQLite-backed reminder worker, and confirmation-gated assistant task actions. AI remains disabled by default, and the stack remains loopback-only development infrastructure rather than a production deployment.

## Status summary

| Milestone | Status | Outcome |
|---|---|---|
| 0. Architecture and public foundation | Complete | Repository rules, architecture, security baseline, and documentation |
| 1. ARM64 application foundation | Complete | API health service, foundation web shell, Compose, validation, tests |
| 2. Identity and persistence | Complete | Owner bootstrap, SQLite/Alembic, sessions, auth boundary |
| 3. Dashboard shell and design system | Complete | Authenticated navigation, shared UI primitives, accessible states |
| 4. System read-only module | Complete | Authenticated Pi telemetry with safe unavailable service/container boundary |
| 5. Assistant gateway | Complete | Conversations, bounded provider gateway, read-only system tool, assistant UI |
| 6. Tasks and reminders | Complete | Tasks, due dates, priorities, categories, tags, recurrence, reminders, notifications, worker, assistant actions |
| 7. Notes and scoped search | Complete | Notes, tags, SQLite FTS5 search, source-aware retrieval chunks, assistant read tools |
| 8. Safe host actions | Complete | Confirmation-gated maintenance actions, audit events, verified SQLite backups, and recovery documentation |
| 9. Files, projects, Git, Docker views | Complete | Approved roots, repository/project metadata, sanitized Docker read operations |
| 10. Deployment hardening | Complete | Hardened LAN proxy, systemd startup, encrypted replication, resource limits, and recovery gate |
| 11. Integrations and plugins | Complete | Calendar, finance, media, outbound notification channels, and the out-of-process plugin boundary |

| 12. Restore and recovery automation | Complete | Confirmation-gated restore from verified local and encrypted off-host backup artifacts with safety backup, staging, digest/integrity verification, and atomic swap |
| 13. Backup retention and lifecycle | Complete | Policy-driven retention cleanup with last-backup protection, digest-safe pruning of local and encrypted artifacts, and confirmation-gated AES-256 key rotation |
| 15. External source ingestion | In progress | Bounded text/Markdown uploads, approved-file imports, versioned ingestion, source-aware retrieval, and lifecycle controls |

## Milestone 6 complete — tasks, reminders, and notifications

Implemented:

- Reversible Alembic migration `0003_tasks_notifications`.
- User-owned tasks with titles, descriptions, due dates, priorities, statuses, categories, and tags.
- Daily, weekly, and monthly constrained recurrence rules with future-occurrence generation.
- Absolute and due-date-relative reminders.
- Persistent in-app notifications with deterministic deduplication.
- Dedicated ARM64-compatible SQLite worker with bounded reminder batches and lease recovery.
- Authenticated task, category, tag, reminder, and notification routes with CSRF, permission, ownership, and audit boundaries.
- Responsive task workspace and notification center.
- Read-only assistant task lookup plus confirmation-gated create, update, complete, delete, approve, and reject actions.
- Backend migration, task, recurrence, worker, ownership, CSRF, and assistant policy tests.

Known limitations:

- Notifications are in-app only; email, SMS, push, and calendar integrations remain deferred.
- The current recurrence UI creates daily recurrence; the API supports daily, weekly, and monthly rules.
- Idempotency keys cover task, reminder, category, tag, notification, and assistant approval mutations; payload mismatches are rejected and standardized error envelopes remain later hardening work.
- Docker and Raspberry Pi runtime validation require an environment with Docker and the target Pi; local source validation is green.

## Milestone 7 complete — notes, search, and retrieval foundations

Implemented:

- User-owned notes with tags, active/archived states, content versions, and soft deletion.
- SQLite FTS5-backed lexical search over note titles, content, and tags with bounded safe queries and source-aware excerpts.
- Deterministic note retrieval chunks with source IDs, offsets, content hashes, and version provenance.
- Authenticated notes/search/chunk routes with ownership, CSRF, permissions, audit, and idempotency boundaries.
- Read-only assistant `notes.search` and `notes.read` tools; no autonomous memory or note writes.
- Responsive Notes and Search workspaces with mobile-friendly editing, archive/delete controls, and command-palette search.

Known limitations:

- Retrieval is lexical only; embeddings, vector search, autonomous memory extraction, and external ingestion remain deferred.
- FTS5 and target Raspberry Pi runtime validation require Docker-enabled ARM64 hardware.
- Note content is intentionally rendered as text; rich Markdown/HTML rendering remains deferred.

## Milestone 8 complete — safe host actions and recovery foundations

Implemented:

- Reversible Alembic migration `0005_host_actions` for durable action proposals and backup metadata.
- A server-owned allowlist for SQLite backup creation, backup verification, and database integrity checks.
- Explicit confirmation workflows with expiring proposals, CSRF, permissions, idempotency, durable jobs, and auditable lifecycle transitions.
- A non-root worker adapter using Python SQLite backup APIs; no arbitrary shell, Docker socket, filesystem path, reboot, shutdown, package, or systemd control.
- Verified backup metadata with relative paths, SHA-256 hashes, SQLite integrity results, and user-scoped API visibility.
- Authenticated maintenance workspace with review/confirm/reject states, job progress, backup history, and audit history.
- Confirmation-gated assistant `maintenance.request_backup` proposal tool; assistants cannot bypass the same user confirmation flow.
- Recovery and Raspberry Pi/Docker deployment documentation.

Known limitations:

- Automated restore, encrypted/off-host backup replication, retention cleanup, and last-backup deletion protection remain deployment work.
- The current action catalog intentionally excludes reboot, shutdown, package management, systemd, Docker, arbitrary commands, and dynamic paths.
- Docker runtime and sustained-load validation still require a Docker-enabled Raspberry Pi 5 or ARM64 host.

## v1.0 release hardening complete

Implemented:

- Version metadata is aligned at `1.0.0` across API, web, and health responses.
- Worker leases reclaim stale host-action jobs and stop after three bounded attempts with audit events.
- Backup creation is confined to the configured data volume, retry-idempotent by job, and verification detects digest tampering without silently trusting altered files.
- Migration `0006_v1_hardening` adds composite indexes for reminder and host-action claim scans.
- Docker, ARM64, recovery, migration-head, and release validation guidance is synchronized.

The v1.0 release remains private/local-first: reverse-proxy TLS, encrypted off-host replication, restore drills, and systemd orchestration remain operational follow-up work rather than hidden claims.

## Milestone 9 complete — files, projects, Git, and Docker views

Implemented:

- Reversible Alembic migration `0007_workspace_views` for the dedicated `workspace_views.read` permission.
- Bounded read-only Files, Projects, Git, and Docker API views.
- Server-configured approved roots through `WORKSPACE_ROOTS`; request paths are never accepted.
- Sensitive filename filtering, symlink exclusion, depth/item bounds, and relative-path responses.
- Fixed-command Git inspection with timeouts, bounded output, and no mutation operations.
- Optional sanitized Docker metadata through an explicitly supplied Unix socket boundary; Docker inspection is unavailable by default.
- Read-only assistant tools for recent files, projects, Git repositories, and Docker containers.
- Responsive Files, Projects, Git, and Docker workspaces with loading, empty, unavailable, retry, and read-only boundary states.
- Backend security, adapter, permission, authentication, migration, and read-only behavior coverage.

Known limitations:

- File views expose metadata only; file content reading and editing remain deferred.
- Project discovery uses safe direct-child markers and does not execute project tooling.
- Docker health/restart details are intentionally limited to metadata returned by the read-only container listing endpoint.
- The default Compose topology does not mount the Docker socket; Docker views remain unavailable until an operator creates a separately reviewed socket boundary. A filesystem read-only mount does not limit Docker API capabilities.

## Milestone 10 — deployment hardening

Implemented:

- Opt-in hardened Compose overlay with ARM64 Caddy internal TLS, private upstream routing, direct API/web port removal, and bounded service resources.
- Raspberry Pi systemd unit with Docker/SSD dependencies, startup/shutdown commands, and documented upgrade/rollback procedure.
- Reversible migration `0008_deployment_hardening` for encrypted/off-host backup metadata.
- Provider-neutral operator-mounted destination adapter with bounded AES-256-GCM chunk encryption, unique nonces, authenticated metadata, atomic writes, verification, leases, retries, and idempotent job keys.
- Authenticated deployment status and Maintenance UI replication/encryption visibility.
- Environment validation requiring the replication destination and 256-bit key as a pair; replication remains disabled by default.

Known limitations:

- The current adapter targets an operator-mounted destination directory; object-storage providers remain future integrations.
- Restore remains an operator-controlled procedure and requires a real Pi restore drill.
- Certificate trust installation, Docker image builds, cold-boot behavior, retention, key rotation, and production monitoring require target-environment validation.

## Milestone 13 complete — backup retention and lifecycle policy

Implemented:

- Reversible Alembic migration `0011_backup_lifecycle` adding `backup_records.pruned_at`; pruned records are soft-deleted (status `deleted`) and excluded from the backup listing.
- Server-configured retention policy (`BACKUP_RETENTION_COUNT`, default 7, and `BACKUP_RETENTION_DAYS`, default 30) with a read-only `GET /api/v1/system/backups/retention-preview` endpoint.
- A `maintenance.retention_cleanup` action (risk `medium`) that prunes verified backups beyond the policy. The newest verified backup is always retained (last-backup protection); a local artifact is deleted only when its digest still matches the trusted record, encrypted off-host artifacts are deleted when the replication destination is configured, and every prune is audited.
- A `maintenance.rotate_encryption_key` action (risk `high`) that re-encrypts every replicated artifact from `BACKUP_REPLICATION_KEY_PREVIOUS` to the current `BACKUP_ENCRYPTION_KEY` in bounded authenticated chunks with atomic replace, staging cleanup, idempotent retries, and audit rows.
- Maintenance workspace lifecycle panel with the current policy, a prune preview, the retention cleanup action, and the rotation action (shown when replication is configured).
- Backend tests covering retention boundaries, last-backup protection, digest-safe pruning, path confinement, fail-closed encrypted pruning, rotation idempotency, the preview endpoint, and both proposal pipelines.

Known limitations:

- Retention cleanup is policy-driven but still requires explicit confirmation; unattended scheduled pruning is deliberately not enabled because every destructive NexusOS operation requires confirmation.
- Retention considers only `verified` records and deliberately skips digest-mismatched artifacts, so tampered or failed backups and their files are never pruned and can accumulate in the data volume; a future failed-artifact cleanup policy is planned.
- Pruning an encrypted artifact requires `BACKUP_REPLICATION_DESTINATION` to be configured on the pruning host; otherwise the action fails closed before deleting anything.
- Key rotation requires the operator to set `BACKUP_REPLICATION_KEY_PREVIOUS` in the server environment, run the action, then remove it; this keeps keys out of the API and database.

## Milestone 12 complete — restore and recovery automation

Implemented:

- Reversible Alembic migration `0010_restore` adding `backup_records.restored_at`.
- A new `maintenance.restore_backup` catalogued action (risk `high`) accepting only a `backup_id`; server-side resolution of the restore source never accepts client paths.
- `decrypt_file()` in the backup-replication module: authenticated bounded AES-GCM chunk decryption that validates framing and returns the plaintext SHA-256 digest for cross-checking against trusted backup metadata.
- A worker-side restore adapter that first creates a verified safety backup of the live database (rollback guarantee), stages the restore source (local verified backup, or decrypted off-host artifact), re-verifies SHA-256 plus `PRAGMA integrity_check` before anything is replaced, records a restore marker and restore audit row inside the staged database, swaps atomically with `os.replace`, cleans stale WAL/SHM/journal sidecars, and fails safe back to the safety backup.
- Restore runs only in the worker after the standard propose → confirm flow; the assistant cannot trigger it and completion is audited.
- The Maintenance workspace lists verified backups with a Restore action behind a high-risk confirmation modal (path, size, hash, dates, restart warning) with job progress and success/failure states.
- Backend tests covering local restore, encrypted-artifact restore, digest tampering, source resolution, safety-backup failure, ownership, and the proposal/confirmation pipeline.

Known limitations:

- A restore replaces the live database and requires an API/worker restart afterward; the UI and API surface this requirement explicitly.
- Restoring an encrypted artifact requires `BACKUP_REPLICATION_DESTINATION` and `BACKUP_REPLICATION_KEY` to be configured on the restoring host.
- Restore drills on the target Raspberry Pi remain required operational validation.

## Milestone 11 — integrations and plugins

Add integrations and plugins only through explicit capability, credential, isolation, and out-of-process boundaries.

### Milestone 11 (part 1) complete — outbound notification channels

Implemented:

- Reversible Alembic migration `0009_notification_channels` for per-channel delivery rows and the `notifications.settings` permission.
- Outbound-only channel adapters: bounded SMTP email and ntfy-compatible HTTPS push with timeouts, truncated payloads, and no inbound listeners.
- Enqueue at reminder-notification creation (one deduplicated row per enabled channel) and a dedicated worker cycle with bounded batches, processing leases, three-attempt retries, and audited terminal failures.
- Disabled-channel safety: a channel switched off after enqueueing is skipped, never sent.
- Redacted channel settings, test-send, and resend API routes with CSRF, permissions, ownership, and audit boundaries.
- Responsive Notifications workspace with channel status, masked credential state, test controls, and notification-center delivery indicators.
- Backend channel, config, worker, lease, ownership, redaction, and route tests.

Known limitations:

- Channels are configured through server environment variables; a runtime settings persistence layer is deferred to keep the environment-only configuration contract.
- Email is limited to one recipient; SMTP auth is optional but user/password must be configured together.
- Push targets a single ntfy-compatible endpoint/topic; object-storage or cloud push providers remain future integrations.
- Real SMTP relays, self-hosted ntfy servers, and sustained delivery load still require target-environment validation on the Pi.

### Milestone 11 (part 2) complete — calendar, media, finance, and plugin boundary

Implemented:

- Calendar events, categories, all-day support, range filtering, reminders, and worker delivery through the existing notification pipeline.
- Finance accounts, integer-cent transactions, categories, summaries, and strict all-or-nothing CSV import.
- Approved-root media indexing, sensitive-file exclusion, deterministic hashes, bounded Pillow thumbnails, rescan jobs, and confined private streaming.
- Migration `0015_plugins`, manifest validation, operator-approved plugin discovery, JSON-stdio subprocess execution, Linux resource limits, bounded timeout/output, risk-labeled capabilities, plugin run history, and audited lifecycle actions.
- `plugins.read` / `plugins.write` permissions, a Plugins workspace, and an always-confirmed assistant `plugins.invoke` tool. Direct HTTP invocation is limited to read-risk capabilities.
- Secret-free plugin subprocess environments, re-registration after uninstall, bounded run-history retention, and ARM64 Docker plugin-volume guidance.

Known limitations:

- Plugins are trusted operator-installed code, not a complete hostile-code sandbox; use a separate VM/container boundary for untrusted code.
- Docker and target Raspberry Pi runtime validation remain operator checks in the current environment.


## v1.2 semantic retrieval foundation

Implemented and validated in v1.2.0:

- Optional provider-neutral embeddings for existing versioned note chunks.
- SQLite-safe serialized vectors with bounded Python cosine similarity; native vector extensions remain optional.
- Leased worker batches with retries, stale-content detection, and lexical fallback.
- Lexical, semantic, and hybrid retrieval modes with source/version/hash provenance.
- Read-only assistant retrieval integration; no autonomous memory extraction or model-written notes.
- Semantic retrieval remains disabled unless the operator explicitly configures an embedding provider.

Known limitations:

- External embedding providers receive note chunk text only when explicitly enabled.
- Target Raspberry Pi ARM64 provider latency and sustained worker-load validation remain operational checks.
- Autonomous memory, external ingestion, and model-written notes remain future scope.

## v1.5 external source ingestion and lifecycle

Implemented:

- Migration `0018_external_sources` with user-owned sources, immutable versions, deterministic chunks, and source permissions.
- Bounded UTF-8 text and Markdown uploads stored beneath a server-owned data directory with generated filenames.
- Approved-root text-file discovery and opaque file identifiers; client paths are never accepted.
- Durable worker ingestion with bounded retries, integrity hashing, versioned chunks, audit events, and lifecycle states.
- Sources workspace with upload/import, processing, retry, archive, restore, delete, loading, and error states.
- Shared lexical retrieval and grounded Assistant provenance support for external sources.

Known limitations:

- PDF, OCR, arbitrary URLs, web crawling, automatic synchronization, autonomous memory extraction, model-written notes, and streaming remain deferred.
- Source-aware semantic indexing will follow the existing provider-neutral embedding boundary in a future increment.
- Docker and Raspberry Pi sustained-ingestion validation remain target-environment checks.

## v1.4 grounded assistant notes

Implemented:

- Bounded lexical, semantic, and hybrid retrieval of the authenticated user's owned notes during assistant requests.
- Explicitly delimited and escaped untrusted source context that cannot authorize tools or override assistant policy.
- Permission enforcement for `notes.read` and `notes.semantic`, with grounding skipped safely when chat AI is disabled.
- Persisted user-scoped source provenance through migration `0017_assistant_grounding`.
- Assistant retrieval controls and accessible retrieved-source links that open the owned Notes workspace.
- Backend migration, ownership, prompt-injection, permission, disabled-provider, and frontend build coverage.

Known limitations:

- Sources are server-derived retrieved-source references, not claims that the model cited or quoted each source.
- External document ingestion, autonomous memory extraction, model-written notes, and streaming remain deferred.
- The v1.5 feature is unreleased; the current production tag remains v1.3.2 until a release is created.

## v1.3 provider integration — NVIDIA NIM

Implemented and validated in v1.3.0:

- Hosted NVIDIA API Catalog defaults for OpenAI-compatible chat completions and embeddings.
- `NVIDIA_API_KEY` server-side fallback for `AI_PROVIDER=nvidia_nim` and `EMBEDDING_PROVIDER=nvidia_nim`.
- Explicit model configuration and reviewed public-compatible endpoint overrides.
- Existing provider target validation, DNS-rebinding-resistant transport, bounded response/output limits, secret redaction, and disabled-by-default behavior preserved.
- Configuration, missing-credential, environment-validation, Python compilation, backend, and frontend build coverage.

Known limitations:

- Hosted NIM requires outbound HTTPS and operator credentials; real quota/latency testing remains deployment-specific.
- Private and loopback provider targets remain rejected by design; this release does not claim self-hosted NIM execution on the Pi.
- External source ingestion and source lifecycle management are the next milestone.

## Approval rule

Before starting any milestone, document the plan, files, design decisions, tests, security implications, and rollback/limitations. Wait for owner approval before generating feature code. After completion, update all handoff docs, run validation, commit, and push.
