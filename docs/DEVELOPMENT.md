# NexusOS development

**Current milestone:** Milestone 6 — tasks, reminders, and notifications
**Status:** Identity/assistant persistence, session authentication, responsive shell, read-only Pi telemetry, bounded assistant gateway, task API/UI, reminder worker, and in-app notifications are implemented. Notes, memory, RAG, and host actions remain deferred.
**Last updated:** 2026-08-03

Read this document with [`README.md`](../README.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`API.md`](API.md), [`DATABASE.md`](DATABASE.md), [`AI_SYSTEM.md`](AI_SYSTEM.md), [`SECURITY.md`](SECURITY.md), and [`ROADMAP.md`](ROADMAP.md) before changing code.

## Implemented Milestone 6 files

Backend:

- `app/modules/tasks/`: schemas, recurrence, service, and reminder processing.
- `app/api/routes/tasks.py`: authenticated task/category/tag/reminder/notification routes.
- `app/worker.py`: dedicated reminder worker entrypoint.
- `app/db/models.py`: task, series, reminder, notification, job, and approval persistence.
- `migrations/versions/0003_tasks_notifications.py`: reversible schema migration.
- `tests/test_tasks.py`: CRUD, CSRF, recurrence, worker, and assistant policy coverage.

Frontend:

- `components/task-workspace.tsx`: task creation, filtering, completion, deletion, and state handling.
- `components/notification-center.tsx`: persistent notification polling and read actions.
- `components/assistant-action-confirmation.tsx`: task mutation confirmation UI.
- `lib/tasks.ts` and `lib/notifications.ts`: authenticated clients.
- `lib/auth.ts`: CSRF headers for browser mutations.

## Local setup

```sh
cp .env.example .env
python scripts/validate_env.py --env-file .env
```

Use a random local `JWT_SECRET` of at least 32 characters and keep `AI_PROVIDER=disabled` unless a server-side provider is intentionally configured.

## Backend validation

```sh
cd apps/api
python -m pip install -e '.[test]'
python -m pytest
python -m py_compile $(find app migrations tests -name '*.py' -print)
python -m alembic heads
```

The current expected migration head is `0003_tasks_notifications`.

## Frontend validation

```sh
cd apps/web
npm install
npm run typecheck
npm run build
```

## Run locally

Run explicit migrations and owner bootstrap before starting the API:

```sh
cd apps/api
python -m alembic upgrade head
python -m app.cli.bootstrap_owner --username owner
cd ../..
python -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

Start the web shell in another terminal:

```sh
cd apps/web
npm run dev
```

The task workspace is available from the authenticated Tasks navigation item. The notification center polls every 30 seconds. The assistant remains usable in disabled-provider mode for conversations; task mutations require a configured provider and explicit approval.

Run the reminder worker separately for local scheduler testing:

```sh
cd apps/api
python -m app.worker
```

## Compose and ARM64 validation

```sh
docker compose --env-file .env config --quiet
docker compose --env-file .env run --rm nexus-api python -m alembic upgrade head
docker compose --env-file .env run --rm nexus-api python -m app.cli.bootstrap_owner --username owner
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
docker compose --env-file .env down
```

The API, web, and worker target `linux/arm64`, use non-root runtime users, share the SSD-backed SQLite volume, and use a private network. The current environment lacks Docker, so Compose and target-Pi execution remain required external checks.

## Security rules

- Every task/category/tag/reminder/notification query is user-scoped.
- Cookie mutations require CSRF.
- Assistant task writes require permissions, typed validation, expiry, explicit approval, and audit events.
- Task deletion is soft deletion.
- No provider key, token, arbitrary command, filesystem path, or SQL reaches the browser or task service.

## Definition of done

A milestone is complete only when its code, tests, documentation, security implications, failure states, deployment behavior, and remaining limitations have been reviewed. Design text alone does not make a feature implemented.
