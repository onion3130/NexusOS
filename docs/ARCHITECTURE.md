# NexusOS architecture

**Current milestone:** v1.5 — external source ingestion and source lifecycle management (unreleased)
**Status:** Current runtime is a FastAPI health/identity/system/assistant/tasks/notes/host-actions/workspace-views/notifications service with grounded note context, a dedicated bounded SQLite worker, and an authenticated modular Next.js shell.
**Last updated:** 2026-08-04

NexusOS remains a local-first modular monolith for a Raspberry Pi 5 with an external SSD. The browser, API, persistence, worker, provider, and future host-action boundaries remain separate.

## Runtime components

- `apps/api`: FastAPI application with identity, read-only telemetry, workspace views, assistant gateway, tasks, reminders, notifications, and outbound channel delivery.
- `apps/api/app/modules/tasks`: task service, schemas, recurrence calculator, and reminder dispatcher.
- `apps/api/app/modules/notifications`: channel settings, outbound email/push adapters, enqueue/resend service, and bounded delivery worker.
- `apps/api/app/modules/notes`: canonical notes, SQLite FTS5 search, deterministic chunks, and source-aware retrieval.
- `apps/api/app/modules/sources`: bounded UTF-8 text/Markdown uploads, approved-root imports, source lifecycle, immutable versions, deterministic chunks, and worker ingestion.
- `apps/api/app/modules/host_actions`: typed action catalog, proposal lifecycle, SQLite backups, confirmation-gated restore, retention cleanup/key rotation, plugin lifecycle actions, fixed executor, and worker processing.
- `apps/api/app/modules/plugins`: validated manifests, approved-directory discovery, secret-free JSON-stdio subprocess broker, bounded run history, and capability/risk enforcement.
- `apps/api/app/worker.py`: dedicated bounded SQLite reminder, confirmed host-action, replication, notification-delivery, media-rescan, and embedding worker.
- `apps/api/app/db`: SQLAlchemy engine/session and all persisted models.
- `apps/api/migrations`: explicit Alembic migration history through `0019_source_sync`.
- `apps/web`: authenticated Next.js shell with overview, assistant, tasks, notifications, and notification settings.
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
  ├── sources service -> server-owned source storage -> durable ingestion -> versions/chunks -> retrieval
  ├── source synchronization -> approved-root revalidation -> bounded sync jobs -> existing ingestion pipeline
  ├── host-actions service -> typed proposals -> confirmed job queue -> fixed backup/integrity adapters
  ├── workspace-views service -> approved-root file/project/Git adapters -> optional Docker metadata adapter
  ├── backup-replication service -> bounded AES-GCM encryption -> operator-mounted destination adapter
  ├── notifications service -> channel settings -> email (SMTP) / push (ntfy) outbound adapters
  ├── plugins service -> approved manifest registry -> out-of-process JSON-stdio broker
  └── provider gateway -> optional NVIDIA NIM/OpenAI-compatible chat and embeddings -> bounded worker batches -> serialized vectors

Dedicated worker -> SQLite reminder claims -> notifications -> enqueued channel deliveries
Dedicated worker -> bounded external source ingestion -> immutable versions/chunks
Dedicated worker -> confirmed host-action claims -> verified backup/integrity/restore results
Dedicated worker -> encrypted backup replication claims with leases/retries
Dedicated worker -> outbound channel delivery claims with leases/retries -> email/push

Docker Compose -> private bridge network
  ├── nexus-api
  ├── nexus-web
  ├── nexus-worker
  ├── nexus-proxy (placeholder)
  └── nexus-ai (opt-in placeholder profile)
```

The API and worker share the SQLite database on the external SSD. The owner-only admin status endpoint reads validated process configuration and database readiness but returns only redacted allowlisted status; it never edits `.env` or exposes secrets. The worker has no published port. Host actions are limited to SQLite APIs under a fixed data-directory boundary; workspace views use approved roots and an optional API-only Docker socket. Docker socket access is a powerful host-control boundary even with a filesystem `:ro` mount, so it is disabled by default and must be separately reviewed; no browser-facing shell, privileged command, or arbitrary filesystem operation exists.

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

## Notification channel architecture

The notifications module is outbound-only. The reminder worker enqueues one `notification_channel_deliveries` row per enabled channel at notification creation; no inbound listener or webhook exists. A dedicated worker cycle claims pending rows with bounded batches and processing leases, dispatches through the server-configured adapter (SMTP email or ntfy-compatible push), and retries up to three times before a terminal audit failure. A channel disabled between enqueue and processing is skipped. Secrets (SMTP password, push token) live only in server environment configuration, are never persisted, returned, or logged, and push endpoints reject embedded credentials, loopback, link-local, and metadata hosts while permitting private LAN addresses for self-hosted servers. The assistant cannot trigger delivery; notifications follow the same worker pipeline as the API.

## Safe host-action architecture

Host operations are represented as typed, expiring proposals. Creating a proposal is inert. An authenticated user with `system.host_actions` must explicitly confirm it, after which one durable job is queued. The worker claims the job and invokes only a server-owned adapter. Proposal, confirmation, rejection, success, and failure transitions are audit events.

The current catalog provides database backup creation, backup verification, SQLite integrity checking, and database restore. Backups use Python's SQLite online backup API, fixed `DATA_DIR/backups` storage, SHA-256 metadata, and integrity checks. Optional replication uses bounded AES-256-GCM chunks and an operator-mounted destination adapter; `decrypt_file()` authenticates each chunk in memory-bounded reads and returns the plaintext digest for cross-verification.

Restore is the highest-risk catalogued action and runs only in the worker after the standard propose → confirm flow. The worker first creates a verified safety backup of the live database (rollback guarantee), stages the source (a local verified backup, or a decrypted off-host artifact when the replication key is configured), re-verifies SHA-256 and SQLite integrity before anything is replaced, records a restore marker and audit row inside the staged database, swaps it in atomically, and cleans stale sidecars. A successful restore requires an API/worker restart. Reboot, shutdown, systemd control, package management, Docker control, and arbitrary commands remain excluded from the assistant and browser.

Backup lifecycle completes the operational loop with two more catalogued actions. Retention cleanup (`medium`) prunes verified backups beyond the server-configured policy (`BACKUP_RETENTION_COUNT` / `BACKUP_RETENTION_DAYS`); the newest verified backup is always retained, local artifacts are deleted only when their digest still matches the trusted record, encrypted off-host artifacts are deleted when the destination is configured, and every prune is a soft-delete with an audit row. Key rotation (`high`) re-encrypts every replicated artifact from `BACKUP_REPLICATION_KEY_PREVIOUS` to the current `BACKUP_ENCRYPTION_KEY` in bounded authenticated chunks with atomic replace, staging cleanup, and idempotent retries; keys are environment-only and never cross the API.

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

Notes are canonical user-authored sources. A derived search projection feeds SQLite FTS5, while deterministic versioned chunks provide provenance for RAG. Optional provider-scoped embeddings are generated asynchronously and stored as bounded serialized vectors; hybrid retrieval combines lexical and semantic scores while retaining lexical fallback. Search and retrieval always join through owned canonical notes. Assistant note tools are read-only and return bounded, explicitly source-labeled content. Grounded assistant requests assemble a bounded, explicitly delimited untrusted context and persist source provenance on the assistant message; retrieved text cannot grant tool permissions.

## External source architecture

External source uploads are stored with generated filenames beneath `DATA_DIR/sources`; the browser never selects a destination. Approved-file imports use opaque server-issued file IDs and revalidate the configured root, symlink state, size, hash, and UTF-8 content immediately before copying. Optional synchronization stores only the approved root key, relative path, opaque file identifier, bounded interval, and redacted timestamps; every worker check rescans and revalidates the configured root before reading. Changed content is copied atomically into generated private storage and sent through the existing leased ingestion pipeline. The worker uses bounded batches, retries, and no-change hash checks. Source content participates in lexical retrieval as untrusted reference material; it cannot authorize tools or mutate the system.

## Deferred scope

Not implemented today:

- Streaming assistant responses
- SMS and calendar notification channels (email and push are implemented)
- Autonomous memory extraction and model-written notes
- External document ingestion and file sources
- Privileged host actions and service/container control
- File contents, project execution, Git mutations, and Docker control
- Production monitoring and public-internet ingress
- Plugin package signing and third-party trust verification

See [`ROADMAP.md`](ROADMAP.md) and [`DEVELOPMENT.md`](DEVELOPMENT.md).

## Raspberry Pi and operational limits

The API/web/worker/proxy images target `linux/arm64` and run with bounded resource policies in the hardened profile. Worker polling, reminder batches, host-action batches, and replication batches are bounded. Backup work is throttled through SQLite's online backup controls and encryption reads 1 MiB chunks. Docker image builds, Caddy internal-CA trust, cold boot, SSD-mount delay, and sustained-load/healthcheck timing must still be smoke-tested on the target Pi. Docker is not available in the current development environment.
