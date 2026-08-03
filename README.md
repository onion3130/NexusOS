# NexusOS

NexusOS is a local-first personal AI operating system intended to run on a Raspberry Pi 5 with an external SSD. The long-term product will unify an assistant, productivity, files, development tools, finance, media, and home-server operations in one private dashboard.

## Current milestone

**Milestone 1 — foundation implemented.**

The repository currently contains:

- A FastAPI API with environment-backed startup validation.
- Implemented liveness and storage-readiness endpoints.
- A responsive static Next.js dashboard shell.
- ARM64-aware, non-root API and web Dockerfiles.
- A Docker Compose development topology with loopback-only ports.
- Public-repository protections, environment templates, tests, and operational documentation.

Authentication, database persistence, AI calls, tool calling, tasks, notes, system telemetry, backups, and other product modules are not implemented yet. The authoritative next-step plan is [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Start here for a new coding agent

Read these files before changing code:

1. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — current boundaries and design decisions.
2. [`docs/API.md`](docs/API.md) — implemented health API and clearly marked future contracts.
3. [`docs/DATABASE.md`](docs/DATABASE.md) — current zero-database state and persistence blueprint.
4. [`docs/AI_SYSTEM.md`](docs/AI_SYSTEM.md) — current disabled state and future AI safety boundary.
5. [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — local commands and change workflow.
6. [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — current Compose deployment and limitations.
7. [`docs/ROADMAP.md`](docs/ROADMAP.md) — milestone order and acceptance criteria.

The repository is the project context. Previous conversations are not required.

## Technology

- **Frontend:** Next.js 15, React 19, TypeScript
- **Backend:** FastAPI, Python 3.11+ locally and Python 3.12 in the API image
- **Persistence plan:** SQLAlchemy 2.x + Alembic, SQLite first, PostgreSQL compatibility later
- **Deployment:** Docker Compose, ARM64 target, Raspberry Pi OS Lite 64-bit
- **AI plan:** provider-neutral gateway for NVIDIA NIM, OpenAI-compatible APIs, and optional local endpoints

## Secure local configuration

Copy the public template and replace only local values:

```sh
cp .env.example .env
python scripts/validate_env.py --env-file .env       # Windows-compatible Python command
python3 scripts/validate_env.py --env-file .env     # macOS/Linux alternative
```

Validation does not export values into the current shell. For a local API process on macOS/Linux, export the file before starting Uvicorn:

```sh
set -a
. ./.env
set +a
```

On PowerShell, set the variables in the current session or use Docker Compose, which is the recommended local path. Use a randomly generated `JWT_SECRET` of at least 32 characters. Keep `AI_PROVIDER=disabled` while AI is not intentionally configured. `.env`, databases, runtime data, logs, build output, credentials, and personal data are ignored and must never be committed.

The API reads process environment variables only. Missing or invalid required settings produce a safe startup error naming variable names without printing values.

## Run locally

### API

```sh
cd apps/api
python -m venv .venv
. .venv/bin/activate                 # macOS/Linux
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[test]'
cd ../..
python -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

### Web shell

In a second terminal:

```sh
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`. The web shell is static in Milestone 1 and does not authenticate or call feature APIs.

### Health API

```sh
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
```

`/live` checks only that the process responds. `/ready` checks that `DATA_DIR` exists, disk usage can be read, and the API user can create/delete a temporary file. Database checks are deferred.

## Run with Docker Compose

After `.env` is configured:

```sh
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
docker compose --env-file .env down
```

The API is available at `http://127.0.0.1:8000` and the web shell at `http://127.0.0.1:3000`. Ports bind to loopback only. Do not expose this development stack publicly.

## Repository map

```text
nexusos/
├── apps/api/                  FastAPI package, settings, routes, tests
├── apps/web/                  Next.js static shell
├── infrastructure/docker/     API and web images
├── infrastructure/            Deployment contracts and future profiles
├── scripts/validate_env.py    Safe environment template validator
├── docker-compose.yml         Current ARM64 development topology
├── docs/                      Project handoff and design documentation
├── .env.example               Placeholder-only configuration contract
└── data/                      Ignored local runtime mount
```

## Development rules

1. Work in small approved milestones; do not generate the whole application at once.
2. Before coding, explain the plan and exact files affected.
3. Keep implementation, tests, documentation, and operational behavior aligned.
4. Treat design-only APIs and schemas as unimplemented until code and tests exist.
5. Never allow AI output or user input to become arbitrary host commands.
6. Run relevant tests and builds before committing.
7. Commit completed milestones with a descriptive message and push them to Git.
8. Never commit secrets, tokens, private keys, databases, model files, logs, or personal data.

## Remaining work

The next approved milestone is identity and persistence. Later work includes the authenticated dashboard, system read-only telemetry, AI gateway, tasks, notes/search, safe host actions, files/projects, and production deployment hardening. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the ordered plan.
