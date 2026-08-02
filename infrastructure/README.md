# Infrastructure skeleton

This directory contains deployment design and configuration boundaries for NexusOS. It intentionally contains no application images, Dockerfiles, host-action code, or production credentials until the owner approves the Phase 1 architecture.

## Current state

- The root [`docker-compose.yml`](../docker-compose.yml) is the executable ARM64 no-op foundation scaffold.
- `compose/README.md` documents the planned profile split.
- `systemd/README.md` documents the planned Raspberry Pi startup unit.
- `healthchecks/README.md` documents the healthcheck contract; executable healthchecks begin with Milestone 1.

## Rules

- Only reviewed services may be added to a deployment profile.
- Only the reverse proxy may publish host ports in a normal deployment.
- Application, database, worker, and AI services remain on a private network.
- Secrets are supplied through local environment files or Docker secrets, never committed files.
- ARM64 images must be verified before a Pi deployment tag.
- Runtime data belongs on the external SSD and is never part of a build context.
