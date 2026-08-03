# NexusOS

NexusOS is a local-first personal AI operating system for a Raspberry Pi 5. It is designed to bring an AI assistant, home-server monitoring, personal productivity, projects, files, and integrations into one cohesive dashboard.

## Current status

**Milestone 1 implemented — API/web foundation complete; authentication, persistence, and feature modules are deferred.**

The system is being built incrementally. Each milestone should produce a usable, tested slice of the product and should take roughly 2–6 hours.

## Architecture

The complete architecture and milestone plan are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The current API contract is in [`docs/API.md`](docs/API.md). Persistence and AI designs are in [`docs/DATABASE.md`](docs/DATABASE.md) and [`docs/AI_SYSTEM.md`](docs/AI_SYSTEM.md). Setup, development, environment, deployment, and security guidance are in [`docs/SETUP.md`](docs/SETUP.md), [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md), [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md), [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md), and [`docs/SECURITY.md`](docs/SECURITY.md). These documents are the project handoff for future coding agents; previous conversations are not required.

It covers:

- System boundaries and runtime topology
- Repository and module structure
- SQLite-first database design with PostgreSQL migration support
- Versioned FastAPI API design
- Docker Compose and ARM64 deployment strategy
- AI provider routing and tool-calling boundaries
- Authentication, authorization, and security controls
- Testing, observability, backups, and Raspberry Pi operations
- Incremental implementation milestones
- Architecture decision records under [`docs/adr/`](docs/adr/)

## Development rules

1. Do not generate the entire application at once.
2. Before each feature, explain the implementation plan and files affected.
3. Implement only the approved feature or milestone.
4. Keep components and modules independently testable.
5. Document important functions, APIs, migrations, and operational behavior.
6. Run validation before committing.
7. Commit and push after every major milestone or approved feature.
8. Never commit secrets, tokens, private keys, databases, model files, or personal data.

## Planned stack

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS, shadcn/ui
- **Backend:** FastAPI, Python 3.12+
- **Persistence:** SQLAlchemy + Alembic, SQLite initially, PostgreSQL-compatible schema
- **Authentication:** JWT in secure HttpOnly cookies, Argon2id password hashing, roles
- **Deployment:** Docker Compose on Raspberry Pi OS Lite 64-bit / ARM64
- **AI:** Provider-neutral gateway for NVIDIA NIM, OpenAI-compatible APIs, and local models

## Secure local configuration

The repository is safe to publish publicly: `.env` files, databases, runtime data, logs, build output, and editor settings are ignored. `.env.example` contains placeholders only and is the committed configuration contract.

From the repository root:

```sh
cp .env.example .env
# Generate a secret locally, then put it in JWT_SECRET inside .env.
python scripts/validate_env.py --env-file .env       # Windows
python3 scripts/validate_env.py --env-file .env     # macOS/Linux
```

`NEXUS_ENV=production` requires a non-placeholder `JWT_SECRET` of at least 32 characters and `SESSION_COOKIE_SECURE=true`. Keep `AI_PROVIDER=disabled` until a provider credential is intentionally configured. The API reports missing or unsafe settings without printing secret values.

## Milestone 1 development

Install and run the API locally:

```sh
cd apps/api
python -m venv .venv
. .venv/bin/activate                 # macOS/Linux
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[test]'
cd ../..
python -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

In another shell, run the web shell:

```sh
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`. API checks are available at `http://127.0.0.1:8000/api/v1/health/live` and `/api/v1/health/ready`.

Or run the ARM64-aware Docker development stack:

```sh
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build -d
```

The web shell is on `http://127.0.0.1:3000`; the API is on `http://127.0.0.1:8000`. Both ports bind to loopback only. Stop with `docker compose --env-file .env down`.

Milestone 1 does not implement authentication, database persistence, AI calls, tool calling, tasks, notes, calendar, files, finance, media, plugins, reverse-proxy TLS, backups, or Raspberry Pi write actions.

## Repository foundation

```text
nexusos/
├── .env / .env.example       # local secrets / public template
├── apps/
│   ├── api/                  # FastAPI health foundation and tests
│   └── web/                  # Next.js static shell
├── infrastructure/
│   └── docker/               # non-root API/web images
├── scripts/validate_env.py   # safe configuration validation
├── docker-compose.yml        # ARM64 development stack
├── docs/                     # architecture, contracts, setup, security
└── ...
```

Never commit `.env`, databases, runtime data, logs, backups, model files, credentials, private keys, or personal data.

## Approval boundary

Milestone 1 is complete within its approved scope. The next implementation milestone requires a new plan and approval before coding authentication or persistence.
