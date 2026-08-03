# ADR 0004: SQLite-backed tasks, reminders, and in-app notifications

- **Status:** Accepted
- **Date:** 2026-08-03

## Decision

Milestone 6 adds a user-owned task module inside the existing FastAPI modular monolith. Tasks, constrained recurring series, reminders, notifications, and worker metadata are persisted in SQLite through Alembic revision `0003_tasks_notifications`.

A dedicated lightweight worker process polls SQLite for due reminders. It uses bounded batches, short transactions, leases for recovery, and deterministic notification deduplication. Redis, Celery, RabbitMQ, and other heavyweight infrastructure are intentionally not introduced.

Notifications are initially persistent in-app records. The browser polls the authenticated notification API; email, SMS, web push, and calendar integrations remain future adapters.

Assistant task mutations are typed, permissioned proposals. Create, update, complete, and delete operations require explicit approval and are executed through the task service. Task deletion is soft deletion.

## Rationale

NexusOS targets a Raspberry Pi 5 with an external SSD and must remain useful when AI is disabled. SQLite minimizes idle resource use, while a dedicated worker avoids coupling scheduled work to web-request lifetime. Persistent notifications survive browser and worker restarts.

## Consequences

- All task-domain entities enforce user ownership at the service and route boundaries.
- UTC timestamps and constrained recurrence rules are required.
- The worker must be run exactly once in the current Compose topology.
- Migration backups and restore procedures remain deployment work.
- Notification delivery is local-only until a later integration milestone.
