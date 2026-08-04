<p align="center">
  <img src="docs/assets/nexus-banner.svg" alt="NexusOS — a private AI operating system for Raspberry Pi 5" width="100%">
</p>

<p align="center">
  <strong>A local-first personal AI operating system for the Raspberry Pi 5.</strong><br>
  Private by default. Modular by design. Built for your own hardware.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/onion3130/NexusOS?style=flat-square&label=license" alt="MIT License"></a>
  <a href="https://github.com/onion3130/NexusOS/releases"><img src="https://img.shields.io/badge/release-v1.3.2-8b5cf6?style=flat-square" alt="NexusOS v1.3.2 release"></a>
  <img src="https://img.shields.io/badge/Docker-ARM64--ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker ARM64 ready">
  <img src="https://img.shields.io/badge/Raspberry%20Pi%205-supported-c51a4a?style=flat-square&logo=raspberrypi&logoColor=white" alt="Raspberry Pi 5 supported">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11 or newer">
  <img src="https://img.shields.io/badge/Next.js-15-black?style=flat-square&logo=next.js&logoColor=white" alt="Next.js 15">
  <img src="https://img.shields.io/badge/TypeScript-5.9-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript 5.9">
</p>

NexusOS brings an authenticated dashboard, assistant, productivity tools, and read-only system monitoring together in one private, self-hosted application. It is designed for Raspberry Pi deployments with persistent data stored on an external SSD.

## Features

- 🤖 **AI assistant** — bounded provider gateway with optional NVIDIA NIM chat models configured server-side
- ✅ **Task management** — due dates, priorities, categories, tags, recurring schedules, and reminders
- 📝 **Private notes** — versioned source notes with tags, archive, and soft deletion
- ◇ **External sources** — bounded UTF-8 text/Markdown uploads and approved-file imports with background ingestion
- ⌕ **Scoped search** — local source-aware retrieval across notes and ingested sources
- 🔔 **Notifications** — persistent in-app alerts plus optional email and push (ntfy) delivery for reminders
- 📈 **System telemetry** — read-only Raspberry Pi health and resource overview
- 🛡️ **Owner admin status** — redacted system, provider, storage, and migration status without exposing secrets
- 🔐 **Security boundaries** — user-owned data, sessions, CSRF protection, permissions, confirmation workflows, and audit events
- 🛠️ **Safe maintenance** — explicit-confirmation SQLite backups, integrity checks, restore, retention cleanup, and encryption key rotation without arbitrary host control
- 🌓 **Responsive dashboard** — accessible loading/error states and theme switching
- 🐳 **ARM64 deployment** — non-root Docker Compose services for local and Pi use

## Screenshots

<p align="center">
  <img src="docs/assets/nexus-dashboard-overview.png" alt="NexusOS dashboard overview" width="100%">
</p>

<p align="center">
  <img src="docs/assets/nexus-dashboard-system.png" alt="NexusOS Raspberry Pi 5 system overview" width="100%">
</p>

## Project status

| Item | Status |
| --- | --- |
| **Current milestone** | v1.5 — external source ingestion ✅ (unreleased) |
| **Current version** | `1.3.2` — latest released Docker health and migration compatibility fixes |
| **Next milestone** | v1.6 — external synchronization and richer document parsers |

NexusOS v1.5 adds bounded external text/Markdown ingestion, source lifecycle controls, background versioned chunking, source-aware retrieval, and Assistant provenance while preserving the private, local-first Raspberry Pi architecture. NVIDIA NIM remains optional and disabled by default. See the [roadmap](docs/ROADMAP.md) for scope and follow-up work.

## Technology stack

- **Frontend:** Next.js 15, React 19, TypeScript 5.9
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

Open `http://localhost:3000`. AI is disabled by default. For local development without Docker, read the [setup guide](docs/SETUP.md).

## Documentation

Use the [documentation index](docs/README.md) to find the right guide:

- [Setup](docs/SETUP.md) · [Deployment](docs/DEPLOYMENT.md) · [Development](docs/DEVELOPMENT.md)
- [Environment](docs/ENVIRONMENT.md) · [Security](docs/SECURITY.md) · [API](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md) · [Database](docs/DATABASE.md) · [AI system](docs/AI_SYSTEM.md)
- [Roadmap](docs/ROADMAP.md) · [Changelog](CHANGELOG.md)

## Community

- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)
- [MIT License](LICENSE)

## License

NexusOS is released under the [MIT License](LICENSE).
