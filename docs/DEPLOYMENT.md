# NexusOS deployment guide

**Status:** Design only — deployment automation begins after application milestones.

## Target topology

- Raspberry Pi 5, 8 GB, Raspberry Pi OS Lite 64-bit
- Docker Engine and Compose v2
- External SSD mounted for `DATA_DIR`
- Private Compose network for web, API, worker, database, and adapters
- Reverse proxy as the only normally published service
- Optional external AI provider; no NVIDIA NIM container is assumed on the Pi

## Deployment sequence

1. Prepare and verify the SSD mount and filesystem permissions.
2. Clone a reviewed tag into a dedicated service directory.
3. Copy `.env.example` to `.env` and supply secrets through a protected local mechanism.
4. Run the environment validator and `docker compose config`.
5. Pull/build only reviewed ARM64 images.
6. Start with the approved Compose profile and inspect readiness.
7. Run a smoke check and record the deployment version.
8. Verify backup age and restore status.

## Recovery

- Compose uses healthchecks and `restart: unless-stopped` for long-running services.
- Readiness failures must not be hidden by a passing process-level liveness check.
- Rollback uses the previous reviewed image/tag and documented database migration procedure.
- Reboot and shutdown actions are disabled until owner approval, confirmation UX, audit logging, and recovery procedures exist.

## Current limitation

The repository currently contains only no-op placeholders and architecture documents. There are no deployable web/API images, reverse-proxy configuration, systemd unit, migrations, or backup scripts yet. Do not use the current scaffold as a production service.
