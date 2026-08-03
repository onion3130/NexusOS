# NexusOS deployment

**Current milestone:** Milestone 9 — files, projects, Git, and Docker views
**Status:** v1.0.0 private/local-first release with a real API, web shell, reminder/maintenance worker, notes, SQLite FTS5 search, read-only workspace views, confirmation-gated backups, bounded worker recovery, and audit visibility. Reverse-proxy TLS, off-host encrypted replication, and restore drills remain operational follow-up work.
**Last updated:** 2026-08-03

## Target hardware

- Raspberry Pi 5, 8 GB
- Raspberry Pi OS Lite 64-bit
- Docker Engine and Compose v2
- External SSD mounted as host-side `DATA_DIR`

## Current Compose services

| Service | Current state | Purpose |
|---|---|---|
| `nexus-api` | Implemented | FastAPI identity, telemetry, assistant, task, reminder, and notification API |
| `nexus-web` | Implemented | Next.js authenticated shell and task workspace |
| `nexus-worker` | Implemented | Dedicated non-root ARM64 reminder and confirmed maintenance dispatcher |
| `nexus-proxy` | Placeholder | Future TLS/routing boundary |
| `nexus-ai` | Opt-in placeholder profile | Optional future local/provider boundary |

The worker shares the API's SQLite data mount, publishes no host port, and runs `python -m app.worker`. Run exactly one worker in the current deployment topology.

## Development deployment

1. Verify the external SSD mount and create `${DATA_DIR}/db` and `${DATA_DIR}/logs`.
2. Ensure UID 10001 can write the API and worker database/log mounts.
3. Copy `.env.example` to `.env` and replace the JWT placeholder.
4. Validate configuration:

   ```sh
   python scripts/validate_env.py --env-file .env
   docker compose --env-file .env config --quiet
   ```

5. Apply the explicit migration and bootstrap the first owner:

   ```sh
   docker compose --env-file .env run --rm nexus-api python -m alembic upgrade head
   docker compose --env-file .env run --rm nexus-api python -m app.cli.bootstrap_owner --username owner
   ```

6. Build and start:

   ```sh
   docker compose --env-file .env up --build -d
   docker compose --env-file .env ps
   ```

7. Check `/api/v1/health/live`, `/api/v1/health/ready`, and `http://127.0.0.1:3000`.
8. Stop with `docker compose --env-file .env down`.

Ports remain loopback-only in the default topology. Do not expose this development topology directly to the internet. Workspace views use `WORKSPACE_ROOTS`; Docker inspection remains unavailable unless an operator separately mounts and configures a reviewed socket boundary. A filesystem `:ro` mount does not make the Docker API read-only: access to the Docker Unix socket is a powerful host-control boundary. Never mount the Docker socket into the web or worker service.

## Workspace view deployment

Set `WORKSPACE_ROOTS` to a comma-separated list of approved absolute roots, or paths relative to `DATA_DIR`. Empty configuration scans only the configured data root. The API returns metadata only and does not accept request paths.

Docker metadata is disabled by default. If it is required for a trusted local deployment, mount the Docker Unix socket only into the API service using a deployment-local override, set `DOCKER_SOCKET_PATH` to the container path, and understand that socket access is a powerful host-control boundary—not a sandbox, even when the mount is marked `:ro`. Prefer a filtered/rootless Docker API proxy if this boundary must be exposed. Do not expose the socket to the browser, web service, worker, or assistant directly.

## Safe maintenance behavior

Maintenance actions are never direct shell commands. The UI or assistant creates an expiring proposal; the authenticated user must review and explicitly confirm it. Confirmation queues one durable job. The worker executes only the fixed SQLite backup, backup verification, or integrity-check adapter and writes audit metadata.

Backups are stored beneath `${DATA_DIR}/db/backups` through the shared `/var/lib/nexus/data/backups` mount. They are hot SQLite backups, SHA-256 hashed, and checked with `PRAGMA integrity_check`. The API exposes metadata only.

Do not treat these backups as a complete disaster-recovery system yet: restore, off-host replication, encryption, retention, and backup-before-migration automation remain future deployment work. To recover manually, stop API and worker, preserve the existing database, copy a verified backup over the database path using an operator-controlled procedure, then run `PRAGMA integrity_check` and `alembic upgrade head` before restarting. Never expose restore as an AI or browser action.

## Reminder worker behavior

The worker polls due reminders and confirmed host actions in bounded batches. Host-action leases are reclaimed after a crash and terminally failed after three attempts; reminder notifications remain deduplicated across restarts. It claims pending or expired processing leases, creates one deduplicated in-app notification per reminder, marks successful reminders delivered, and cancels reminders whose tasks are completed, archived, or deleted. Worker restart is safe because notification deduplication is persisted.

## Raspberry Pi validation gate

On the Pi or another Docker-enabled ARM64 environment, validate:

```sh
docker compose --env-file .env config --quiet
docker compose --env-file .env build --no-cache nexus-api nexus-web nexus-worker
docker compose --env-file .env up -d

docker compose --env-file .env ps
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
docker compose --env-file .env down
```

Also test a due reminder, worker restart, notification deduplication, note creation/update/search, FTS5 rebuild behavior, proposal-without-execution, confirmation queueing, backup integrity, worker restart recovery, and healthcheck timing under representative Pi load. Docker is unavailable in the current environment, so these checks remain external validation rather than a local claim. Confirm the target Python runtime includes SQLite FTS5.

## Recovery and production gate

The SSD is primary runtime storage, not a backup. Before production use, add encrypted rotating backups, restore drills, backup-before-migration policy, reverse-proxy TLS, systemd startup, resource limits, logging/monitoring, and rollback automation.
