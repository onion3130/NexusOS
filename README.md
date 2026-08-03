# NexusOS

A local-first personal AI operating system for the Raspberry Pi 5.

NexusOS brings an authenticated dashboard, assistant, productivity tools, and read-only system monitoring together in one private, self-hosted application. It is designed for Raspberry Pi deployments with persistent data stored on an external SSD.

## Features

- 🤖 Provider-neutral AI assistant with server-side credentials
- ✅ Tasks with due dates, priorities, categories, tags, recurring schedules, and reminders
- 🔔 Persistent in-app notifications with a dedicated reminder worker
- 📈 Read-only Raspberry Pi system telemetry
- 🔐 User-owned data, session authentication, CSRF protection, permissions, and audit events
- 🌓 Responsive Next.js dashboard with accessible loading and error states
- 🐳 ARM64-aware Docker Compose deployment for local and Raspberry Pi use

## Screenshots

A product screenshot will be added here as the dashboard evolves.

## Technology stack

- **Frontend:** Next.js, React, TypeScript
- **Backend:** FastAPI, Python 3.11+, SQLAlchemy
- **Database:** SQLite with Alembic migrations
- **Deployment:** Docker Compose, Linux ARM64, Raspberry Pi OS
- **AI:** Optional server-configured OpenAI-compatible or NVIDIA NIM provider

## Quick start

```sh
git clone https://github.com/onion3130/NexusOS.git
cd NexusOS
cp .env.example .env
# Replace JWT_SECRET in .env with a random value of at least 32 characters.
python scripts/validate_env.py --env-file .env
docker compose --env-file .env run --rm nexus-api python -m alembic upgrade head
docker compose --env-file .env run --rm nexus-api python -m app.cli.bootstrap_owner --username owner
docker compose --env-file .env up --build -d
```

Open `http://localhost:3000`. AI is disabled by default; see the setup guide before enabling a provider. For local development without Docker, use the detailed setup instructions.

## Documentation

- [Setup](docs/SETUP.md) — local development and first-run instructions
- [Deployment](docs/DEPLOYMENT.md) — Docker, Raspberry Pi, and operational deployment
- [Development](docs/DEVELOPMENT.md) — project workflow and validation commands
- [Environment](docs/ENVIRONMENT.md) — configuration variables and security rules
- [Security](docs/SECURITY.md) — application boundaries and deployment hardening
- [API reference](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Database](docs/DATABASE.md)
- [AI system](docs/AI_SYSTEM.md)
- [Roadmap](docs/ROADMAP.md)
- [Changelog](CHANGELOG.md)

## Roadmap

Milestone 6, tasks and reminders, is complete. The next milestone focuses on notes and scoped search, followed by safe host actions, files/projects/Git/Docker views, deployment hardening, and carefully isolated integrations.

See the [full roadmap](docs/ROADMAP.md) for current status, scope, and known limitations.

## License

NexusOS is released under the [MIT License](LICENSE).
