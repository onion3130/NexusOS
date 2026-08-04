# Infrastructure skeleton

This directory contains deployment design and configuration boundaries for NexusOS.

## Current state

- The root [`docker-compose.yml`](../docker-compose.yml) is the executable ARM64 development stack.
- API, web, and the v1.0 reminder/maintenance worker are real non-root services.
- The default profile keeps the proxy as a placeholder; `compose/hardened.yml` supplies an opt-in ARM64 Caddy TLS/routing boundary.
- The optional AI service remains a placeholder boundary.
- `compose/README.md` documents future profile splits.
- `systemd/README.md` documents the Raspberry Pi startup, upgrade, rollback, and recovery unit.
- `healthchecks/README.md` documents the liveness/readiness and worker health contracts.

## Rules

- Only reviewed services may be added to a deployment profile.
- Only the reverse proxy may publish host ports in a normal deployment.
- Application, database, worker, and AI services remain on a private network.
- Secrets are supplied through local environment files or Docker secrets, never committed files.
- ARM64 images must be verified before a Pi deployment tag.
- Runtime data belongs on the external SSD and is never part of a build context.
- The worker must use bounded batches and never expose a host port.
