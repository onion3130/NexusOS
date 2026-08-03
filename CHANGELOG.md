# Changelog

All notable NexusOS changes are recorded here. Version `1.0.0` is a private, local-first Raspberry Pi release; internet-facing production deployment remains outside this release.

## [1.0.0] — 2026-08-03

### Release hardening

- Synchronized the complete Milestone 8 implementation, migration, frontend, tests, and documentation for reproducible release builds.
- Added bounded host-action lease recovery, three-attempt retry limits, terminal failure auditing, and job-keyed backup retry idempotency.
- Enforced SQLite source and backup paths beneath the configured data volume and retained trusted backup digests during tamper detection.
- Added worker claim indexes through migration `0006_v1_hardening`.
- Pinned Docker web dependency installation to the committed lockfile with `npm ci`.
- Aligned API, web, and health version metadata at `1.0.0`.

Known limitations: this release is intended for private/local-first use. Reverse-proxy TLS, encrypted off-host replication, restore drills, retention cleanup, and systemd orchestration remain follow-up deployment work.

## [Unreleased]

### Milestone 8 — 2026-08-03

- Added reversible Alembic migration `0005_host_actions` for expiring host-action proposals and verified backup metadata.
- Added a server-owned allowlist for SQLite backup creation, backup verification, and database integrity checks.
- Added explicit CSRF/permission/idempotency-gated proposal, confirm, reject, job, backup, and audit APIs.
- Added a non-root bounded worker with fixed SQLite adapters; arbitrary shell, Docker, reboot, shutdown, package, systemd, restore, and dynamic filesystem operations remain excluded.
- Added SHA-256 and SQLite integrity metadata for NexusOS-created backups.
- Added confirmation-first Maintenance workspace and audit/backup history.
- Added confirmation-gated assistant `maintenance.request_backup` proposal tool.
- Added comprehensive proposal, expiry, CSRF, ownership, worker, backup, migration, and audit tests.

Known limitations: restore, encrypted/off-host replication, retention cleanup, backup-before-migration automation, and target Raspberry Pi/Docker runtime validation remain future work.

### Milestone 7 — 2026-08-03

- Added reversible Alembic migration `0004_notes_search` for canonical notes, shared tags, FTS5 search projection, and retrieval chunks.
- Added user-owned note CRUD, archive/restore, soft deletion, content versioning, synchronous lexical indexing, and bounded source-aware retrieval.
- Added authenticated note/search/chunk routes with CSRF, permissions, ownership, audit, and payload-bound idempotency controls.
- Added read-only assistant `notes.search` and `notes.read` tools; embeddings, autonomous memory, and model-written notes remain deferred.
- Added responsive Notes and Search workspaces plus command-palette search integration.
- Added backend notes, FTS5, migration, ownership, chunk, and retrieval tests.

Known limitations: retrieval is lexical only; embeddings/vector search, autonomous memory extraction, external ingestion, rich Markdown rendering, and target Raspberry Pi runtime validation remain future work.

### Milestone 6 — 2026-08-03

- Added reversible task persistence migration `0003_tasks_notifications`.
- Added user-owned tasks with due dates, priorities, statuses, categories, tags, and soft deletion.
- Added constrained daily, weekly, and monthly recurring task series.
- Added absolute and due-date-relative reminders.
- Added a dedicated ARM64-compatible SQLite reminder worker with leases and notification deduplication.
- Added persistent in-app notifications with unread/read APIs and frontend polling.
- Added authenticated task, category, tag, reminder, and notification routes with permission, ownership, CSRF, validation, and audit controls.
- Added responsive task workspace with filtering, creation, completion, deletion, recurrence, and reminder controls.
- Added assistant task lookup plus confirmation-gated create, update, complete, delete, approve, and reject actions.
- Added backend migration, task, recurrence, worker, CSRF, ownership, and assistant policy tests.
- Updated all architecture, API, database, AI, security, setup, deployment, environment, and roadmap documentation.

Known limitations: notification delivery is in-app only; the current recurrence UI exposes daily, weekly, and monthly creation controls but only one weekday for weekly rules; standardized error envelopes, backups, and target-Pi runtime validation remain future hardening. Idempotency payload mismatches are rejected with `422`.

### Milestone 5 — 2026-08-02

- Added owned conversation/message persistence through reversible Alembic migration `0002_assistant`.
- Added authenticated conversation list/create/read and bounded message endpoints.
- Added a provider-neutral gateway with disabled, OpenAI-compatible, and NVIDIA NIM-compatible server-side selection, strict timeouts, safe normalized errors, and no browser credentials.
- Added the allowlisted read-only `system.get_overview` tool with sanitized tool-call metadata.
- Added the responsive assistant workspace, conversation list, bounded composer, disabled-provider state, and retry/error states.
- Kept streaming, jobs, RAG, memory, host actions, and arbitrary commands out of scope.

### Milestone 4 — 2026-08-02

- Added an authenticated, read-only Raspberry Pi system overview for CPU, memory, storage, temperature, uptime, and network status.
- Added fixed procfs/sysfs/filesystem adapters with bounded unavailable states and no subprocess, arbitrary path, Docker socket, or host-control access.
- Added dashboard polling with loading, stale, degraded, retry, and unavailable states.

[Unreleased]: https://github.com/onion3130/NexusOS/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/onion3130/NexusOS/releases/tag/v1.0.0
