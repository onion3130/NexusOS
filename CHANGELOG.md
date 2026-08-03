# Changelog

All notable NexusOS changes are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases will use semantic versioning once implementation begins.

## [Unreleased]

### Planned

- Add identity, persistence, and secure session boundaries as Milestone 2.
- Add the first dashboard data module after the foundation is stable.

## [0.1.0] — 2026-08-02

### Added

- Public-repository security baseline with `.gitignore`, `.env.example`, and environment validation.
- ARM64-aware Docker Compose foundation with real API and web services plus deferred placeholders.
- FastAPI liveness/readiness endpoints with environment-only startup validation.
- Responsive Next.js Milestone 1 shell with local-first status presentation.
- Backend health tests and frontend TypeScript/build configuration.
- Complete Phase 1 architecture and API contracts covering system boundaries, frontend, backend, database, AI tools, Raspberry Pi operations, Docker, plugins, security, and milestones.
- Initial setup, environment, deployment, and security documentation structure.
- Architecture decision record placeholders for the modular monolith, SQLite-first persistence, and provider-neutral AI gateway.

### Security

- Local secrets, databases, runtime data, logs, build artifacts, and editor settings are excluded from Git.
- API configuration rejects missing, placeholder, or short JWT secrets and insecure production cookies.
- API and web containers use reviewed ARM64 bases and non-root runtime users.
- Development ports bind to loopback; no public listener is introduced by Milestone 1.

[Unreleased]: https://github.com/onion3130/NexusOS/compare/main...HEAD
[0.1.0]: https://github.com/onion3130/NexusOS/releases/tag/v0.1.0
