# NexusOS development

**Current milestone:** v1.5 — external source ingestion and source lifecycle management (unreleased)
**Status:** Identity/assistant persistence, session authentication, responsive shell, read-only Pi telemetry, bounded assistant gateway, task API/UI, reminder worker, notes/search, optional semantic/hybrid retrieval, grounded assistant note context and provenance, confirmation-gated host maintenance, confirmation-gated restore, retention cleanup, encryption key rotation, read-only workspace views, encrypted directory replication, and outbound email/push notification channels are implemented. PDF/OCR parsing, external URLs, automatic source synchronization, autonomous memory, and privileged host control remain deferred.
**Last updated:** 2026-08-04

Read this document with [`README.md`](../README.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`API.md`](API.md), [`DATABASE.md`](DATABASE.md), [`AI_SYSTEM.md`](AI_SYSTEM.md), [`SECURITY.md`](SECURITY.md), and [`ROADMAP.md`](ROADMAP.md) before changing code.

## Implemented Milestone 6 files

Backend:

- `app/modules/tasks/`: schemas, recurrence, service, and reminder processing.
- `app/api/routes/tasks.py`: authenticated task/category/tag/reminder/notification routes.
- `app/worker.py`: dedicated reminder worker entrypoint.
- `app/db/models.py`: task, series, reminder, notification, job, and approval persistence.
- `migrations/versions/0003_tasks_notifications.py`: reversible schema migration.
- `tests/test_tasks.py`: CRUD, CSRF, recurrence, worker, and assistant policy coverage.
- `tests/test_notes.py`, `test_search.py`, `test_retrieval.py`: notes, FTS5 search, ownership, chunks, and retrieval coverage.
- `migrations/versions/0004_notes_search.py`: notes, FTS5 projection, tags, and retrieval migration.
- `app/modules/host_actions/`: allowlisted action catalog, proposals, fixed SQLite backup/integrity adapters, and worker execution.
- `app/api/routes/host_actions.py`: authenticated catalog, confirmation, backup, job, and audit routes.
- `migrations/versions/0005_host_actions.py`: reversible host-action and backup metadata migration.
- `migrations/versions/0006_v1_hardening.py`: worker claim indexes for bounded SQLite scheduling.
- `migrations/versions/0007_workspace_views.py`: dedicated read-only workspace permission.
- `migrations/versions/0008_deployment_hardening.py`: encrypted/off-host backup metadata.
- `app/modules/backup_replication/`: bounded AES-GCM encryption and destination adapter.
- `app/modules/notifications/`: outbound email/push channel adapters, enqueue/resend service, and bounded delivery worker.
- `app/api/routes/notifications.py`: authenticated settings, test-send, and resend routes.
- `migrations/versions/0009_notification_channels.py`: per-channel delivery rows and the notification settings permission.
- `tests/test_notification_channels.py`: adapter, config, worker, lease, ownership, redaction, and route coverage.
- `app/modules/host_actions/restore.py`: confirmation-gated restore with safety backup, staging, digest/integrity verification, and atomic swap.
- `app/modules/backup_replication/encryption.py`: `decrypt_file()` bounded authenticated AES-GCM chunk decryption.
- `migrations/versions/0010_restore.py`: reversible `backup_records.restored_at` migration.
- `tests/test_restore.py`: local/encrypted restore, tamper, source resolution, safety-backup failure, ownership, and proposal flow coverage.
- `app/modules/host_actions/lifecycle.py`: retention policy, digest-safe pruning with last-backup protection, and idempotent encryption key rotation.
- `migrations/versions/0011_backup_lifecycle.py`: reversible `backup_records.pruned_at` migration.
- `tests/test_backup_lifecycle.py`: retention boundaries, pruning safety, path confinement, rotation idempotency, preview endpoint, and proposal pipeline coverage.
- `app/modules/workspace_views/`: approved-root Files, Projects, Git, and optional Docker adapters.
- `app/api/routes/workspace_views.py`: authenticated read-only workspace routes.
- `tests/test_workspace_views.py`: adapter, permission, authentication, and redaction coverage.
- `tests/test_host_actions.py`: proposal, CSRF, ownership, expiry, worker, backup, and audit coverage.

Frontend:

- `components/task-workspace.tsx`: task creation, filtering, completion, deletion, and state handling.
- `components/notification-center.tsx`: persistent notification polling, read actions, channel delivery indicators, and resend.
- `components/notification-settings.tsx`: channel status, masked credential state, and test-send controls.
- `components/assistant-action-confirmation.tsx`: task mutation confirmation UI.
- `lib/tasks.ts` and `lib/notifications.ts`: authenticated clients.
- `components/files-workspace.tsx`, `projects-workspace.tsx`, `git-workspace.tsx`, and `docker-workspace.tsx`: read-only workspace views.
- `lib/workspace-views.ts`: authenticated workspace view clients.
- `lib/auth.ts`: CSRF headers for browser mutations.

## Local setup

```sh
cp .env.example .env
python scripts/validate_env.py --env-file .env
```

Use a random local `JWT_SECRET` of at least 32 characters and keep `AI_PROVIDER=disabled` unless a server-side provider is intentionally configured. For hosted NVIDIA NIM validation, use `AI_PROVIDER=nvidia_nim`, `NVIDIA_API_KEY`, and a supported `AI_MODEL`; hosted endpoints are defaulted by the configuration boundary and private targets remain rejected.

## Backend validation

The v1.0 release validation set is intentionally explicit:

```sh
cd apps/api
python -m pip install -e '.[test]'
python -m pytest
python -m py_compile $(find app migrations tests -name '*.py' -print)
python -c "import cryptography; print(cryptography.__version__)"
python -m alembic heads
python -m alembic check  # may report pre-existing SQLite FTS5/legacy-index model drift; upgrade and migration tests remain authoritative
```

The current expected migration head is `0018_external_sources`. The migration suite also verifies upgrades from the legacy `0006_v1_hardening` head used by earlier deployments. The readiness check also requires the SQLite FTS5 notes index. Embeddings remain disabled unless an operator configures an approved provider.

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

The owner-only Admin status panel reports redacted system, AI-provider, embedding, storage, version, and migration state without exposing credentials. The task workspace, Notes/Search workspaces, Maintenance workspace, Notifications workspace, and read-only Files/Projects/Git/Docker workspaces are available from authenticated navigation. The notification center polls every 30 seconds and shows outbound email/push delivery state per item. Notes use synchronous SQLite FTS5 projection updates and deterministic retrieval chunks; optional embeddings are generated by the bounded worker and semantic/hybrid search falls back to lexical retrieval when unavailable. Grounded assistant requests use bounded owned-note context with persisted source provenance, while note content remains untrusted and cannot authorize tools. The assistant remains usable in disabled-provider mode for conversations; task mutations require a configured provider and explicit approval, while note tools are read-only.

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

The API, web, and worker target `linux/arm64`, use non-root runtime users, share the SSD-backed SQLite volume, and use a private network. The current environment lacks Docker, so Compose and target-Pi execution remain required external checks; the repository includes a deterministic Compose configuration check for CI or a Docker-enabled host.

## Security rules

- Every task/category/tag/reminder/notification query is user-scoped.
- Cookie mutations require CSRF.
- Assistant task writes require permissions, typed validation, expiry, explicit approval, and audit events.
- Task deletion is soft deletion.
- No provider key, token, backup encryption key, arbitrary command, filesystem path, Docker socket, privileged host operation, or SQL reaches the browser or task/host-action service.
- Host actions are proposed, explicitly confirmed, queued, fixed-adapter executed, and audited; backups remain on the configured data volume, and restore is confirmation-gated, verified, and atomic with a safety-backup rollback.
- Workspace views use server-configured roots, bounded adapters, sanitized output, and no browser-controlled paths or commands.

## Definition of done

A milestone is complete only when its code, tests, documentation, security implications, failure states, deployment behavior, and remaining limitations have been reviewed. Design text alone does not make a feature implemented.
