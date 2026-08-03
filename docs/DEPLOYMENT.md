# NexusOS deployment

**Current milestone:** Milestone 6 tasks, reminders, and notifications
**Status:** Local/ARM64 development deployment with a real API, web shell, and reminder worker. Production hardening is not complete.
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
| `nexus-worker` | Implemented | Dedicated non-root ARM64 reminder dispatcher |
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

Ports remain loopback-only. Do not expose this development topology directly to the internet.

## Reminder worker behavior

The worker polls due reminders in bounded batches. It claims pending or expired processing leases, creates one deduplicated in-app notification per reminder, marks successful reminders delivered, and cancels reminders whose tasks are completed, archived, or deleted. Worker restart is safe because notification deduplication is persisted.

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

Also test a due reminder, worker restart, notification deduplication, and healthcheck timing under representative Pi load. Docker is unavailable in the current environment, so these checks remain external validation rather than a local claim.

## Recovery and production gate

The SSD is primary runtime storage, not a backup. Before production use, add encrypted rotating backups, restore drills, backup-before-migration policy, reverse-proxy TLS, systemd startup, resource limits, logging/monitoring, and rollback automation.
