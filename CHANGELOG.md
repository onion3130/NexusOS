# Changelog

All notable NexusOS changes are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases will use semantic versioning once implementation begins.

## [Unreleased]

### Planned

- Replace the no-op Compose services with the approved ARM64 application foundation after owner approval.
- Add the first executable FastAPI health endpoints and Next.js shell as Milestone 1.

## [0.1.0] — 2026-08-02

### Added

- Public-repository security baseline with `.gitignore`, `.env.example`, and environment validation.
- ARM64-aware Docker Compose placeholder topology for local development planning.
- Complete Phase 1 architecture and API contracts covering system boundaries, frontend, backend, database, AI tools, Raspberry Pi operations, Docker, plugins, security, and milestones.
- Initial setup, environment, deployment, and security documentation structure.
- Architecture decision record placeholders for the modular monolith, SQLite-first persistence, and provider-neutral AI gateway.

### Security

- Local secrets, databases, runtime data, logs, build artifacts, and editor settings are excluded from Git.
- Production configuration requires a non-placeholder JWT secret and secure session cookies.
- Placeholder containers run as a non-root user with read-only filesystems and private networking.

[Unreleased]: https://github.com/onion3130/NexusOS/compare/main...HEAD
[0.1.0]: https://github.com/onion3130/NexusOS/releases/tag/v0.1.0
