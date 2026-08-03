# NexusOS database design

**Status:** Design accepted for future implementation; no database engine, ORM, model, or migration is implemented in Milestone 1.
**Last updated:** 2026-08-02

This document is the database handoff for a new coding agent. It describes the intended persistence boundary without implying that the planned tables or migrations already exist.

## Current implementation

Milestone 1 validates `DB_TYPE` and `DATABASE_URL` as configuration contracts, but the API does not open a database connection. The readiness endpoint checks only the configured `DATA_DIR` directory and a temporary write/delete probe. Database readiness, models, repositories, migrations, and persistence tests belong to Milestone 2.

Do not add database calls to the Milestone 1 health endpoint as a convenience. Implement the persistence boundary as a separate, approved feature with migrations and tests.

## Decisions

- Use SQLAlchemy 2.x for the persistence abstraction.
- Use Alembic for reversible, versioned migrations.
- Use SQLite on the Raspberry Pi initially, stored on the external SSD.
- Keep SQL and repository behavior portable to PostgreSQL.
- Use UTC timestamps and opaque UUID identifiers.
- Store large bodies, uploads, logs, and model artifacts in the filesystem data mount; database rows hold metadata, ownership, hashes, and references.
- Keep domain modules behind repository/service interfaces. A module must not query another module's tables directly.

## Runtime layout

The host-side `DATA_DIR` is the persistent root. Compose currently maps its `db` directory to `/var/lib/nexus/data` in the API container. The configured SQLite URL in `.env.example` points at `/var/lib/nexus/data/nexus.db`.

Planned layout:

```text
DATA_DIR/
├── db/                 # SQLite database and WAL files
├── backups/            # encrypted backup artifacts
├── uploads/            # approved user files
├── logs/               # bounded application logs
└── cache/              # disposable provider/index cache
```

The database, runtime data, backups, and personal content are ignored by Git and must never be committed.

## Initial entity model

The first persistence milestone should introduce the smallest useful schema, in this order:

1. `users`, `roles`, `permissions`, `user_roles`
2. `sessions` and `audit_events`
3. `tasks`, `reminders`, and `notifications`
4. `conversations`, `messages`, `model_runs`, and `tool_calls`
5. `settings` and integration metadata as their security design is approved

The broader architecture reserves these future entities:

| Entity | Ownership | Purpose |
|---|---|---|
| `users` | identity | Local account identity and status |
| `roles`, `permissions`, `user_roles` | identity | Role and action authorization |
| `sessions` | identity | Revocable session metadata and token hashes |
| `audit_events` | identity/observability | Security and administrative trail |
| `tasks`, `reminders`, `notifications` | tasks | Productivity and scheduled work |
| `conversations`, `messages` | assistant | User-scoped assistant history |
| `model_runs`, `tool_calls` | assistant | Traceable AI execution and approvals |
| `memories` | assistant | Explicit, retention-aware user memory |
| `jobs` | workers | Asynchronous operation state |
| `system_snapshots`, `service_status` | system | Historical telemetry and service checks |
| `notes` | notes | User-owned notes and search metadata |
| `settings` | settings | Instance/user preferences and encrypted references |
| `integration_accounts` | integrations | Provider identity without raw credentials in ordinary rows |

## Data rules

- Every user-owned row includes an ownership relationship or an explicit instance scope.
- Foreign keys are enforced in SQLite connections.
- SQLite uses WAL mode after the connection layer is introduced.
- Transactions are short and explicit; long-running work uses jobs rather than open HTTP transactions.
- Soft deletion is used where auditability or user recovery matters; permanent deletion requires an explicit policy and audit event.
- Secrets are never stored as plaintext columns. Prefer Docker secrets or an approved encrypted credential store and persist only a reference.
- Conversation and memory retention must be configurable, visible to the user, and enforced by bounded background jobs.
- Schema migrations must not silently destroy data.

## Migration policy

Every schema change must include:

- An Alembic revision with an upgrade and downgrade path.
- Model/repository tests for the changed behavior.
- A fresh-database upgrade test.
- A downgrade-and-reupgrade test for the previous revision.
- SQLite validation and PostgreSQL validation when the migration uses portable support.
- A backup/restore note for data transformations.

Before a production migration, create and verify a backup. Irreversible transformations require explicit owner approval and a documented recovery path.

## Milestone 2 acceptance criteria

- API startup can create a configured engine without leaking the URL or credentials.
- A fresh SQLite database upgrades to the migration head.
- Owner bootstrap creates a first account without shipping default credentials.
- Authentication and session rows are revocable and auditable.
- Tests cover repository behavior, migration upgrade/downgrade, ownership isolation, and invalid configuration.
- Readiness reports database status separately from storage status.
- PostgreSQL compatibility is either tested or clearly marked as not yet supported; it must not be claimed based only on a portable-looking schema.

## Related documents

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — persistence boundary and milestone plan.
- [`API.md`](API.md) — resource and job contracts.
- [`ENVIRONMENT.md`](ENVIRONMENT.md) — current database configuration variables.
- [`DEPLOYMENT.md`](DEPLOYMENT.md) — runtime storage and current limitations.
