# Changelog

All notable NexusOS changes are recorded here. The repository is currently pre-release; version `0.1.0` describes the foundation and not a production-ready operating system.

## [Unreleased]

### Checkpoint — 2026-08-02

- Confirmed Phase 0 and Milestone 1 are complete within scope; no new product feature was started.
- Reviewed API, frontend, Docker, Compose, environment, security, Raspberry Pi/ARM64, and architecture alignment.
- Confirmed the current runtime is limited to the FastAPI health service and static Next.js shell.
- Recorded remaining technical debt: ARM64/on-device validation, healthcheck timing validation on a loaded Pi, and production deployment hardening.

### Documentation

- Refreshed the project handoff so a new coding agent can continue without previous conversation history.
- Added `docs/ROADMAP.md` as the source of truth for milestone order and acceptance criteria.
- Reconciled README, architecture, database, API, AI, deployment, and development documentation with the actual Milestone 1 implementation.
- Marked planned resources and designs explicitly so they are not mistaken for live features.

### Planned

- Milestone 2: identity, SQLite persistence, reversible migrations, owner bootstrap, and secure sessions.
- Milestone 3: authenticated dashboard shell and design-system completion.

## [0.1.0] — 2026-08-02

### Added

- Environment-only FastAPI configuration with safe validation errors.
- `GET /api/v1/health/live` process liveness endpoint.
- `GET /api/v1/health/ready` storage readiness endpoint with a write/delete probe.
- Responsive Next.js 15 web shell showing foundation status and deferred capabilities.
- ARM64-aware Docker Compose development stack with non-root API/web containers.
- Loopback-only development ports and healthchecks.
- Backend health tests, frontend typecheck/build configuration, and public GitHub safety baseline.
- Architecture, API, database, AI, deployment, development, setup, environment, and security documentation.

### Security

- `.env`, `.env.*`, databases, runtime data, logs, build output, dependencies, and editor settings are ignored.
- Placeholder or short JWT secrets are rejected; production requires secure cookies.
- Provider credentials are represented only by placeholders in `.env.example` and are not used while `AI_PROVIDER=disabled`.
- No public listener, authentication flow, database, AI provider connection, or host action is introduced by Milestone 1.

[Unreleased]: https://github.com/onion3130/NexusOS/compare/main...HEAD
[0.1.0]: https://github.com/onion3130/NexusOS/releases/tag/v0.1.0
