# NexusOS deployment

**Current milestone:** v1.4 — grounded assistant notes (unreleased)
**Status:** Hardened Compose/systemd/proxy configuration, encrypted off-host directory replication, confirmation-gated restore, retention cleanup, encryption key rotation, bounded worker recovery, optional semantic retrieval, grounded assistant note context and provenance, Maintenance deployment status, and outbound email/push notification channels are implemented. Target-Pi image, TLS trust, restore-drill validation, and real SMTP/ntfy endpoint checks remain required operator checks.
**Last updated:** 2026-08-04

## Target hardware

- Raspberry Pi 5, 8 GB
- Raspberry Pi OS Lite 64-bit
- Docker Engine and Compose v2
- External SSD mounted as host-side `DATA_DIR`

## Current Compose services

| Service | Current state | Purpose |
|---|---|---|
| `nexus-api` | Implemented | FastAPI identity, telemetry, assistant, productivity, integrations, plugin, and maintenance API |
| `nexus-web` | Implemented | Next.js authenticated shell and task workspace |
| `nexus-worker` | Implemented | Dedicated non-root ARM64 reminder and confirmed maintenance dispatcher |
| `nexus-proxy` | Hardened profile | ARM64 Caddy TLS/routing boundary; absent from default profile |
| `nexus-ai` | Opt-in placeholder profile | Optional future local/provider boundary |

The worker shares the API's SQLite data mount and read-only `/var/lib/nexus/plugins` mount, publishes no host port, and runs `python -m app.worker`. Run exactly one worker in the current deployment topology. If hosted NVIDIA NIM is enabled, the API and worker receive the server-side `NVIDIA_API_KEY` only through the private environment contract; never expose it to the web container or browser. Plugin code is trusted operator-installed code; use a separate VM/container boundary for untrusted extensions.

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

Ports remain loopback-only in the default topology. Do not expose this development topology directly to the internet. The hardened overlay is LAN-facing only and must use a trusted private hostname/certificate policy. Workspace views use `WORKSPACE_ROOTS`; Docker inspection remains unavailable unless an operator separately mounts and configures a reviewed socket boundary. A filesystem `:ro` mount does not make the Docker API read-only: access to the Docker Unix socket is a powerful host-control boundary. Never mount the Docker socket into the web or worker service.

## Plugin deployment

Leave `PLUGINS_DIR` empty to disable plugins. In Compose, set the host-side `PLUGINS_DIR` to a dedicated operator-owned directory; the default stack mounts it read-only at `/var/lib/nexus/plugins` in the API and worker and sets the in-container environment value automatically. Run a confirmed Plugins → Rescan directory action after adding or replacing a manifest. Keep plugin files separate from the database, backup, Docker socket, and secrets volumes. Verify the plugin directory is not writable by untrusted users. The broker uses no shell, a minimal secret-free environment, bounded wall time/output, and Linux resource limits on the Raspberry Pi.

## Workspace view deployment

Set `WORKSPACE_ROOTS` to a comma-separated list of approved absolute roots, or paths relative to `DATA_DIR`. Empty configuration scans only the configured data root. The API returns metadata only and does not accept request paths.

Docker metadata is disabled by default. If it is required for a trusted local deployment, mount the Docker Unix socket only into the API service using a deployment-local override, set `DOCKER_SOCKET_PATH` to the container path, and understand that socket access is a powerful host-control boundary—not a sandbox, even when the mount is marked `:ro`. Prefer a filtered/rootless Docker API proxy if this boundary must be exposed. Do not expose the socket to the browser, web service, worker, or assistant directly.

## Safe maintenance behavior

Maintenance actions are never direct shell commands. The UI or assistant creates an expiring proposal; the authenticated user must review and explicitly confirm it. Confirmation queues one durable job. The worker executes only the fixed SQLite backup, backup verification, integrity-check, or restore adapter and writes audit metadata.

Backups are stored beneath `${DATA_DIR}/db/backups` through the shared `/var/lib/nexus/data/backups` mount. They are hot SQLite backups, SHA-256 hashed, and checked with `PRAGMA integrity_check`. When both replication settings are configured, the worker encrypts each verified artifact in bounded AES-256-GCM chunks and writes it atomically beneath the operator-mounted `BACKUP_REPLICATION_DESTINATION`. The API exposes metadata only.

Restore is an explicit, confirmation-gated maintenance action (risk `high`). From the Maintenance workspace (or through the same proposal/confirm API flow), select one verified backup and confirm. The worker then creates a verified safety backup of the current database (rollback guarantee), stages the chosen source (the local verified backup, or the decrypted off-host artifact when `BACKUP_REPLICATION_DESTINATION` and `BACKUP_REPLICATION_KEY` are configured on the restoring host), re-verifies SHA-256 and integrity before touching anything, records a restore marker and audit row inside the staged database, swaps it in atomically, and cleans stale WAL/SHM/journal sidecars. NexusOS must be restarted after a successful restore; the UI and API result state this explicitly. Restore never accepts client paths, commands, or destinations.

Retention is a confirmed Maintenance action driven by `BACKUP_RETENTION_COUNT` (default 7) and `BACKUP_RETENTION_DAYS` (default 30): it keeps the newest verified backups and everything younger than the day window, always retains the newest backup, deletes only digest-matched local artifacts (and encrypted off-host artifacts when the destination is configured), soft-deletes the records, and audits each prune. Key rotation is a confirmed high-risk action: set `BACKUP_REPLICATION_KEY_PREVIOUS` to the old `BACKUP_ENCRYPTION_KEY` value, run the rotation, verify the Maintenance panel, then remove the previous key from the environment. Keys never cross the API or database.

Do not treat these backups as a complete disaster-recovery system yet: restore drills on the target Pi, retention tuning, and backup-before-migration automation remain operator deployment work. Replication is disabled unless both destination and key are configured.

## Reminder worker behavior

The worker polls due reminders and confirmed host actions in bounded batches. Host-action leases are reclaimed after a crash and terminally failed after three attempts; reminder notifications remain deduplicated across restarts. It claims pending or expired processing leases, creates one deduplicated in-app notification per reminder, marks successful reminders delivered, and cancels reminders whose tasks are completed, archived, or deleted. Worker restart is safe because notification deduplication is persisted.

## Hardened LAN deployment

```sh
docker compose --env-file .env -f docker-compose.yml -f infrastructure/compose/hardened.yml --profile hardened config --quiet
docker compose --env-file .env -f docker-compose.yml -f infrastructure/compose/hardened.yml --profile hardened up --build -d
```

Set `NEXUS_HOST` to a private LAN hostname. Caddy uses its internal CA; install `/data/caddy/pki/authorities/local/root.crt` on trusted clients, or replace the Caddy TLS policy with operator-provisioned certificates. The hardened overlay removes direct API/web host ports and publishes only the proxy on 80/443. The Caddy container uses the official image runtime with its default non-root `caddy` user (the named `/data` and `/config` volumes are initialized to that ownership by the image), a read-only root filesystem, drops all capabilities except `NET_BIND_SERVICE`, and requires `BACKUP_REPLICATION_HOST_PATH` to be set to a genuinely off-host or removable mount. `nexus.service` runs `docker compose up` in the foreground with `Restart=on-failure` so boot-time failures restart; per-container failures remain owned by the Compose `restart: unless-stopped` policy. Ensure the host `nexus` account can access Docker before enabling `nexus.service`; this is a deliberate host-level privilege boundary. Enable the unit only after validating the overlay and SSD mount.

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

Also test a due reminder, worker restart, notification deduplication, outbound email/push delivery and retry exhaustion, test-send and resend routes, note creation/update/search, grounded assistant retrieval with retrieved-source links, FTS5 rebuild behavior, proposal-without-execution, confirmation queueing, backup integrity, a local and an encrypted-artifact restore with restart, worker restart recovery, and healthcheck timing under representative Pi load. In production, set `NOTIFICATION_EMAIL_*` and/or `NOTIFICATION_PUSH_*` per the environment contract; the worker delivers reminders through the enabled channels with bounded batches and retries. Docker is unavailable in the current environment, so image builds, proxy startup, systemd boot, and restore-drill checks remain external validation rather than local claims. The local Alembic upgrade succeeds; `alembic check` currently reports pre-existing SQLite FTS5 virtual-table/legacy-index model drift outside Milestone 10. Confirm the target Python runtime includes SQLite FTS5.

## Recovery and production gate

The SSD is primary runtime storage, not a backup. Before production use, configure encrypted replication, perform a restore drill (including a restore from an empty data directory using an encrypted off-host artifact), install the systemd unit, validate the internal CA trust path, and document retention/key-rotation policy. Production monitoring and rollback automation remain operational follow-up work.
