# NexusOS development setup

**Status:** Milestone 7 implemented — API health, identity/assistant persistence, session authentication, authenticated web shell, read-only Pi telemetry, bounded assistant gateway, tasks, reminders, notifications, user-owned notes, SQLite FTS5 search, and source-aware retrieval chunks are available. Embeddings and autonomous memory remain deferred.

## Prerequisites

- Git
- Python 3.11+ locally; API/worker image uses Python 3.12+
- Node.js 20+ and npm
- Docker Engine and Docker Compose v2 for the full ARM64 stack
- Raspberry Pi deployments additionally require Raspberry Pi OS Lite 64-bit and an external SSD

## Local configuration

```sh
cp .env.example .env
python scripts/validate_env.py --env-file .env
```

Replace `JWT_SECRET` with a random value of at least 32 characters. Keep `AI_PROVIDER=disabled` until a provider is intentionally configured. Configure `TASK_WORKER_INTERVAL_SECONDS` and `TASK_WORKER_BATCH_SIZE` only within their documented bounds.

## Run the API and worker locally

```sh
cd apps/api
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m alembic upgrade head
python -m app.cli.bootstrap_owner --username owner
python -m uvicorn app.main:app --reload --port 8000
```

Run the worker in another terminal:

```sh
cd apps/api
. .venv/Scripts/activate  # Windows; use . .venv/bin/activate on POSIX
python -m app.worker
```

## Run the web shell

```sh
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`, sign in, and select Notes or Search. The notification center is available in the authenticated top bar. Assistant task writes require a configured provider and explicit confirmation; note search/read tools are read-only and the assistant remains safely unavailable when AI is disabled.

## Full Compose stack

```sh
docker compose --env-file .env config --quiet
docker compose --env-file .env run --rm nexus-api python -m alembic upgrade head
docker compose --env-file .env run --rm nexus-api python -m app.cli.bootstrap_owner --username owner
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
```

The API, web, and worker use ARM64-compatible non-root images and the worker shares the SSD-backed SQLite mount. Ports bind to loopback only. Stop with `docker compose --env-file .env down`.

## Validation

```sh
cd apps/api && python -m pytest
cd ../web && npm run typecheck && npm run build
cd ../.. && git diff --check
```

Docker-enabled environments should also validate Compose and ARM64 image builds. Run a due-reminder smoke test and restart the worker to verify notification deduplication.
