# NexusOS roadmap

**Current milestone:** Milestone 9 — files, projects, Git, and Docker views
**Next milestone:** Milestone 10 — deployment hardening
**Last updated:** 2026-08-03

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
| 10. Deployment hardening | Planned | Reverse proxy, systemd, SSD operations, backups, restore drill |
| 11. Integrations and plugins | Planned | Calendar/media/finance ports and out-of-process plugin boundary |

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

## Milestones 10–11 — production and expansion

Harden ARM64 deployment with reverse proxy/TLS, systemd startup, resource limits, encrypted backups, restore drills, monitoring, and rollback. Add integrations and plugins only through explicit capability and isolation boundaries.

## Approval rule

Before starting any milestone, document the plan, files, design decisions, tests, security implications, and rollback/limitations. Wait for owner approval before generating feature code. After completion, update all handoff docs, run validation, commit, and push.
