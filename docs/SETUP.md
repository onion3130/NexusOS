# NexusOS development setup

**Status:** v1.5 external source ingestion and lifecycle (unreleased) — API health, identity/assistant persistence, session authentication, authenticated web shell, read-only Pi telemetry, bounded assistant gateway, tasks, reminders, notifications, notes/search, source-aware retrieval, optional embeddings, grounded assistant responses with note provenance, calendar, finance, media, confirmation-gated host maintenance, verified SQLite backups, encrypted directory replication, confirmation-gated restore, retention cleanup, encryption key rotation, outbound email/push notification channels, audited out-of-process plugins, and audit history are available. External source uploads/imports are available for UTF-8 text and Markdown; approved-file synchronization is available with an opt-in 15-minute-to-24-hour polling interval. PDF/OCR, crawling, and autonomous memory remain deferred.

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

Replace `JWT_SECRET` with a random value of at least 32 characters. Keep `AI_PROVIDER=disabled` until a provider is intentionally configured. To use hosted NVIDIA NIM, set `AI_PROVIDER=nvidia_nim`, `AI_MODEL` to an NVIDIA-supported chat model, and `NVIDIA_API_KEY`; the hosted chat and embeddings endpoints are defaulted automatically unless you set explicit reviewed public-compatible `AI_BASE_URL` or `EMBEDDING_BASE_URL` values. Configure `TASK_WORKER_INTERVAL_SECONDS` and `TASK_WORKER_BATCH_SIZE` only within their documented bounds. Leave `PLUGINS_DIR` empty unless you are deliberately installing trusted operator-approved plugins.

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

For optional encrypted replication, generate a 256-bit key with `openssl rand -hex 32`, set `BACKUP_REPLICATION_DESTINATION` to an absolute operator-mounted destination, and configure both values together. Never commit the key.

For optional outbound notification channels, set `NOTIFICATION_EMAIL_ENABLED=true` with an SMTP relay host, sender, and recipient (and paired user/password when the relay requires authentication), and/or `NOTIFICATION_PUSH_ENABLED=true` with an absolute ntfy-compatible URL and topic. Secrets stay server-side; the Notifications workspace shows redacted status and offers a test-send button. `python scripts/validate_env.py --env-file .env` reports incomplete channel configuration.

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

Open `http://localhost:3000` (or the Pi's LAN address), sign in as the owner, and open **Admin** in the sidebar. Follow the step-by-step NVIDIA NIM form: paste an NVIDIA API Catalog key, choose a recommended chat model, optionally enable embeddings, use **Test connection**, then **Save**. The key is sent only to the authenticated API, encrypted beneath the data volume, and never returned or stored in SQLite. The API activates immediately and the worker reloads automatically — no SSH or container restart is required for normal NIM setup. Environment configuration (`AI_PROVIDER=nvidia_nim`, `AI_MODEL`, `NVIDIA_API_KEY`) remains available for advanced operators. In Sources, import an approved workspace text/Markdown file, then choose **Enable sync** on its source card to keep it current. Synchronization is worker-side and can be triggered with **Sync now**; it never accepts a browser path. In Assistant, enable **Use my notes** and choose lexical, semantic, or hybrid retrieval; retrieved-source links open the owned note in the Notes workspace. Assistant task writes require a configured provider and explicit confirmation; note search/read and grounded retrieval are read-only, and grounding is skipped when AI is disabled.

## Full Compose stack

```sh
docker compose --env-file .env config --quiet
docker compose --env-file .env run --rm nexus-api python -m alembic upgrade head
docker compose --env-file .env run --rm nexus-api python -m app.cli.bootstrap_owner --username owner
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
```

The API, web, and worker use ARM64-compatible non-root images and the worker shares the SSD-backed SQLite mount. Ports bind to loopback only. Read-only Files, Projects, and Git views scan `WORKSPACE_ROOTS`; Docker views are disabled by default and remain unavailable unless an operator supplies a separately reviewed socket boundary. Plugins are disabled in the default Compose stack. To explicitly enable them, use the documented plugin overlay with a dedicated host directory. Stop with `docker compose --env-file .env down`.

## Validation

```sh
cd apps/api && python -m pytest
cd ../web && npm run typecheck && npm run build
cd ../.. && git diff --check
```

Docker-enabled environments should also validate the default and hardened Compose profiles, ARM64 image builds, Caddy internal-CA trust, systemd boot behavior, encrypted replication to the mounted destination, and a restore drill. Run a due-reminder smoke test and restart the worker to verify notification deduplication.
