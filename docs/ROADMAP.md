# NexusOS roadmap

**Current milestone:** Milestone 1 — foundation implemented
**Next milestone:** Milestone 2 — identity and persistence, pending an approved implementation plan
**Last updated:** 2026-08-02

This roadmap is the source of truth for sequencing. Do not implement a later milestone because its design appears in another document.

## Checkpoint status — 2026-08-02

The project is paused after Milestone 1. The checkpoint found no confirmed application bug requiring feature work. Available automated validation is green, while Docker/ARM64 image builds and on-device Raspberry Pi 5 behavior remain unverified on the current workstation.

Before Milestone 2 begins, preserve these boundaries:

- The only live API routes are `/api/v1/health/live` and `/api/v1/health/ready`.
- The database and AI documents describe designs, not implemented services.
- Compose is a loopback-only development topology, not a production or LAN deployment.
- Any healthcheck timeout adjustment must be validated on the target Pi rather than guessed.

## Status summary

| Milestone | Status | Outcome |
|---|---|---|
| 0. Architecture and public foundation | Complete | Repository rules, architecture, security baseline, and documentation |
| 1. ARM64 application foundation | Complete | API health service, static web shell, Compose, validation, tests |
| 2. Identity and persistence | Not started | Owner account, SQLite/Alembic, sessions, auth boundary |
| 3. Dashboard shell and design system | Planned | Authenticated navigation, shared UI primitives, accessible states |
| 4. System read-only module | Planned | Pi telemetry and allowlisted service/container status |
| 5. Assistant gateway | Planned | Conversations, provider gateway, streaming jobs, read-only tools |
| 6. Tasks and reminders | Planned | Homework/tasks, reminders, notifications, assistant task actions |
| 7. Notes and scoped search | Planned | Notes, tags, search, source-aware retrieval |
| 8. Safe host actions | Planned | Confirmation UI, audit events, allowlisted operations, backups |
| 9. Files, projects, Git, Docker views | Planned | Approved paths, repository/project metadata, safe read operations |
| 10. Deployment hardening | Planned | Reverse proxy, systemd, SSD operations, backups, restore drill |
| 11. Integrations and plugins | Planned | Calendar/media/finance ports and out-of-process plugin boundary |

## Milestone 1 complete

Built and verified:

- FastAPI startup configuration loaded from process environment variables.
- Safe rejection of missing, placeholder, short, or production-insecure configuration.
- `GET /api/v1/health/live`.
- `GET /api/v1/health/ready` with a storage write/delete probe.
- Next.js static shell showing foundation status and deferred capabilities.
- ARM64/non-root API and web Dockerfiles.
- Compose services and loopback-only development ports.
- Backend tests and frontend typecheck/build configuration.

Not built in Milestone 1: auth, database, AI, tools, jobs, feature APIs, telemetry, backups, TLS, or Pi write actions.

## Milestone 2 — identity and persistence

**Estimated effort:** 4–6 hours

Plan:

- Add SQLAlchemy engine/session boundary and Alembic migrations.
- Implement users, roles/permissions, sessions, and audit events.
- Add owner bootstrap without default credentials.
- Add password hashing, login/logout/current-user, secure HttpOnly session cookies, CSRF strategy, and rate limiting.
- Update readiness to report database status separately from storage.
- Add SQLite migration tests and document PostgreSQL compatibility status.

Acceptance criteria:

- Unauthenticated users cannot access authenticated resources.
- Session tokens are revocable and only hashes are persisted.
- Fresh database upgrade, downgrade, and re-upgrade tests pass.
- No secrets or passwords are logged or returned.
- Documentation and API contracts match the implementation.

## Milestone 3 — authenticated dashboard shell

Add the shared app shell, route protection, navigation, theme tokens, command-palette foundation, loading/empty/error/permission states, and accessibility checks. Do not add feature data modules yet.

## Milestone 4 — read-only system module

Add Pi CPU, memory, storage, temperature, network, uptime, and allowlisted service/container status through a bounded adapter. Keep all write actions disabled.

## Milestone 5 — assistant gateway

Persist conversations, add the provider-neutral `ModelGateway`, normalized errors, streaming/job boundaries, provider health, and read-only typed tools. AI provider selection remains server-controlled.

## Milestones 6–9 — useful modules

Add tasks/reminders, notes/search, safe host actions, then files/projects/Git/Docker views. Each write capability requires permissions, validation, confirmation where risky, audit events, and tests.

## Milestones 10–11 — production and expansion

Harden ARM64 deployment with reverse proxy/TLS, systemd startup, resource limits, encrypted backups, restore drills, monitoring, and rollback. Add integrations and plugins only through explicit capability and isolation boundaries.

## Approval rule

Before starting any milestone, document the plan, files, design decisions, tests, security implications, and rollback/limitations. Wait for owner approval before generating feature code. After completion, update all handoff docs, run validation, commit, and push.
