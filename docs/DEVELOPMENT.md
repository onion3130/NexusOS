# NexusOS development guide

**Status:** Milestone 1 foundation implemented; this guide describes the current workflow and the rules for future milestones.
**Last updated:** 2026-08-02

A new coding agent should read this document, [`README.md`](../README.md), and [`ARCHITECTURE.md`](ARCHITECTURE.md) before changing code. The repository is the source of project context; previous chat history is not required.

## Current scope

Implemented:

- FastAPI API package under `apps/api`.
- Environment-only validated configuration.
- `GET /api/v1/health/live` and `GET /api/v1/health/ready`.
- Responsive static Next.js shell under `apps/web`.
- ARM64-aware non-root API/web Dockerfiles and Compose development stack.
- Backend tests, frontend typecheck/build configuration, and public-repository security baseline.

Deferred:

- Authentication, database models/migrations, dashboard data, AI calls/tools, jobs, system adapters, backups, reverse-proxy TLS, and feature modules.

Do not add deferred feature code without a written plan and owner approval for that milestone.

## Repository map

```text
apps/api/                  FastAPI package and pytest suite
apps/web/                  Next.js app and npm scripts
infrastructure/docker/     API and web image definitions
docker-compose.yml         Current development services
scripts/validate_env.py    Safe environment template validator
docs/                      Architecture, contracts, operations, and ADRs
data/                      Local runtime mount; ignored and not committed
```

## Local setup

From the repository root:

```sh
cp .env.example .env
# Replace the JWT placeholder with a locally generated secret of at least 32 characters.
python scripts/validate_env.py --env-file .env
```

On Windows, use `copy .env.example .env` in Command Prompt or `Copy-Item .env.example .env` in PowerShell. Keep `AI_PROVIDER=disabled` for the foundation.

The API reads process environment variables only. For a local API process, export the variables from `.env` using a shell/tool appropriate to the operating system; do not add dotenv loading to application code unless the configuration decision is explicitly changed. Docker Compose reads `.env` and passes the required values to the API.

## Run and test the API

```sh
cd apps/api
python -m venv .venv
. .venv/bin/activate                 # macOS/Linux
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[test]'
python -m pytest
python -m py_compile app/main.py app/core/config.py app/api/routes/health.py
cd ../..
python -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

The API requires all required environment variables. Startup errors name invalid setting names without printing values. Health checks:

```sh
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
```

## Run and build the web shell

```sh
cd apps/web
npm install
npm run typecheck
npm run build
npm run dev
```

The current shell is intentionally static and does not call the API or hold credentials.

## Compose validation

With `.env` configured:

```sh
cd ../..
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
docker compose --env-file .env down
```

The development ports bind to `127.0.0.1`. Do not expose them publicly. Validate ARM64 builds on the Pi or in CI before calling a deployment compatible with the target hardware.

## Change workflow

For every approved feature or milestone:

1. Read the relevant architecture, API, database, AI, security, and deployment docs.
2. Explain the implementation plan and exact files before coding.
3. Confirm the scope does not silently implement a later milestone.
4. Add/update tests with the behavior.
5. Update the relevant docs in the same change.
6. Run backend tests/compilation, frontend typecheck/build, Compose validation, and security checks appropriate to the change.
7. Review the complete diff and staged file list; check `git diff --check`.
8. Commit with a concise descriptive message.
9. Push completed major milestones to `origin/main` without force-pushing.
10. Record the shipped behavior, decisions, validation, and remaining work in `CHANGELOG.md`.

Never commit `.env`, credentials, tokens, private keys, databases, runtime data, logs, backups, model files, or personal data. If a secret is exposed, rotate it immediately and inspect Git history.

## Documentation ownership

- `README.md`: orientation, current status, quick start, and repository map.
- `CHANGELOG.md`: shipped milestone summary, security notes, and remaining planned work.
- `docs/ARCHITECTURE.md`: system boundaries, design decisions, and milestone plan.
- `docs/API.md`: endpoint/resource contract; mark implemented versus planned behavior.
- `docs/DATABASE.md`: persistence design, schema ownership, and migration rules.
- `docs/AI_SYSTEM.md`: provider, tool, memory, and safety boundaries.
- `docs/DEPLOYMENT.md`: Pi/Compose operations, recovery, and production gates.
- `docs/DEVELOPMENT.md`: this workflow and commands.

Update documentation when behavior changes. Avoid wording that makes a design-only endpoint or feature appear implemented.

## Definition of done

A change is complete only when its code, tests, docs, error states, security implications, and operational behavior are reviewed. A milestone is not complete because it compiles: it must have a usable slice, clear rollback/limitations, and a clean pushed commit.
