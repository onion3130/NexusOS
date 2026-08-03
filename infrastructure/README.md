# Infrastructure skeleton

This directory contains deployment design and configuration boundaries for NexusOS. Milestone 1 adds only the API/web Dockerfiles; host-action code, reverse-proxy configuration, and production credentials remain deferred.

## Current state

- The root [`docker-compose.yml`](../docker-compose.yml) is the executable ARM64 development stack; API and web are real Milestone 1 services, while deferred services remain placeholders.
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
