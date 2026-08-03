# NexusOS deployment guide

**Status:** Milestone 1 development deployment implemented; production hardening remains deferred.
**Last updated:** 2026-08-02

## Target topology

- Raspberry Pi 5, 8 GB, Raspberry Pi OS Lite 64-bit
- Docker Engine and Compose v2
- External SSD mounted for `DATA_DIR`
- Private Compose network for web, API, worker, database, and adapters
- API and web images built from reviewed ARM64-compatible Dockerfiles
- Reverse proxy remains a deferred placeholder; development binds API/web to loopback ports only
- Optional external AI provider; no NVIDIA NIM container is assumed on the Pi

## Milestone 1 deployment

1. Prepare and verify the SSD mount and filesystem permissions.
2. Clone a reviewed commit into a dedicated service directory.
3. Create the SSD-backed data directories and grant them to the API runtime UID 10001.
4. Copy `.env.example` to `.env` and supply a non-placeholder JWT secret.
5. Run `python scripts/validate_env.py --env-file .env`.
6. Run `docker compose --env-file .env config --quiet`.
7. Build/start the foundation: `docker compose --env-file .env up --build -d`.
8. Verify `http://127.0.0.1:8000/api/v1/health/live`, readiness, and the web shell on port 3000.
9. Record the deployed commit and inspect `docker compose ps` health states.

## Recovery

- Compose uses healthchecks and `restart: unless-stopped` for long-running services.
- Readiness failures must not be hidden by a passing process-level liveness check.
- Rollback uses the previous reviewed commit/image and documented database migration procedure.
- Reboot and shutdown actions are disabled until owner approval, confirmation UX, audit logging, and recovery procedures exist.

## Documentation handoff

For development and configuration contracts, see [`DEVELOPMENT.md`](DEVELOPMENT.md), [`ENVIRONMENT.md`](ENVIRONMENT.md), and [`DATABASE.md`](DATABASE.md). AI provider deployment boundaries are documented in [`AI_SYSTEM.md`](AI_SYSTEM.md). The architecture and API documents distinguish planned topology from the services that actually run today.

## Current limitation

Milestone 1 does not provide authentication, database persistence, reverse-proxy TLS, systemd startup, migrations, backups, AI calls, or feature modules. Do not expose the development ports publicly. Production deployment begins only after those controls are implemented and reviewed.
