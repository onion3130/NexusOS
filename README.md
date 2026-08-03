# NexusOS

NexusOS is a local-first personal AI operating system intended to run on a Raspberry Pi 5 with an external SSD. The long-term product will unify an assistant, productivity, files, development tools, finance, media, and home-server operations in one private dashboard.

## Current milestone

**Milestone 5 — assistant gateway implemented.**

The repository currently contains:

- A FastAPI API with environment-backed startup validation.
- Implemented liveness, storage/database-readiness, and identity endpoints.
- SQLite persistence with an explicit Alembic migration.
- Argon2id password hashing, tracked sessions, JWT access tokens, CSRF protection, and login backoff.
- A responsive Next.js dashboard shell with modular navigation, theme switching, command palette, accessible states, and a login/authentication boundary.
- Authenticated read-only Raspberry Pi telemetry for CPU, memory, storage, temperature, uptime, and network status.
- Authenticated assistant conversations with bounded provider-neutral gateway calls and the read-only `system.get_overview` tool.
- ARM64-aware, non-root API and web Dockerfiles.
- A Docker Compose development topology with loopback-only ports.
- Public-repository protections, environment templates, tests, and operational documentation.

Tasks, notes, backups, service actions, streaming jobs, RAG, memory, and other product modules are not implemented yet. AI calls are available only through the server-configured Milestone 5 gateway; `AI_PROVIDER=disabled` remains the safe default. The authoritative next-step plan is [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Milestone 5 implementation status — 2026-08-02

Milestone 5 is implemented within its approved scope. The API persists user-owned conversations and messages, routes bounded requests through a server-selected provider gateway, records normalized model/tool metadata, and exposes only the read-only `system.get_overview` tool. Provider credentials remain server-side and AI is disabled by default.

Implemented assistant boundary:

- `POST/GET /api/v1/conversations`
- `GET /api/v1/conversations/{id}`
- `POST /api/v1/conversations/{id}/messages`
- Reversible Alembic migration `0002_assistant`
- Responsive authenticated assistant workspace with disabled-provider and retry states

## Milestone 4 implementation status — 2026-08-02

Milestone 4 is implemented within its approved read-only scope. The API collects bounded Linux telemetry through fixed procfs/sysfs/filesystem adapters, requires authentication, degrades safely when sources are unavailable, and deliberately does not expose service/container control or Docker socket access.

Implemented system boundary:

- `GET /api/v1/system/overview`
- Read-only CPU, memory, storage, temperature, uptime, and network adapters
- Dashboard polling with loading, stale, unavailable, and degraded states
- Explicit unavailable service/container status boundary

## Milestone 3 implementation status — 2026-08-02

Milestone 3 is implemented within its approved scope. The authenticated shell now has modular components, responsive navigation, persisted light/dark appearance, keyboard command search, loading/error/empty/locked states, and accessible focus behavior. No domain feature data or host actions were added.

Implemented frontend boundaries:

- Modular auth/session client in `apps/web/lib/auth.ts`
- Theme context and toggle in `apps/web/components/theme-provider.tsx` and `theme-toggle.tsx`
- Authenticated shell in `apps/web/components/dashboard-shell.tsx`
- Keyboard command palette in `apps/web/components/command-palette.tsx`
- Reusable auth/state/status components under `apps/web/components/`


Milestone 2 identity and persistence is implemented within its approved scope. Database migrations are explicit and must be run through the owner-bootstrap command or Alembic; application startup never mutates the schema.

Implemented identity routes:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/sessions`
- `DELETE /api/v1/auth/sessions/{id}`

Authentication uses Argon2id password hashes, short-lived HS256 access JWTs, hashed/rotated refresh tokens, HttpOnly cookies, a readable CSRF cookie plus required header, generic invalid-login responses, and bounded in-process login backoff.

## Project checkpoint — 2026-08-02

Phase 0, Milestone 1 foundation, Milestone 2 identity/persistence, Milestone 3 shell/design-system, Milestone 4 read-only telemetry, and approved Milestone 5 assistant gateway work are implemented. No later product feature was started during this milestone.

### What has been built

- Public GitHub foundation: `.gitignore`, placeholder-only `.env.example`, license, changelog, and security guidance.
- FastAPI runtime in `apps/api` with process-environment configuration validation.
- `GET /api/v1/health/live` and storage/database `GET /api/v1/health/ready`.
- Identity and session routes under `/api/v1/auth`.
- SQLAlchemy identity/assistant models and Alembic migrations `0001_identity` and `0002_assistant`.
- Backend migration, identity, health, security, gateway, tool, and assistant API tests.
- Next.js 15/React 19 shell in `apps/web`, including standalone output and login/session boundary.
- Non-root ARM64-targeted API/web Dockerfiles and loopback-only Compose development services.
- Self-contained architecture, API, database, AI, deployment, development, setup, environment, security, and roadmap documentation.

### Current structure and important files

```text
apps/api/app/                 FastAPI entrypoint, settings, health/auth routes, identity module
apps/api/migrations/           Explicit Alembic identity migrations
apps/api/tests/               Health, migration, identity, and security tests
apps/web/app/                 Next.js workspace composition and global styles
infrastructure/docker/        API and web images
infrastructure/healthchecks/  Health contract and current endpoint notes
infrastructure/compose/       Future Compose profile guidance
scripts/validate_env.py       Safe dotenv-style validation helper
docker-compose.yml            Current API/web plus placeholder service topology
docs/                         Handoff, contracts, architecture, and roadmap
```

### Working now

The API starts when required environment variables are valid, explicit migrations create the identity schema, liveness works without storage, readiness detects missing/unwritable storage or unmigrated databases, login/session flows work, the web production build succeeds, and the frontend/backend checks pass. Docker is configured for `linux/arm64`, non-root runtime users, private networking, restart policies, and loopback host bindings.

### Incomplete

There is no background job worker, streaming endpoint, RAG/semantic memory, task/note domain API, host action, reverse-proxy TLS, systemd service, encrypted backup, or public/LAN access mode. Provider calls are bounded and available only when explicitly enabled in server configuration. The current identity/database implementation is intentionally limited to the first owner/session schema. These are roadmap work, not hidden implementation.

### Checkpoint findings and technical debt

- No hardcoded production secrets, arbitrary shell execution, privileged containers, or Docker socket mounts were found in the current implementation.
- Next.js standalone output is configured and matches the web runner image.
- Raspberry Pi 5 ARM64 compatibility is verified for the API/web image builds, Compose configuration, non-root web container, and web runtime smoke test; sustained-load and healthcheck timing remain open.
- Inline Python/Node healthchecks use short timeouts; validate or tune them on a loaded Pi before production deployment.
- The development stack intentionally binds to loopback, so it is not a LAN-accessible Pi deployment yet.
- Docker image reproducibility and production hardening remain future work; use the roadmap rather than treating the current Compose file as production infrastructure.

## Start here for a new coding agent

Read these files before changing code:

1. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — current boundaries and design decisions.
2. [`docs/API.md`](docs/API.md) — implemented health/identity API and clearly marked future contracts.
3. [`docs/DATABASE.md`](docs/DATABASE.md) — current identity schema and persistence boundary.
4. [`docs/AI_SYSTEM.md`](docs/AI_SYSTEM.md) — current disabled AI state and future safety boundary.
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

The API reads process environment variables only. Missing or invalid required settings produce a safe startup error naming variable names without printing values. The template database URL targets the Docker mount at `/var/lib/nexus/data`; for a host-only Uvicorn run, override it with `DATABASE_URL=sqlite:///./data/nexus.db` while keeping `DATA_DIR=./data`.

## Run locally

### API

```sh
cd apps/api
python -m venv .venv
. .venv/bin/activate                 # macOS/Linux
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[test]'
# Host-only development uses a repository-relative SQLite file:
# export DATABASE_URL=sqlite:///./data/nexus.db
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

Open `http://localhost:3000`. The web shell authenticates against the identity API, refreshes tracked sessions, and provides the Milestone 5 assistant workspace. Tasks, notes, and other domain feature APIs remain deferred.

### Health API

```sh
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
```

`/live` checks only that the process responds. `/ready` checks storage plus whether the configured identity migration has been applied. It never mutates the schema; run the explicit owner-bootstrap/Alembic command first.

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
├── apps/web/                  Next.js authenticated dashboard shell
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

The next planned milestone is tasks and reminders. Later work includes notes/search, safe host actions, files/projects, and production deployment hardening. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the ordered plan.
