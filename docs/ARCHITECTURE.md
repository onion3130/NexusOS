# NexusOS architecture

**Current milestone:** Milestone 5 — assistant gateway implemented
**Status:** Current runtime is a FastAPI health/identity/system/assistant service plus an authenticated modular Next.js shell. Tasks, memory, RAG, and host-action modules remain design-only.
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

- `apps/api`: FastAPI application with environment-backed settings, identity, read-only system telemetry, and assistant gateway.
- `apps/api/app/api/routes/health.py`, `auth.py`, `system.py`, and `assistant.py`: health, identity, system, and assistant route modules.
- `apps/api/app/modules/assistant`: owned conversation service, provider gateway, and typed read-only tool registry.
- `apps/api/app/db`: SQLAlchemy engine, models, and request-scoped sessions.
- `apps/api/app/modules/system`: fixed-source telemetry adapters and safe aggregation service.
- `apps/api/migrations`: explicit Alembic migration history.
- `apps/web`: Next.js 15 shell with login/current-user/logout boundary, modular navigation, theme context, command palette, and accessible state components.
- `infrastructure/docker/api.Dockerfile`: non-root API image.
- `infrastructure/docker/web.Dockerfile`: non-root Next.js image.
- `docker-compose.yml`: ARM64 development topology with real API/web services and placeholder proxy/worker/AI services.
- `scripts/validate_env.py`: safe validation of the public environment contract.

### Implemented boundary

```text
Browser -> authenticated Next.js shell -> same-origin `/api/v1` rewrite -> FastAPI

Health client -> FastAPI
                 ├── /api/v1/health/live
                 ├── /api/v1/health/ready -> DATA_DIR/database probe
                 ├── /api/v1/system/overview -> fixed procfs/sysfs/storage reads
                 └── /api/v1/conversations -> owned messages -> bounded ModelGateway -> read-only tool registry

Docker Compose -> private bridge network
                 ├── nexus-api  (real)
                 ├── nexus-web  (real)
                 ├── nexus-proxy (placeholder)
                 ├── nexus-worker (placeholder)
                 └── nexus-ai (opt-in placeholder profile)
```

Compose publishes only `127.0.0.1:3000` and `127.0.0.1:8000` in the development stack. The API opens the configured SQLite database only after explicit migration, authenticates users, manages sessions, and handles bounded assistant requests. Provider calls are server-configured and optional; the API does not execute host actions.

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

Development ports bind to loopback. A future reverse proxy may provide LAN HTTPS, but public exposure, remote access, and TLS are not part of the current development milestone.

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

- Domain-specific database tables, repositories, and feature persistence beyond identity.
- Authenticated dashboard data modules beyond the current shell/design system.
- Streaming/jobs, memory, RAG, provider health dashboards, and additional assistant tools.
- Tasks, notes, calendar, files, projects, Git, Docker inventory, finance, and media integrations.
- Pi write actions and service/container control; read-only telemetry is implemented.
- Production reverse proxy, systemd service, encrypted backups, restore drills, limits, and monitoring.
- Plugin loading and package verification.

See [`ROADMAP.md`](ROADMAP.md) for the approved sequence and [`DEVELOPMENT.md`](DEVELOPMENT.md) for implementation rules.

## 8. Checkpoint review — 2026-08-02

The architecture still matches the Nexus requirements at the current stage: local-first operation, privacy by default, modular-monolith evolution, ARM64 targeting, optional AI, explicit host-action boundaries, and incremental delivery. The current implementation is deliberately much smaller than the target architecture.

### Verified

- API and web are separate runtime services on a private Compose network.
- Host ports are loopback-only in the development stack.
- API/web images use non-root users; placeholder services use read-only filesystems and temporary filesystems where appropriate.
- The API accepts configuration through environment variables, connects only to the configured SQLite database after explicit migrations, and contacts an AI provider only when a server-side provider is explicitly enabled.
- The web image's `output: "standalone"` setting matches its runner-stage copy.
- No arbitrary subprocess, shell execution, Docker socket mount, or privileged container was found in the current implementation.

### Milestone 4 system boundary

System telemetry is authenticated and read-only. Adapters may read fixed procfs/sysfs paths and the configured data volume, but never accept arbitrary paths, execute subprocesses, access the Docker socket, or mutate services. A missing source produces a bounded unavailable reason and does not fail the entire overview.

### Milestone 3 design boundary

The dashboard shell is presentation and session orchestration only. It does not own domain data, permissions, host actions, or feature API calls. Navigation items for future modules are disabled/locked rather than fake links. Theme preference is a browser-local UI preference, not a server setting. The command palette exposes only fixed shell actions and never accepts arbitrary commands.

### Open technical debt

- ARM64 API/web image builds, Compose configuration, and a web runtime smoke test have passed on the available Raspberry Pi 5; sustained-load and healthcheck timing tests remain open.
- Healthcheck interpreter startup and timeout behavior should be measured on a loaded Pi before production use.
- Current Compose is a development topology: no reverse proxy, TLS, LAN access, resource limits, systemd startup, backups, or monitoring.
- Docker image dependency reproducibility and image digest pinning remain hardening work.

These are documented risks and future gates, not reasons to start a later feature early.
