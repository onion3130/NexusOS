# NexusOS

NexusOS is a local-first personal AI operating system for a Raspberry Pi 5. It is designed to bring an AI assistant, home-server monitoring, personal productivity, projects, files, and integrations into one cohesive dashboard.

## Current status

**Phase 1 architecture complete — implementation awaits owner approval; no application code generated yet.**

The system is being built incrementally. Each milestone should produce a usable, tested slice of the product and should take roughly 2–6 hours.

## Architecture

The complete architecture and milestone plan are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The implementation-independent API contracts are in [`docs/API.md`](docs/API.md). Setup, environment, deployment, and security guidance are in [`docs/SETUP.md`](docs/SETUP.md), [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md), [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md), and [`docs/SECURITY.md`](docs/SECURITY.md).

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

Set up local configuration without putting secrets in Git:

```sh
cp .env.example .env
# Generate a secret locally, for example:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# Put the generated value in JWT_SECRET inside .env.
# Windows
python scripts/validate_env.py --env-file .env
# macOS/Linux
python3 scripts/validate_env.py --env-file .env
docker compose --env-file .env config
docker compose --env-file .env up -d
```

`NEXUS_ENV=production` requires a non-placeholder `JWT_SECRET` of at least 32 characters and `SESSION_COOKIE_SECURE=true`. Select an AI provider only after setting its corresponding local credential (`NVIDIA_API_KEY`, `OPENAI_API_KEY`, or `AI_API_KEY`). The validator reports missing or unsafe variable names without printing secret values.

The current repository has no FastAPI or Next.js runtime yet. `scripts/validate_env.py` is therefore the dependency-free executable configuration contract for this scaffold; the first application milestone must reuse the same environment names and fail startup with equivalent safe errors.

The repository foundation is:

```text
nexusos/
├── .env                 # local only; never commit
├── .env.example         # safe template; commit this
├── .gitignore           # protects secrets and runtime data
├── docker-compose.yml   # ARM64 placeholder topology
├── scripts/
│   └── validate_env.py  # safe configuration validation
├── README.md
├── docs/
└── ...
```

`docker compose --env-file .env up -d` currently starts the ARM64 no-op foundation containers (`nexus-proxy`, `nexus-api`, `nexus-web`, and `nexus-worker`). They validate the private network, restart policy, healthcheck, and external data mounts. They are placeholders only: no web UI or API endpoint is available until the application implementation milestone replaces them with real images. The optional `nexus-ai` placeholder requires `docker compose --env-file .env --profile ai-scaffold up`. Stop the scaffold with `docker compose --env-file .env down`.

There is no automated test suite, application build, or real web/API startup available yet; those will be added with the first implementation milestone.

On the Raspberry Pi, set `DATA_DIR` in `.env` to a directory on the external SSD before starting the stack. Do not commit `.env`, `data/`, database files, logs, backups, or model files.

## Approval boundary

Phase 0 and Phase 1 are complete as documentation and infrastructure design. No feature code has been generated. After owner approval, the next requested milestone will replace the placeholders with the minimal ARM64 development and deployment foundation: repository conventions, configuration contracts, Docker Compose scaffolding, health endpoints, and validation scripts. It will not implement the dashboard or AI assistant yet.
