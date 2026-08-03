# NexusOS database

**Current milestone:** Milestone 5 — assistant gateway
**Current status:** Identity and assistant persistence are implemented. Alembic revisions `0001_identity` and `0002_assistant` create the current identity, conversation, message, model-run, tool-call, and audit tables. Later domain feature tables remain deferred.
**Last updated:** 2026-08-02

This document distinguishes the current configuration contract from the planned persistence design.

## Current database state

The API validates `DB_TYPE=sqlite` and `DATABASE_URL`, opens SQLite through SQLAlchemy after migrations are applied, and reports migration/database status through `/api/v1/health/ready`. Startup does not run migrations automatically.

The current `.env.example` database values define the Milestone 2 SQLite contract:

```text
DB_TYPE=sqlite
DATABASE_URL=sqlite:////var/lib/nexus/data/nexus.db
```

Compose mounts the host `${DATA_DIR}/db` directory at `/var/lib/nexus/data`. Runtime database files are ignored by Git.

## Implemented persistence boundary

- `apps/api/app/db/base.py` defines the declarative base.
- `apps/api/app/db/models.py` defines the identity, assistant, and audit models.
- `apps/api/app/db/session.py` creates the engine and request-scoped sessions.
- `apps/api/migrations/versions/0001_identity.py` creates identity/audit tables.
- `apps/api/migrations/versions/0002_assistant.py` creates conversations, messages, model runs, and tool calls.
- `python -m app.cli.bootstrap_owner --username owner` runs migrations and creates the first owner interactively.

## Planned decisions

- SQLAlchemy 2.x will be the persistence abstraction.
- Alembic will own reversible, versioned migrations.
- SQLite is the first Pi deployment database and should use WAL mode and foreign keys.
- PostgreSQL support is a compatibility target, not a claim that has been tested yet.
- IDs will be opaque UUIDs and timestamps will be UTC.
- Large bodies, uploads, logs, and model artifacts remain in the filesystem data mount; rows store metadata, ownership, hashes, and references.
- Secrets will never be plaintext database values. Use Docker secrets or an approved encrypted credential boundary and store only references where possible.

## Planned storage layout

```text
DATA_DIR/
├── db/                 SQLite database and WAL files
├── backups/            encrypted backup artifacts
├── uploads/            approved user files
├── logs/               bounded application logs
└── cache/              disposable provider/index cache
```

## Current identity schema and planned feature schema

The identity and assistant tables below are current. Remaining domain entities are design-only and will be introduced incrementally:

| Entity | Owner | Purpose |
|---|---|---|
| `users` | identity | Local account identity and status |
| `roles`, `permissions`, `user_roles` | identity | Action-oriented authorization |
| `sessions` | identity | Revocable session metadata and token hashes |
| `audit_events` | observability | Authentication, permission, tool, and data-change trail |
| `tasks`, `reminders`, `notifications` | tasks | Productivity and scheduled work |
| `conversations`, `messages` | assistant | User-scoped assistant history |
| `model_runs`, `tool_calls` | assistant | Provider trace and tool approvals |
| `memories` | assistant | Explicit, retention-aware user memory |
| `jobs` | workers | Long-running operation state |
| `system_snapshots`, `service_status` | system | Telemetry and service checks |
| `notes` | notes | User-owned notes and search metadata |
| `settings` | settings | Instance/user preferences and encrypted references |
| `integration_accounts` | integrations | Provider metadata without raw credentials |

Every user-owned entity must have an ownership boundary. Feature modules must access persistence through services/repositories rather than another module's tables.

## Migration rules

Every schema change must include:

1. An Alembic upgrade and downgrade revision.
2. Fresh-database upgrade coverage.
3. Downgrade and re-upgrade coverage.
4. Repository/service tests for ownership and invalid states.
5. SQLite validation and PostgreSQL validation when compatibility is claimed.
6. A backup and recovery note for data transformations.

Back up before production migrations. Irreversible transformations require explicit owner approval and a documented recovery path.

## Milestone 5 persistence boundary — complete

- Conversations and messages are owned by a local user.
- Provider calls occur after the user-message transaction commits.
- Provider credentials and raw upstream payloads are not persisted.
- Model runs and tool calls retain bounded normalized metadata and safe error codes.
- Migration upgrade/downgrade/re-upgrade coverage includes the assistant schema.

## Milestone 2 acceptance criteria — complete


- The API creates a configured engine without leaking connection strings or credentials.
- A fresh SQLite database upgrades to the migration head.
- An owner bootstrap flow creates the first account without default credentials.
- Sessions are revocable and audit events are recorded.
- Readiness reports database status separately from storage status.
- Tests prove ownership isolation and migration safety.

See [`ARCHITECTURE.md`](ARCHITECTURE.md), [`API.md`](API.md), and [`ROADMAP.md`](ROADMAP.md) for the surrounding boundaries.
