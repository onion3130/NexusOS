# Compose profile skeleton

The root `docker-compose.yml` is the current source of truth for the Phase 0 no-op scaffold. This directory reserves the profile split for implementation milestones without pretending that application images already exist.

## Planned profiles

| Profile | Purpose | Introduced |
|---|---|---|
| default | Local ARM64 foundation and core services | Phase 0 / current scaffold |
| `dev` | Hot-reload API/web development dependencies | Milestone 1 |
| `pi` | Raspberry Pi deployment with SSD mounts and recovery policies | Deployment milestone |
| `postgres` | PostgreSQL compatibility and migration validation | Persistence milestone |
| `ai` | Explicitly enabled external/local model boundary | Assistant milestone |

Each future profile must document image provenance, ARM64 support, healthchecks, resource limits, volumes, networks, secrets, and rollback behavior. Do not add a placeholder Dockerfile solely to make a profile appear runnable.

## Validation

From the repository root, when Docker is installed:

```sh
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
docker compose --env-file .env down
```

The current no-op containers do not expose a web UI or API endpoint. They validate topology only.
