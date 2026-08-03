# NexusOS roadmap

**Current milestone:** Milestone 7 — notes, search, and retrieval foundations implemented
**Next milestone:** Milestone 8 — safe host actions
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
| 8. Safe host actions | Planned | Confirmation UI, audit events, allowlisted operations, backups |
| 9. Files, projects, Git, Docker views | Planned | Approved paths, repository/project metadata, safe read operations |
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

## Milestones 8–9 — useful modules

Add safe host actions, then files/projects/Git/Docker views. Each write capability requires permissions, validation, confirmation where risky, audit events, and tests.

## Milestones 10–11 — production and expansion

Harden ARM64 deployment with reverse proxy/TLS, systemd startup, resource limits, encrypted backups, restore drills, monitoring, and rollback. Add integrations and plugins only through explicit capability and isolation boundaries.

## Approval rule

Before starting any milestone, document the plan, files, design decisions, tests, security implications, and rollback/limitations. Wait for owner approval before generating feature code. After completion, update all handoff docs, run validation, commit, and push.
