# NexusOS architecture

**Current milestone:** Milestone 1 — foundation implemented
**Status:** Current runtime is a FastAPI health service plus a static Next.js shell. Database, authentication, AI, and product modules are design-only.
**Last updated:** 2026-08-02

This is the architectural source of truth for a new coding agent. A design described here is not implemented unless the current-state sections and tests say so.

## 1. Mission and principles

NexusOS is a local-first personal AI operating system for a Raspberry Pi 5 with an external SSD. It should remain private, modular, maintainable, responsive, accessible, ARM64-compatible, and useful even when every optional AI provider is disabled.

Core principles:

- Start as a modular monolith instead of premature microservices.
- Keep the browser, API, persistence, provider, and host-action boundaries separate.
- Deliver small tested milestones rather than speculative feature breadth.
- Treat model output, plugin code, and host input as untrusted.
- Make destructive operations explicit, typed, permissioned, confirmed, and audited.
- Keep runtime data on the SSD and never treat the SSD as the only backup.

## 2. What exists now

### Runtime components

- `apps/api`: FastAPI application with environment-backed settings and a startup lifespan check.
- `apps/api/app/api/routes/health.py`: the only route module currently registered.
- `apps/web`: Next.js 15 static dashboard shell; it does not call the API yet.
- `infrastructure/docker/api.Dockerfile`: non-root API image.
- `infrastructure/docker/web.Dockerfile`: non-root Next.js image.
- `docker-compose.yml`: ARM64 development topology with real API/web services and placeholder proxy/worker/AI services.
- `scripts/validate_env.py`: safe validation of the public environment contract.

### Implemented boundary

```text
Browser -> static Next.js shell

Health client -> FastAPI
                 ├── /api/v1/health/live
                 └── /api/v1/health/ready -> DATA_DIR probe

Docker Compose -> private bridge network
                 ├── nexus-api  (real)
                 ├── nexus-web  (real)
                 ├── nexus-proxy (placeholder)
                 ├── nexus-worker (placeholder)
                 └── nexus-ai (opt-in placeholder profile)
```

Compose publishes only `127.0.0.1:3000` and `127.0.0.1:8000` in the development stack. The API does not open `DATABASE_URL`, call an AI provider, authenticate users, or execute host actions.

## 3. Planned target architecture

Once later milestones are approved, the system becomes a layered modular monolith:

```text
Web console
    -> versioned FastAPI routes
        -> authentication/authorization
            -> domain services and bounded modules
                -> repositories and migrations
                    -> SQLite on Pi / PostgreSQL validation

Assistant service -> authorized context -> ModelGateway -> typed ToolRegistry
                                                          -> domain/host adapters
```

The web console will render and coordinate UI state. The API will remain the authorization and orchestration boundary. Domain modules will own their services, schemas, repositories, migrations, and tests. Long-running AI, backup, scan, and sync work will run as jobs instead of blocking requests.

## 4. Repository structure

```text
nexusos/
├── apps/
│   ├── api/                    FastAPI package and tests
│   └── web/                    Next.js application
├── infrastructure/
│   ├── docker/                 Current API/web Dockerfiles
│   ├── compose/                Future profile documentation
│   ├── healthchecks/           Health contract
│   └── systemd/                Future Pi startup design
├── scripts/                    Environment and future operations scripts
├── docs/                       Handoff, contracts, ADRs, and roadmap
├── docker-compose.yml          Current development topology
└── data/                       Ignored runtime mount
```

Future backend modules belong under clear boundaries such as `identity`, `system`, `assistant`, `tasks`, `notes`, `files`, `projects`, `git`, `docker`, `finance`, `media`, and `plugins`. No such feature module should be created without an approved milestone plan.

## 5. Important decisions

### Modular monolith first

One API process keeps deployment and debugging simple on a Raspberry Pi. Narrow internal interfaces preserve the option to extract a worker or module later.

### SQLite first, PostgreSQL-compatible design

SQLite minimizes idle resource use and is appropriate for the first Pi deployment. SQLAlchemy and Alembic will provide a migration/repository boundary, while PostgreSQL compatibility must be tested rather than assumed.

### Provider-neutral AI gateway

NVIDIA NIM and OpenAI-compatible services are external provider options. A Pi 5 is not assumed to have an NVIDIA GPU, so local inference is optional. Provider selection is server policy, never a user-controlled arbitrary URL.

### Private by default

Development ports bind to loopback. A future reverse proxy may provide LAN HTTPS, but public exposure, remote access, and TLS are not part of Milestone 1.

### Typed and auditable actions

AI and UI requests may select only server-defined tools/actions. No arbitrary shell command, Docker argument, filesystem path, or SQL is accepted from model output or the browser.

## 6. Security boundaries

- The browser never receives provider keys, JWT signing secrets, database credentials, Docker socket access, or unrestricted host paths.
- The API remains authoritative for identity, ownership, permissions, and confirmation.
- Plugins, when implemented, will run out of process with explicit capabilities and no Docker socket.
- Logs must be bounded and redacted; secrets and raw credentials are never logged.
- Production cookies will be Secure and HttpOnly with CSRF protection for state-changing requests.
- Reboot, shutdown, restart, delete, Git write, and backup actions require explicit policy and audit records.

## 7. Deferred scope

Not implemented today:

- Database engine, ORM, migrations, repositories, and persistence tests.
- User accounts, password hashing, JWT/session cookies, roles, and permissions.
- Authenticated dashboard data access.
- AI provider calls, conversation storage, memory, RAG, tool registry, and streaming.
- Tasks, notes, calendar, files, projects, Git, Docker inventory, finance, and media integrations.
- Pi telemetry adapters and write actions.
- Production reverse proxy, systemd service, encrypted backups, restore drills, limits, and monitoring.
- Plugin loading and package verification.

See [`ROADMAP.md`](ROADMAP.md) for the approved sequence and [`DEVELOPMENT.md`](DEVELOPMENT.md) for implementation rules.
