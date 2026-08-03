# Changelog

All notable NexusOS changes are recorded here. The repository is currently pre-release; version `0.1.0` describes the foundation and not a production-ready operating system.

## [Unreleased]

### Milestone 3 — 2026-08-02

- Replaced the monolithic dashboard page with modular auth, shell, theme, command palette, and status components.
- Added responsive navigation, mobile menu behavior, skip-link support, locked future modules, and accessible loading/error/empty states.
- Added persisted light/dark appearance controls and a fixed-command keyboard palette with Cmd/Ctrl+K, arrow navigation, Enter, Escape, focus trapping, and restoration.
- Kept all domain feature APIs and host actions out of scope; the shell exposes only implemented identity behavior and fixed UI actions.
- Validated the standalone frontend build and documented Raspberry Pi 5 ARM64 verification as part of the milestone gate.

### Milestone 2 — 2026-08-02

- Implemented the SQLite/SQLAlchemy persistence boundary and reversible Alembic identity migration.
- Added owner bootstrap, Argon2id password hashing, short-lived access JWTs, rotated hashed refresh sessions, CSRF protection, audit events, and bounded login backoff.
- Added health readiness checks for storage and migration/database state.
- Added login, refresh, logout, current-user, session-list, and session-revocation APIs with tests.
- Added the authenticated Next.js shell boundary and session refresh behavior.
- Recorded remaining technical debt: ARM64/on-device validation, healthcheck timing validation on a loaded Pi, and production deployment hardening.

### Documentation

- Updated the project handoff to identify Milestone 2 and Milestone 3 as implemented and distinguish live identity/database/shell behavior from deferred product modules.
- Refreshed the project handoff so a new coding agent can continue without previous conversation history.
- Added `docs/ROADMAP.md` as the source of truth for milestone order and acceptance criteria.
- Reconciled README, architecture, database, API, AI, deployment, setup, and development documentation with the actual Milestone 3 implementation.
- Marked planned resources and designs explicitly so they are not mistaken for live features.

### Planned

- Milestone 4: read-only Raspberry Pi system telemetry.

## [0.1.0] — 2026-08-02

### Added

- Environment-only FastAPI configuration with safe validation errors.
- `GET /api/v1/health/live` process liveness endpoint.
- `GET /api/v1/health/ready` storage readiness endpoint with a write/delete probe.
- Responsive Next.js 15 web shell with login, session refresh, modular shell controls, and deferred capabilities.
- ARM64-aware Docker Compose development stack with non-root API/web containers.
- Loopback-only development ports and healthchecks.
- Backend health, migration, identity, and security tests; frontend typecheck/build configuration; and public GitHub safety baseline.
- Architecture, API, database, AI, deployment, development, setup, environment, and security documentation.

### Security

- `.env`, `.env.*`, databases, runtime data, logs, build output, dependencies, and editor settings are ignored.
- Placeholder or short JWT secrets are rejected; production requires secure cookies.
- Provider credentials are represented only by placeholders in `.env.example` and are not used while `AI_PROVIDER=disabled`.
- No AI provider connection, host action, public listener, or LAN exposure is introduced by Milestone 2; development ports remain loopback-only.

[Unreleased]: https://github.com/onion3130/NexusOS/compare/main...HEAD
[0.1.0]: https://github.com/onion3130/NexusOS/releases/tag/v0.1.0
