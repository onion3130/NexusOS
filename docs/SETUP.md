# NexusOS development setup

**Status:** Phase 0 foundation — no application runtime yet.

## Prerequisites

- Git
- Docker Engine and Docker Compose v2 for the scaffold
- Python 3.11+ for `scripts/validate_env.py` (Python 3.12+ is planned for the FastAPI runtime)
- Node.js/npm are not required until the Next.js milestone
- Raspberry Pi deployments additionally require Raspberry Pi OS Lite 64-bit, Docker, and an external SSD

## Local configuration

From the repository root:

```sh
cp .env.example .env
```

On Windows, use `copy .env.example .env` in Command Prompt or `Copy-Item .env.example .env` in PowerShell. Replace `JWT_SECRET` with a locally generated value of at least 32 characters. Keep `AI_PROVIDER=disabled` until a provider credential is intentionally configured.

Validate without printing secret values:

```sh
python scripts/validate_env.py --env-file .env       # Windows
python3 scripts/validate_env.py --env-file .env     # macOS/Linux
```

For production-like configuration, set `NEXUS_ENV=production`, use a non-placeholder secret, and set `SESSION_COOKIE_SECURE=true`. Provider credentials are required only when their provider is enabled.

## Current scaffold

When Docker is installed:

```sh
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
docker compose --env-file .env ps
docker compose --env-file .env down
```

The current services are no-op ARM64 placeholders. They validate private networking, restart policies, healthchecks, non-root execution, read-only filesystems, and external data mounts. They do not provide a web interface or API endpoint.

## Validation before a change is committed

```sh
git diff --check
python -m py_compile scripts/validate_env.py
git status --short
```

Once application packages exist, CI must add frontend typechecking/builds, backend tests, API contract tests, migration tests, Compose validation, ARM64 image builds, and secret scanning.

## Public-repository rules

Never commit `.env`, databases, runtime data, logs, backups, model files, credentials, private keys, or personal data. Use a private local `.env`, a deployment secret manager, or Docker secrets. Review `docs/SECURITY.md` before adding an integration.
