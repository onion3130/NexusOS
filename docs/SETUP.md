# NexusOS development setup

**Status:** Milestone 1 implemented — API health foundation and web shell are available; authentication, persistence, and feature modules remain deferred.

## Prerequisites

- Git
- Python 3.11+ locally; the API image uses Python 3.12+
- Node.js 20+ and npm for local web development
- Docker Engine and Docker Compose v2 for the full ARM64 stack
- Raspberry Pi deployments additionally require Raspberry Pi OS Lite 64-bit and an external SSD

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

The API itself reads process environment variables only. Docker Compose supplies `.env`; local API runs should export the variables or use a shell environment loader. The API fails startup with a value-free configuration error when required variables are missing or invalid.

## Run the API locally

Install the API package and test extras from `apps/api`:

```sh
cd apps/api
python -m venv .venv
. .venv/bin/activate                 # macOS/Linux
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[test]'
cd ../..
python -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

In another shell, check:

```sh
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
```

The readiness endpoint checks the configured `DATA_DIR` boundary, including a temporary write/delete probe as the API user. On Linux/Pi bind mounts, ensure the host data directories are writable by the API container UID 10001. Database checks are deferred to Milestone 2.

## Run the web shell locally

```sh
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`. The shell is intentionally static in Milestone 1 and does not authenticate or call feature APIs.

## Run the full development stack

From the repository root, after `.env` is configured:

```sh
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
```

Open `http://localhost:3000` for the shell and `http://localhost:8000/api/v1/health/live` for the API liveness check. Stop the stack with:

```sh
docker compose --env-file .env down
```

The API and web services build from ARM64-compatible Dockerfiles and run as non-root users. The proxy, worker, and AI services remain deferred placeholders.

## Validation before a change is committed

```sh
python -m py_compile apps/api/app/main.py apps/api/app/core/config.py apps/api/app/api/routes/health.py
cd apps/api && pytest
cd ../web && npm run typecheck && npm run build
cd ../.. && git diff --check
```

Docker-enabled environments should also run `docker compose --env-file .env config --quiet` and an ARM64 image build. Never commit `.env`, databases, runtime data, logs, backups, model files, credentials, private keys, or personal data.
