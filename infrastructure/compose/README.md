# Compose profile guidance

The root `docker-compose.yml` is the current source of truth for the Milestone 6 development stack.

## Current services

- `nexus-api`: FastAPI API, loopback port 8000.
- `nexus-web`: Next.js shell, loopback port 3000.
- `nexus-worker`: dedicated ARM64 reminder worker, no published port, shared SQLite SSD mount.
- `nexus-proxy`: deferred placeholder.
- `nexus-ai`: opt-in deferred placeholder.

## Planned profiles

| Profile | Purpose | Introduced |
|---|---|---|
| default | Local ARM64 foundation, API, web, and task worker | Milestone 6 |
| `dev` | Hot-reload API/web development | Future |
| `pi` | Raspberry Pi deployment with SSD mounts and recovery policies | Deployment milestone |
| `postgres` | PostgreSQL compatibility validation | Persistence milestone |
| `ai` | Explicit external/local model boundary | Assistant milestone |

Each future profile must document image provenance, ARM64 support, healthchecks, resource limits, volumes, networks, secrets, and rollback behavior.

## Validation

```sh
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
docker compose --env-file .env down
```

The current environment may not have Docker installed. Validate on a Docker-enabled host or the target Raspberry Pi before deployment.
