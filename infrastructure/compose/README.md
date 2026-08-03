# Compose profile skeleton

The root `docker-compose.yml` is the current source of truth for the Milestone 1 development stack. API and web images now build from `infrastructure/docker/`; this directory reserves future profile splits without pretending deferred services exist.

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

The current default stack exposes the implemented web shell on `127.0.0.1:3000` and the API health endpoints on `127.0.0.1:8000`. The proxy, worker, and AI profile remain placeholders and validate topology/process behavior only.
