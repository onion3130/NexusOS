# NexusOS roadmap

**Current milestone:** Milestone 5 — assistant gateway implemented
**Next milestone:** Milestone 6 — tasks and reminders
**Last updated:** 2026-08-02

This roadmap is the source of truth for sequencing. Do not implement a later milestone because its design appears in another document.

## Checkpoint status — 2026-08-02

The project is paused after Milestone 5. The authenticated shell, read-only system telemetry, and bounded assistant gateway are complete within scope. Local validation and the API/web ARM64 image/runtime checks on the available Raspberry Pi 5 are green.

Current boundaries:

- The live API includes health, identity/session, system overview, and assistant conversation routes documented in `docs/API.md`.
- The identity and assistant database schema is implemented through Alembic migrations `0001_identity` and `0002_assistant`; later domain tables remain design-only.
- The assistant gateway is live with server-side provider selection, but AI remains disabled by default and later memory/RAG/job designs remain deferred.
- Compose is a loopback-only development topology, not a production or LAN deployment.
- Any healthcheck timeout adjustment must be validated on the target Pi rather than guessed.

## Status summary

| Milestone | Status | Outcome |
|---|---|---|
| 0. Architecture and public foundation | Complete | Repository rules, architecture, security baseline, and documentation |
| 1. ARM64 application foundation | Complete | API health service, foundation web shell, Compose, validation, tests |
| 2. Identity and persistence | Complete | Owner bootstrap, SQLite/Alembic, sessions, auth boundary |
| 3. Dashboard shell and design system | Complete | Authenticated navigation, shared UI primitives, accessible states |
| 4. System read-only module | Complete | Authenticated Pi telemetry with safe unavailable service/container boundary |
| 5. Assistant gateway | Complete | Conversations, bounded provider gateway, read-only system tool, assistant UI |
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
- Next.js foundation shell showing status and deferred capabilities.
- ARM64/non-root API and web Dockerfiles.
- Compose services and loopback-only development ports.
- Backend tests and frontend typecheck/build configuration.

Not built in Milestone 1: auth, database, AI, tools, jobs, feature APIs, telemetry, backups, TLS, or Pi write actions.

## Milestone 2 complete — identity and persistence

Implemented:

- SQLAlchemy engine/session boundary with SQLite foreign keys, WAL, and busy timeout.
- Reversible Alembic migration `0001_identity`.
- Users, roles, permissions, sessions, join tables, and audit events.
- Explicit owner bootstrap without default credentials.
- Argon2id passwords, HS256 access JWTs, rotated hashed refresh tokens, CSRF, and login backoff.
- Identity APIs, database readiness, migration tests, and frontend login boundary.

Acceptance criteria met:

- Unauthenticated callers cannot access identity resources.
- Session secrets are hashed and revocable.
- Migration upgrade/downgrade/re-upgrade tests pass.
- Errors and responses do not expose passwords, tokens, or secrets.
- Documentation and API contracts identify implemented versus planned routes.

## Milestone 3 complete — authenticated dashboard shell

Implemented the shared app shell, responsive route-aware navigation, persisted theme tokens and toggle, keyboard command-palette foundation, loading/error/empty/permission states, focus management, and accessibility semantics. Feature data modules remain intentionally absent.

Acceptance criteria met:

- Authenticated users receive a responsive shell with mobile navigation and a skip link.
- Light/dark appearance can be toggled and persists locally without adding a dependency.
- Command palette opens with Cmd/Ctrl+K and supports search, arrows, Enter, Escape, focus trapping, and focus restoration.
- Unfinished modules are visibly locked and do not call feature APIs.
- Frontend typecheck, production build, and dependency audit pass.


## Milestone 4 complete — read-only system module

Implemented authenticated CPU, memory, storage, temperature, network, and uptime telemetry through bounded procfs/sysfs/filesystem adapters. Missing sources degrade to safe status codes. Service/container status remains explicitly unavailable because no Docker socket or host-control boundary was introduced. Dashboard polling is bounded to 30 seconds and all write actions remain disabled.

Acceptance criteria met:

- Unauthenticated callers cannot access system telemetry.
- Adapter failures do not expose host paths, stack traces, or command output.
- API and frontend expose no restart, shutdown, Docker write, or arbitrary command action.
- Deterministic adapter/authentication tests pass.
- ARM64 Docker and runtime validation remains compatible with the verified Pi deployment boundary.

## Milestone 5 complete — assistant gateway

Implemented owned conversation/message persistence, reversible migration `0002_assistant`, bounded synchronous provider calls, normalized provider errors, server-side provider selection, the read-only `system.get_overview` tool, and the authenticated assistant workspace. Streaming, background jobs, provider health dashboards, memory, RAG, and write tools remain deferred.

## Milestones 6–9 — useful modules

Add tasks/reminders, notes/search, safe host actions, then files/projects/Git/Docker views. Each write capability requires permissions, validation, confirmation where risky, audit events, and tests.

## Milestones 10–11 — production and expansion

Harden ARM64 deployment with reverse proxy/TLS, systemd startup, resource limits, encrypted backups, restore drills, monitoring, and rollback. Add integrations and plugins only through explicit capability and isolation boundaries.

## Approval rule

Before starting any milestone, document the plan, files, design decisions, tests, security implications, and rollback/limitations. Wait for owner approval before generating feature code. After completion, update all handoff docs, run validation, commit, and push.
