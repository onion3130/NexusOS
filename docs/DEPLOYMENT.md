# NexusOS deployment

**Current milestone:** Milestone 5 assistant gateway deployment
**Status:** Local/ARM64 foundation only. Production hardening is not complete.
**Last updated:** 2026-08-02

## Target hardware

- Raspberry Pi 5, 8 GB
- Raspberry Pi OS Lite 64-bit
- Docker Engine and Compose v2
- External SSD mounted as the host-side `DATA_DIR`

## Current Compose services

| Service | Current state | Purpose |
|---|---|---|
| `nexus-api` | Implemented | FastAPI health/identity/system/assistant service, non-root, port 8000 on loopback |
| `nexus-web` | Implemented | Next.js authenticated shell, non-root, port 3000 on loopback |
| `nexus-proxy` | Placeholder | Future TLS/routing boundary |
| `nexus-worker` | Placeholder | Future jobs, reminders, backups, and scans |
| `nexus-ai` | Opt-in placeholder profile | Future local/provider boundary |

All services use the private `nexus-private` bridge network.The web image's same-origin `/api/v1` rewrite targets `nexus-api:8000` inside that network, while local development defaults to `127.0.0.1:8000`. The shell itself adds no new runtime service or native dependency.
 The development Compose file does not include a database container; SQLite is stored in the API-mounted `/var/lib/nexus/data` volume. Run the explicit owner bootstrap/migration command before expecting readiness.

## Development deployment

1. Install Docker Compose v2 and verify the SSD mount.
2. Clone a reviewed commit.
3. Create host directories for `DATA_DIR/db` and `DATA_DIR/logs`.
4. Ensure the API container runtime user (UID 10001) can write the mounted API directories.
5. Copy `.env.example` to `.env` and replace the JWT placeholder.
6. Build/run the explicit owner bootstrap inside the API container so the configured `/var/lib/nexus/data` path and mounted host database are used:

   ```sh
   docker compose --env-file .env run --rm nexus-api python -m app.cli.bootstrap_owner --username owner
   ```
7. Validate configuration:

   ```sh
   python scripts/validate_env.py --env-file .env
   ```

8. Validate and start:

   ```sh
   docker compose --env-file .env config --quiet
   docker compose --env-file .env up --build -d
   docker compose --env-file .env ps
   ```

9. Check `http://127.0.0.1:8000/api/v1/health/live`, `/api/v1/health/ready`, and `http://127.0.0.1:3000`.
10. Stop with `docker compose --env-file .env down`.

Do not expose ports 3000 or 8000 directly to the internet. No TLS, remote access, or production reverse proxy exists yet; the current authentication boundary is intended for the local development topology.

## Recovery and operations

Compose uses `restart: unless-stopped` and bounded healthchecks. Liveness confirms the API process responds; readiness confirms storage plus the migrated identity database. A passing liveness check does not mean future feature modules are ready.

The external SSD is primary runtime storage, not a backup. Read-only telemetry reports the configured data volume but does not perform host actions. Assistant conversations and bounded model-run metadata use the same SQLite volume; provider calls are outbound-only, optional, and disabled by default. Encrypted rotating backups, restore verification, systemd startup, resource limits, storage alerts, and upgrade/rollback automation are future deployment work.

## Production gate

Do not call the system production-ready until the following exist and are tested:

- Backup-before-migration policy and tested restore process.
- Reverse-proxy TLS and approved remote-access boundary.
- Systemd startup after network and SSD readiness.
- Encrypted backups with a successful restore drill.
- ARM64 image validation, resource limits, logging, and monitoring.
- Safe authorization/audit controls for any host actions.

See [`DEVELOPMENT.md`](DEVELOPMENT.md), [`ENVIRONMENT.md`](ENVIRONMENT.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), and [`ROADMAP.md`](ROADMAP.md).
