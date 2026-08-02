# NexusOS

NexusOS is a local-first personal AI operating system for a Raspberry Pi 5. It is designed to bring an AI assistant, home-server monitoring, personal productivity, projects, files, and integrations into one cohesive dashboard.

## Current status

**Phase: architecture approved for review — no application code generated yet.**

The system is being built incrementally. Each milestone should produce a usable, tested slice of the product and should take roughly 2–6 hours.

## Architecture

The complete architecture and milestone plan are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The implementation-independent API contracts are in [`docs/API.md`](docs/API.md).

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

## First implementation milestone

After architecture approval, Milestone 1 will create the minimal ARM64 development and deployment foundation: repository conventions, configuration contracts, Docker Compose scaffolding, health endpoints, and validation scripts. It will not implement the dashboard or AI assistant yet.
