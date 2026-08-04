# Compose profile guidance

The root `docker-compose.yml` is the current source of truth for the v1.0 ARM64 development stack.

## Current services

- `nexus-api`: FastAPI API, loopback port 8000.
- `nexus-web`: Next.js shell, loopback port 3000.
- `nexus-worker`: dedicated ARM64 reminder and confirmed maintenance worker, no published port, shared SQLite SSD mount.
- `nexus-proxy`: placeholder in the default profile; Caddy TLS proxy in the opt-in `hardened` overlay.
- `nexus-ai`: opt-in deferred placeholder.

## Profiles

The default file remains loopback-only development. The hardened Raspberry Pi overlay adds Caddy on ports 80/443 using the official image's non-root `caddy` user with a read-only root filesystem and only `NET_BIND_SERVICE`, removes direct API/web host ports, enables production cookies, and applies bounded resource limits. `BACKUP_REPLICATION_HOST_PATH` and `NEXUS_HOST` are required:

```sh
docker compose --env-file .env -f docker-compose.yml -f infrastructure/compose/hardened.yml --profile hardened up -d
```

Set `NEXUS_HOST` to a private LAN hostname and install Caddy's internal CA root certificate on trusted clients. The overlay is opt-in and does not grant the proxy access to the API or worker host volumes.


| Profile | Purpose | Introduced |
|---|---|---|
| default | Local ARM64 API, web, reminder/maintenance worker, and safe backup boundary | v1.0 |
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
