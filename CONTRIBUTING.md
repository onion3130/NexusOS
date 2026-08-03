# Contributing to NexusOS

Thank you for your interest in NexusOS. Contributions are welcome, especially improvements that preserve its local-first, private-by-default design and Raspberry Pi compatibility.

## Before you start

- Read the [development guide](docs/DEVELOPMENT.md), [architecture](docs/ARCHITECTURE.md), and [security baseline](docs/SECURITY.md).
- Check the [roadmap](docs/ROADMAP.md) before proposing work that belongs to a future milestone.
- For a new feature, open an issue or discussion first so scope and design can be agreed before implementation.

## Development workflow

1. Fork the repository and create a focused branch.
2. Make the smallest modular change that solves the problem.
3. Add or update tests and documentation where behavior changes.
4. Run the relevant backend tests, frontend typecheck/build, and `git diff --check`.
5. Open a pull request with a clear summary, validation results, security considerations, and any Raspberry Pi or deployment impact.

## Project standards

- Keep authentication, authorization, ownership, CSRF, audit, and input validation at the API boundary.
- Do not add secrets, personal data, arbitrary host actions, or unbounded model-controlled operations.
- Keep Docker images non-root and ARM64-compatible where applicable.
- Prefer explicit migrations and backward-compatible API changes.
- Follow the existing formatting, naming, and module boundaries.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). For security vulnerabilities, use the process in [SECURITY.md](SECURITY.md) rather than opening a public issue.
