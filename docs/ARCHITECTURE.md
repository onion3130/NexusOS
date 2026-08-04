# NexusOS architecture

**Current milestone:** Milestone 10 — deployment hardening
**Status:** Current runtime is a FastAPI health/identity/system/assistant/tasks/notes/host-actions/workspace-views service, a dedicated bounded SQLite worker, and an authenticated modular Next.js shell.
**Last updated:** 2026-08-03

NexusOS remains a local-first modular monolith for a Raspberry Pi 5 with an external SSD. The browser, API, persistence, worker, provider, and future host-action boundaries remain separate.

## Runtime components

- `apps/api`: FastAPI application with identity, read-only telemetry, workspace views, assistant gateway, tasks, reminders, and notifications.
- `apps/api/app/modules/tasks`: task service, schemas, recurrence calculator, and reminder dispatcher.
- `apps/api/app/modules/notes`: canonical notes, SQLite FTS5 search, deterministic chunks, and source-aware retrieval.
- `apps/api/app/modules/host_actions`: typed action catalog, proposal lifecycle, SQLite backups, fixed executor, and worker processing.
- `apps/api/app/worker.py`: dedicated bounded SQLite reminder and confirmed host-action worker.
- `apps/api/app/db`: SQLAlchemy engine/session and all persisted models.
- `apps/api/migrations`: explicit Alembic migration history through `0008_deployment_hardening`.
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
  ├── notes service -> notes/tags/search projection/retrieval chunks
  ├── host-actions service -> typed proposals -> confirmed job queue -> fixed backup/integrity adapters
  ├── workspace-views service -> approved-root file/project/Git adapters -> optional Docker metadata adapter
  └── backup-replication service -> bounded AES-GCM encryption -> operator-mounted destination adapter

Dedicated worker -> SQLite reminder claims -> notifications
Dedicated worker -> confirmed host-action claims -> verified backup/integrity results
Dedicated worker -> encrypted backup replication claims with leases/retries

Docker Compose -> private bridge network
  ├── nexus-api
  ├── nexus-web
  ├── nexus-worker
  ├── nexus-proxy (placeholder)
  └── nexus-ai (opt-in placeholder profile)
```

The API and worker share the SQLite database on the external SSD. The worker has no published port. Host actions are limited to SQLite APIs under a fixed data-directory boundary; workspace views use approved roots and an optional API-only Docker socket. Docker socket access is a powerful host-control boundary even with a filesystem `:ro` mount, so it is disabled by default and must be separately reviewed; no browser-facing shell, privileged command, or arbitrary filesystem operation exists.

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

## Safe host-action architecture

Host operations are represented as typed, expiring proposals. Creating a proposal is inert. An authenticated user with `system.host_actions` must explicitly confirm it, after which one durable job is queued. The worker claims the job and invokes only a server-owned adapter. Proposal, confirmation, rejection, success, and failure transitions are audit events.

The current catalog provides database backup creation, backup verification, and SQLite integrity checking. Backups use Python's SQLite online backup API, fixed `DATA_DIR/backups` storage, SHA-256 metadata, and integrity checks. Optional replication uses bounded AES-256-GCM chunks and an operator-mounted destination adapter. Restore, reboot, shutdown, systemd control, package management, Docker control, and arbitrary commands remain excluded from the assistant and browser.

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

## Workspace view architecture

Milestone 9 exposes live read-only metadata beneath server-configured approved roots. Files are bounded direct filesystem metadata scans; projects use safe marker discovery; Git uses fixed commands with timeout and output bounds; Docker inspection is disabled unless an operator explicitly supplies a Unix socket boundary. The Docker endpoint issues only a fixed metadata request, but socket access itself is not a security sandbox and can control the daemon; use only in a trusted, separately reviewed deployment. No workspace view accepts arbitrary paths, commands, container controls, or file contents.

## Notes and retrieval architecture

Notes are canonical user-authored sources. A derived search projection feeds SQLite FTS5, while deterministic versioned chunks provide provenance for future RAG. Search and retrieval always join through owned canonical notes. Assistant note tools are read-only and return bounded, explicitly source-labeled content; retrieved text is untrusted context and cannot grant tool permissions.

## Deferred scope

Not implemented today:

- Streaming assistant responses
- Email, SMS, push, or calendar notification channels
- Embeddings, vector search, and semantic memory extraction
- External document ingestion and file sources
- Privileged host actions and service/container control
- File contents, project execution, Git mutations, and Docker control
- Automated restore, key rotation, retention policy, production monitoring, and public-internet ingress
- Plugin loading and package verification

See [`ROADMAP.md`](ROADMAP.md) and [`DEVELOPMENT.md`](DEVELOPMENT.md).

## Raspberry Pi and operational limits

The API/web/worker/proxy images target `linux/arm64` and run with bounded resource policies in the hardened profile. Worker polling, reminder batches, host-action batches, and replication batches are bounded. Backup work is throttled through SQLite's online backup controls and encryption reads 1 MiB chunks. Docker image builds, Caddy internal-CA trust, cold boot, SSD-mount delay, and sustained-load/healthcheck timing must still be smoke-tested on the target Pi. Docker is not available in the current development environment.
