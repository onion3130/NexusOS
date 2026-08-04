# Changelog

All notable NexusOS changes are recorded here. NexusOS releases use Semantic Versioning; private, local-first Raspberry Pi deployment remains the supported operating model.

## [Unreleased]

### Grounded assistant notes

- Added bounded lexical, semantic, and hybrid note grounding for assistant responses.
- Added explicit untrusted-source context boundaries, note permissions, disabled-provider safeguards, and prompt-injection-safe escaping.
- Added persisted, user-scoped source provenance and ownership-checked source metadata endpoints.
- Added Assistant controls for enabling note grounding, selecting retrieval mode, and opening cited notes.
- Added migration `0017_assistant_grounding` and security, migration, and ownership coverage.
- External document ingestion, autonomous memory extraction, and model-written notes remain deferred.

## [1.3.2] — 2026-08-04

NexusOS v1.3.2 is a Docker healthcheck patch for the ARM64 web container.

### Docker reliability

- Explicitly bind the Next.js standalone web server to `0.0.0.0` so the container-local healthcheck and service-to-service networking use the same listener.
- Verified the fix against the Raspberry Pi deployment, where the previous image served through the published host port but refused container-loopback probes.
- Preserved the v1.3.1 migration compatibility fix and v1.3 NVIDIA NIM support.


## [1.3.1] — 2026-08-04

NexusOS v1.3.1 is a compatibility patch for upgrading existing v1.0/v1.1 databases to the current schema.

### Migration compatibility

- Fixed permission-seeder queries in migrations `0012_calendar` through `0016_embeddings` to respect the composite `role_permissions` primary key.
- Added regression coverage for upgrading a legacy `0006_v1_hardening` database through `0016_embeddings`.
- Preserved all v1.3.0 NVIDIA NIM behavior and security boundaries.


NexusOS v1.3.0 adds first-class NVIDIA NIM configuration on top of the existing provider-neutral gateway.

### NVIDIA NIM support

- Added hosted NVIDIA API Catalog defaults for chat completions and embeddings.
- Added `NVIDIA_API_KEY` fallback for `AI_PROVIDER=nvidia_nim` and `EMBEDDING_PROVIDER=nvidia_nim`, without exposing credentials to the browser, web container, database, or logs.
- Preserved explicit custom endpoint configuration for reviewed compatible public providers.
- Kept bounded timeouts, output/response limits, private-target rejection, DNS-rebinding-resistant transport, and lexical fallback behavior.
- Added configuration, environment-validation, credential-failure, and hosted-default tests.

### Limitations

- NIM remains disabled by default and requires an operator-provided NVIDIA API key and model identifiers.
- Hosted NIM requires outbound network access; private and loopback provider targets remain rejected by design, and this release does not claim self-hosted NIM execution on the Pi.
- NVIDIA NIM runtime latency and quota behavior require operator validation on the target deployment.


## [1.2.0] — 2026-08-04

NexusOS v1.2.0 adds the semantic retrieval foundation for private notes.

### Semantic retrieval

- Added optional provider-neutral embeddings for deterministic, versioned note chunks.
- Added migration `0016_embeddings` and the `notes.semantic` permission.
- Added bounded serialized-vector storage and Python cosine similarity without a mandatory native SQLite extension.
- Added leased worker batches, retry limits, stale-content detection, and provider-disabled safety behavior.
- Added lexical, semantic, and hybrid retrieval modes with source/version/hash provenance and lexical fallback.
- Added aggregate embedding status without exposing vectors or credentials.
- Extended the assistant note search contract with retrieval-mode metadata while preserving lexical behavior by default.
- Added security, migration, configuration, and vector-boundary tests.

### Limitations

- Embeddings are disabled by default and require explicit server-side provider configuration.
- External providers receive note chunk text only when enabled by the operator.
- Autonomous memory extraction, external ingestion, model-written notes, and native vector extensions remain future work.


## [1.1.0] — 2026-08-04

NexusOS v1.1.0 delivers calendar, finance, media, and the security-first out-of-process plugin boundary.

### Milestone 11 part 2 integrations and plugin boundary

- Added a user-owned Calendar workspace with categories, all-day events, bounded date-range queries, absolute and event-relative reminders, and worker-delivered notifications.
- Added a Finance workspace with integer-cent account balances, categorized transactions, period summaries, and strict all-or-nothing CSV import.
- Added a derived Media workspace with approved-root indexing, credential-file exclusion, deterministic hashing, bounded Pillow thumbnails, rescan jobs, and confined private streaming.
- Added the out-of-process plugin boundary: manifest validation, approved-directory discovery, JSON-stdio subprocess execution, Linux resource limits, bounded timeout/output, capability risk labels, run history, and audited lifecycle actions.
- Added migration `0015_plugins`, `PLUGINS_DIR`, and `PLUGIN_INVOKE_TIMEOUT_SECONDS`; plugin lifecycle mutations require explicit confirmation and write/dangerous capabilities are unavailable through the direct HTTP path.
- Added backend and frontend validation for plugin confinement, timeouts, capability enforcement, lifecycle auditing, migration reversibility, TypeScript, and production builds.

### Milestone 13 backup retention and lifecycle policy

- Added policy-driven retention cleanup through the confirmed `maintenance.retention_cleanup` action: keeps the newest `BACKUP_RETENTION_COUNT` (default 7) verified backups and everything younger than `BACKUP_RETENTION_DAYS` (default 30), always retains the newest backup, deletes only digest-matched local artifacts (and encrypted off-host artifacts when the destination is configured), soft-deletes records, and audits every prune.
- Added `BACKUP_RETENTION_COUNT`, `BACKUP_RETENTION_DAYS`, and `BACKUP_REPLICATION_KEY_PREVIOUS` environment settings with bounds and key-difference validation.
- Added the read-only `GET /api/v1/system/backups/retention-preview` endpoint and the Maintenance workspace lifecycle panel with a prune preview.
- Added the confirmed high-risk `maintenance.rotate_encryption_key` action that re-encrypts every replicated artifact from the previous key to the current key in bounded authenticated chunks with atomic replace, staging cleanup, and idempotent retries.
- Added migration `0011_backup_lifecycle` with `backup_records.pruned_at`; pruned records are excluded from the backup listing.
- Added backend tests for retention boundaries, last-backup protection, digest-safe pruning, path confinement, fail-closed encrypted pruning, rotation idempotency, the preview endpoint, and both proposal pipelines.

### Milestone 12 restore and recovery automation

- Added confirmation-gated restore from verified NexusOS backup artifacts through the existing proposal/confirm worker pipeline (risk `high`, input limited to `backup_id`).
- Added a worker-side restore adapter: verified safety backup of the live database first (rollback guarantee), server-side source resolution (local verified backup or encrypted off-host artifact), staged SHA-256 plus `PRAGMA integrity_check` re-verification before replacement, restore marker and audit row recorded inside the staged database, atomic `os.replace` swap, stale WAL/SHM/journal cleanup, and rollback to the safety backup on swap failure.
- Added `decrypt_file()` to the backup-replication module for bounded, authenticated AES-256-GCM chunk decryption that returns the plaintext SHA-256 digest for cross-checking against trusted backup metadata.
- Added migration `0010_restore` with `backup_records.restored_at`.
- Added the Restore section to the Maintenance workspace with a high-risk confirmation modal, job progress, and success/failure states; successful restore requires an API/worker restart, surfaced in the UI and API result.
- Added backend tests for local and encrypted restore, digest tampering, source resolution, safety-backup failure, ownership, and the proposal pipeline.

### Milestone 11 (part 1) notification channels

- Added outbound-only notification channel delivery: bounded SMTP email and ntfy-compatible HTTPS push with timeouts, truncated payloads, and no inbound listeners.
- Added per-channel delivery rows through migration `0009_notification_channels`, the `notifications.settings` permission, and a dedicated worker cycle with bounded batches, processing leases, three-attempt retries, and audited terminal failures.
- Added redacted channel settings, test-send, and resend API routes with CSRF, permission, ownership, and audit boundaries.
- Added the Notifications workspace with channel status, masked credential state, test controls, and notification-center delivery indicators.
- Reminders now enqueue one delivery per enabled channel at creation; channels disabled later are skipped, never sent.

### Milestone 10 deployment hardening

- Added an opt-in ARM64 hardened Compose overlay with Caddy internal TLS, private upstream routing, direct API/web port removal, and bounded resources.
- Added Raspberry Pi systemd startup/shutdown orchestration with SSD mount dependency and upgrade/rollback guidance.
- Added optional AES-256-GCM chunk encryption and operator-mounted off-host backup replication with durable leases, retries, atomic writes, and tamper detection.
- Added migration `0008_deployment_hardening`, deployment status API, Maintenance replication status, and security-focused tests.

### Milestone 9 workspace views

- Added authenticated read-only Files, Projects, Git, and Docker metadata workspaces.
- Added approved-root configuration, sensitive filename filtering, bounded scans, fixed Git inspection, and optional sanitized Docker inspection.
- Added the `workspace_views.read` permission, migration `0007_workspace_views`, assistant read tools, and security-focused tests.

## [1.0.1] — 2026-08-03

### Docker packaging fix

- Fixed the web ARM64 image build to copy the committed `package-lock.json` before running `npm ci`.
- Confirmed backend tests, frontend typecheck, and frontend production build remain green.

## [1.0.0] — 2026-08-03

NexusOS v1.0.0 establishes a private, local-first personal AI operating system for Raspberry Pi 5 with an authenticated dashboard, productivity modules, bounded assistant tools, read-only telemetry, and safe maintenance workflows.

### Features

- Added owned conversation and message persistence through reversible Alembic migration `0002_assistant`.
- Added a provider-neutral assistant gateway with disabled, OpenAI-compatible, and NVIDIA NIM-compatible server-side providers.
- Added the allowlisted read-only `system.get_overview` assistant tool.
- Added read-only Raspberry Pi telemetry for CPU, memory, storage, temperature, uptime, and network status.
- Added user-owned tasks with due dates, priorities, statuses, categories, tags, and soft deletion.
- Added constrained daily, weekly, and monthly recurring task series.
- Added absolute and due-date-relative reminders with persistent in-app notifications.
- Added a dedicated ARM64-compatible SQLite worker with leases and notification deduplication.
- Added user-owned notes, archive/restore, content versioning, SQLite FTS5 search, and source-aware retrieval chunks.
- Added confirmation-gated assistant task actions for create, update, complete, and delete operations.
- Added confirmation-gated safe maintenance actions for SQLite backup creation, backup verification, and database integrity checks.
- Added the responsive dashboard, Assistant, Tasks, Notes, Search, Notifications, and Maintenance workspaces.

### Security and reliability

- Added session authentication with Argon2id password hashing, refresh rotation, revocation, and CSRF protection.
- Added server-side permissions, ownership checks, bounded payload validation, audit events, and idempotency controls.
- Added explicit confirmation workflows for assistant mutations and all host actions.
- Excluded arbitrary shell commands, Docker socket access, reboot, shutdown, package management, systemd control, restore requests, and dynamic filesystem paths.
- Added bounded host-action lease recovery, three-attempt retry limits, terminal failure auditing, and job-keyed backup retry idempotency.
- Enforced SQLite source and backup paths beneath the configured data volume.
- Added SHA-256 metadata, SQLite integrity checks, tamper detection, and recovery for incomplete backup artifacts.
- Added worker claim indexes through migration `0006_v1_hardening`.
- Pinned Docker web dependency installation to the committed lockfile with `npm ci`.
- Aligned API, web, and health version metadata at `1.0.0`.

### Validation

- Backend test suite: 46 tests passed.
- Python compilation: passed.
- Alembic upgrade, downgrade, and re-upgrade lifecycle: passed.
- Documentation link validation: 59 internal links passed.
- Frontend TypeScript typecheck: passed.
- Frontend production build: passed.
- Static ARM64, non-root, loopback, private-network, and no-Docker-socket checks: passed.

### Known limitations

This release is intended for private, local-first use. Docker and Raspberry Pi runtime validation must be completed on a Docker-enabled ARM64 host. Reverse-proxy TLS, encrypted off-host replication, restore drills, retention cleanup, systemd orchestration, production monitoring, semantic retrieval, embeddings, autonomous memory, and external notification channels remain follow-up work.

[1.0.1]: https://github.com/onion3130/NexusOS/releases/tag/v1.0.1
[1.0.0]: https://github.com/onion3130/NexusOS/releases/tag/v1.0.0
[1.1.0]: https://github.com/onion3130/NexusOS/releases/tag/v1.1.0
[1.3.2]: https://github.com/onion3130/NexusOS/releases/tag/v1.3.2
[1.3.1]: https://github.com/onion3130/NexusOS/releases/tag/v1.3.1
[1.3.0]: https://github.com/onion3130/NexusOS/releases/tag/v1.3.0
[Unreleased]: https://github.com/onion3130/NexusOS/compare/v1.3.2...HEAD
