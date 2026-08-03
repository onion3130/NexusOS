# NexusOS architecture

**Current milestone:** Milestone 7 — notes, search, and retrieval foundations implemented
**Status:** Current runtime is a FastAPI health/identity/system/assistant/tasks/notes service, a dedicated SQLite reminder worker, and an authenticated modular Next.js shell.
**Last updated:** 2026-08-03

NexusOS remains a local-first modular monolith for a Raspberry Pi 5 with an external SSD. The browser, API, persistence, worker, provider, and future host-action boundaries remain separate.

## Runtime components

- `apps/api`: FastAPI application with identity, read-only telemetry, assistant gateway, tasks, reminders, and notifications.
- `apps/api/app/modules/tasks`: task service, schemas, recurrence calculator, and reminder dispatcher.
- `apps/api/app/modules/notes`: canonical notes, SQLite FTS5 search, deterministic chunks, and source-aware retrieval.
- `apps/api/app/worker.py`: dedicated bounded SQLite reminder worker.
- `apps/api/app/db`: SQLAlchemy engine/session and all persisted models.
- `apps/api/migrations`: explicit Alembic migration history through `0004_notes_search`.
- `apps/web`: authenticated Next.js shell with overview, assistant, tasks, and notification center.
- `docker-compose.yml`: ARM64 development topology with API, web, and real worker services; proxy and optional AI remain placeholders.

## Implemented boundary

```text
Browser -> authenticated Next.js shell -> same-origin `/api/v1` rewrite -> FastAPI

FastAPI
  ├── identity/session boundary
  ├── read-only system telemetry
  ├── bounded assistant gateway -> typed tool registry
  ├── tasks service -> tasks/categories/tags/reminders/notifications
  └── notes service -> notes/tags/search projection/retrieval chunks

Dedicated worker -> SQLite reminder claims -> persistent in-app notifications

Docker Compose -> private bridge network
  ├── nexus-api
  ├── nexus-web
  ├── nexus-worker
  ├── nexus-proxy (placeholder)
  └── nexus-ai (opt-in placeholder profile)
```

The API and worker share the SQLite database on the external SSD. The worker has no published port and performs no host actions.

## Task architecture

The task module owns:

- Task and category/tag validation
- User ownership checks
- Task CRUD and completion transitions
- Constrained recurrence calculation
- Reminder scheduling and cancellation
- Notification query/read state
- Task mutation audit events

The worker owns only scheduled reminder delivery. It claims bounded batches, uses processing leases for restart recovery, and uses a unique deduplication key to avoid duplicate notifications.

## Assistant action architecture

The assistant gateway may propose task actions, but the task service remains authoritative. Create, update, complete, and delete tools are permissioned and confirmation-gated. Approval and rejection endpoints verify conversation ownership, expiry, permissions, and typed arguments. Delete is soft deletion.

## Important decisions

### Modular monolith first

The API keeps feature modules in one deployable process. The worker is a separate process because scheduled work should not depend on web-request lifetime.

### SQLite first

SQLite minimizes idle Pi resource use. WAL mode, foreign keys, short transactions, bounded batches, and SSD storage are required.

### Private by default

Development ports bind to loopback. No TLS, LAN exposure, public access, or host-control boundary is introduced by Milestone 6.

### Typed and auditable actions

No arbitrary shell command, Docker argument, filesystem path, SQL, or provider URL is accepted from model output or browser input. User-owned mutations are validated, permissioned, CSRF-protected for cookies, and audited.

## Notes and retrieval architecture

Notes are canonical user-authored sources. A derived search projection feeds SQLite FTS5, while deterministic versioned chunks provide provenance for future RAG. Search and retrieval always join through owned canonical notes. Assistant note tools are read-only and return bounded, explicitly source-labeled content; retrieved text is untrusted context and cannot grant tool permissions.

## Deferred scope

Not implemented today:

- Streaming assistant responses
- Email, SMS, push, or calendar notification channels
- Embeddings, vector search, and semantic memory extraction
- External document ingestion and file sources
- Host actions and service/container control
- Files, projects, Git, Docker views
- Production reverse proxy, systemd, encrypted backups, restore drills, limits, and monitoring
- Plugin loading and package verification

See [`ROADMAP.md`](ROADMAP.md) and [`DEVELOPMENT.md`](DEVELOPMENT.md).

## Raspberry Pi and operational limits

The API/web/worker images target `linux/arm64` and run non-root. Worker polling and batch sizes are configuration-bounded. Compose remains development infrastructure; Docker image builds and sustained-load/healthcheck timing must be validated on the target Pi before production use. Docker is not available in the current development environment, so local Compose validation is deferred to a Docker-enabled or Pi environment.
