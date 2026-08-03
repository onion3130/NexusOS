# NexusOS database

**Current milestone:** Milestone 6 — tasks, reminders, and notifications
**Current status:** Identity, assistant, and task productivity persistence are implemented through Alembic revisions `0001_identity`, `0002_assistant`, and `0003_tasks_notifications`.
**Last updated:** 2026-08-03

## Current database state

The API uses SQLAlchemy 2.x with SQLite on the Raspberry Pi. SQLite foreign keys, WAL mode, and a bounded busy timeout are configured per connection. Startup does not run migrations automatically. Run Alembic or the owner-bootstrap command explicitly.

## Implemented persistence boundary

- `apps/api/app/db/base.py` defines the declarative base and UTC timestamp helper.
- `apps/api/app/db/models.py` defines identity, assistant, task, reminder, notification, job, and audit models.
- `apps/api/app/db/session.py` creates the engine/session boundary and checks the current migration head.
- `0001_identity` creates identity and audit tables.
- `0002_assistant` creates conversations, messages, model runs, and tool calls.
- `0003_tasks_notifications` creates categories, tags, task series, tasks, task tags, reminders, notifications, jobs, and approval lifecycle columns, including recoverable assistant-processing leases.

## Milestone 6 tables

| Entity | Owner | Purpose |
|---|---|---|
| `task_categories` | user | User-owned categories |
| `tags` | user | User-owned tags |
| `task_series` | user | Constrained recurring-task definitions |
| `tasks` | user | Task occurrences and completion history |
| `task_tags` | task/tag ownership | Task/tag many-to-many relation |
| `reminders` | user/task | Scheduled reminder state and worker leases |
| `notifications` | user | Persistent in-app notification records |
| `jobs` | system | Durable worker job metadata for future expansion |

Task deletion is soft deletion through `deleted_at`. Recurring completion creates one future occurrence while retaining the completed occurrence. Reminder delivery is idempotent through a unique `notifications.dedupe_key`.

## Recurrence

The API accepts version-one structured recurrence JSON supporting daily, weekly, and monthly schedules with bounded intervals. It does not accept arbitrary RRULE strings. All persisted instants are UTC; recurrence configuration retains a timezone label for future calculations.

## Migration rules

Every schema change must include:

1. An Alembic upgrade and downgrade revision.
2. Fresh-database upgrade coverage.
3. Downgrade and re-upgrade coverage.
4. Repository/service tests for ownership and invalid states.
5. SQLite validation and PostgreSQL validation when compatibility is claimed.
6. A backup and recovery note for data transformations.

Back up before production migrations. The task migration is reversible, but production data still requires a tested backup and restore procedure.

## Security and ownership

Every user-owned table includes a user boundary directly or through an owned parent. Services and routes filter by the authenticated user; frontend visibility is never used as authorization. Secrets, tokens, and provider payloads are not persisted.

## Remaining database work

- PostgreSQL compatibility remains a tested future claim, not an assumption.
- Backup-before-migration automation, encrypted backups, and restore drills remain deployment work.
- Notification retention cleanup and permanent task deletion remain future policy work.
