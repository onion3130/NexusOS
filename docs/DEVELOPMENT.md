# NexusOS development

**Current milestone:** Milestone 5 assistant gateway
**Status:** SQLite identity/assistant persistence, session authentication, modular responsive frontend shell, authenticated read-only Pi telemetry, and the bounded assistant gateway are implemented; tasks, notes, memory, RAG, and host actions remain deferred.
**Last updated:** 2026-08-02

A new AI coding agent should read this file, [`README.md`](../README.md), and [`ROADMAP.md`](ROADMAP.md) before changing code. The repository is the project context.

## Project checkpoint — 2026-08-02

The checkpoint reviewed the current implementation without starting a later feature. Phase 0, Milestone 1, Milestone 2 identity/persistence, Milestone 3 shell/design-system, Milestone 4 telemetry, and Milestone 5 assistant-gateway scope are complete.
 The working tree was validated for API behavior, frontend build health, environment safety, Docker boundaries, Raspberry Pi compatibility assumptions, and architecture drift.

### Files created/modified across the foundation

- API: `apps/api/pyproject.toml`, `app/main.py`, `app/core/config.py`, `app/api/routes/health.py`, and `tests/test_health.py`.
- Web: `apps/web/package.json`, Next config, TypeScript config, layout, page, styles, and public placeholder.
- Infrastructure: `docker-compose.yml`, API/web Dockerfiles, Compose/healthcheck/systemd guidance.
- Project contract: `.gitignore`, `.env.example`, `README.md`, `CHANGELOG.md`, and the `docs/` handoff set.

### Review result

No confirmed application bug was found in the current scope. The authenticated Next.js shell uses standalone output as required by its Docker runner. The API has no shell execution, AI call, host action, privileged container, or Docker socket access; its SQLite identity database is accessed only after explicit migration. The API/web `linux/arm64` images, Compose configuration, non-root web container, and web runtime smoke test have been verified on the available Raspberry Pi 5. Remaining risks are sustained-load/healthcheck timing behavior and production deployment hardening.

Docker validation has been run on the available Raspberry Pi 5 for the current API/web images and web smoke test. Do not call the stack production-ready until sustained-load checks, backups, TLS, authentication, persistence, and recovery controls exist.

## Implemented files

- `apps/api/app/main.py`: FastAPI application, CORS setup, and startup settings validation.
- `apps/api/app/core/config.py`: process-environment settings and safe validation errors.
- `apps/api/app/api/routes/health.py`: liveness and storage/database readiness routes.
- `apps/api/app/api/routes/system.py` and `app/modules/system/`: authenticated read-only telemetry boundary and adapters.
- `apps/api/app/api/routes/assistant.py` and `app/modules/assistant/`: authenticated conversations, provider gateway, and read-only tool registry.
- `apps/api/migrations/versions/0002_assistant.py`: assistant persistence migration.
- `apps/api/app/api/routes/auth.py`: login, refresh, logout, current-user, and session routes.
- `apps/api/app/db/` and `apps/api/migrations/`: identity persistence and migration history.
- `apps/api/tests/`: health, migration, identity, CSRF, and security tests.
- `apps/web/app/page.tsx`: authenticated workspace composition.
- `apps/web/components/`: auth screens, dashboard shell, theme provider/toggle, command palette, and reusable status states.
- `apps/web/lib/auth.ts`: browser session API boundary.
- `apps/web/lib/system.ts` and `components/system-overview.tsx`: authenticated telemetry client and presentation.
- `infrastructure/docker/*.Dockerfile`: non-root API/web images.
- `docker-compose.yml`: current ARM64 development topology.

## Deferred files and modules

There is currently no domain feature persistence beyond identity and assistant conversations, no `app/domain`, `app/workers`, task/note API, memory/RAG subsystem, streaming endpoint, or host-action module. The read-only system telemetry and assistant modules are implemented under `app/modules/system` and `app/modules/assistant`; create additional feature modules only as part of an approved milestone.

## Environment setup

From the repository root:

```sh
cp .env.example .env
python scripts/validate_env.py --env-file .env
```

Validation does not export variables into the calling shell. On macOS/Linux, export them before starting a local API process:

```sh
set -a
. ./.env
set +a
```

On Windows, use `copy .env.example .env` or `Copy-Item .env.example .env`, then set the variables in the current PowerShell session or use Docker Compose. Replace `JWT_SECRET` with a local random value of at least 32 characters. Keep `AI_PROVIDER=disabled`.

The API reads process variables only. Docker Compose supplies `.env`; local processes need the variables exported by the shell or another explicitly chosen environment loader. Do not silently add dotenv loading to application code. Run the explicit owner-bootstrap command before expecting database readiness.

## Backend commands

```sh
cd apps/api
python -m venv .venv
. .venv/bin/activate                 # macOS/Linux
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[test]'
python -m pytest
python -m py_compile $(find app migrations tests -name '*.py' -print)
# Run explicit migrations/owner bootstrap once, interactively:
python -m app.cli.bootstrap_owner --username owner
cd ../..
python -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

## Frontend commands

```sh
cd apps/web
npm install
npm run typecheck
npm run build
npm run dev
```

The current web shell calls the identity, system, and assistant APIs through the same-origin Next.js rewrite, presents login when unauthenticated, refreshes access sessions, sends CSRF-protected logout, and polls read-only telemetry every 30 seconds. It supports theme persistence, responsive navigation, command shortcuts, conversation loading, bounded message submission, disabled-provider/error states, and locked future modules. It does not call task, note, memory, or host-action APIs.

## Compose commands

```sh
cd ../..
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
docker compose --env-file .env down
```

The development ports are loopback-only. Validate ARM64 builds on the Pi or in CI before using an image in deployment.

## Change workflow

For every feature or milestone:

1. Read the relevant architecture, API, database, AI, deployment, and security docs.
2. Explain the plan and exact files before coding.
3. Implement only the approved scope.
4. Add tests for behavior and failure states.
5. Update documentation in the same change.
6. Run backend tests/compilation, frontend typecheck/build, Compose validation, and security checks relevant to the change.
7. Review `git diff`, run `git diff --check`, and inspect the staged file list.
8. Commit with a concise descriptive message.
9. Push completed major milestones to `origin/main` without force-pushing.

Never commit `.env`, credentials, tokens, private keys, databases, runtime data, logs, backups, model files, or personal data. If a secret is exposed, rotate it and inspect Git history.

## Definition of done

A milestone is complete only when its code, tests, documentation, security implications, failure states, deployment behavior, and remaining limitations have been reviewed. Design text alone does not make an API, database, AI provider, or feature implemented.
