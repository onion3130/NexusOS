# Changelog

All notable NexusOS changes are recorded here. Version `1.0.0` is a private, local-first Raspberry Pi release; internet-facing production deployment remains outside this release.

## [Unreleased]

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
[Unreleased]: https://github.com/onion3130/NexusOS/compare/v1.0.0...HEAD
