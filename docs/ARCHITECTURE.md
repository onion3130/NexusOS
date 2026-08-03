# NexusOS Architecture

**Status:** Phase 1 architecture complete; Milestone 1 foundation implemented; Milestone 2 awaits owner approval
**Last updated:** 2026-08-02
**Scope:** Architecture, boundaries, contracts, operations, and milestones. Only the approved Milestone 1 foundation has been implemented.

## 1. Mission and architectural goals

NexusOS is a local-first personal AI operating system for a Raspberry Pi 5 (8 GB) with an external SSD. It provides one cohesive dashboard for assistant conversations, productivity, files, development, finance, and home-server operations.

The architecture is optimized for:

- **Local-first behavior:** core data and core functionality remain available on the local network without a cloud dependency.
- **Privacy:** secrets, personal data, conversation history, and files stay local unless a user explicitly enables an external provider or integration.
- **Modularity:** every domain is a replaceable module with a narrow service boundary.
- **Low maintenance:** containers restart automatically, health is observable, backups are scheduled, and failures degrade safely.
- **ARM64 compatibility:** all images and dependencies must support Raspberry Pi OS Lite 64-bit / ARM64.
- **Progressive delivery:** each milestone delivers a usable, tested slice instead of a speculative full application.
- **Future scale:** SQLite is the initial database, but schemas and repositories remain compatible with PostgreSQL.
- **Safety:** destructive system actions require explicit authorization and confirmation; AI suggestions never silently perform dangerous actions.

## 2. Non-goals for the first release

The first release will not attempt to:

- Replace a full desktop operating system.
- Run a large language model locally on the Pi by default.
- Expose administrative services directly to the public internet.
- Implement every listed feature before the foundation is proven.
- Treat AI output as trusted executable code.
- Store arbitrary user-uploaded files in the database.

The initial product is a secure local dashboard with a reliable API, a small set of useful modules, and an extensible tool gateway.

## 3. System overview

Nexus uses a layered modular monolith first. This avoids premature microservice complexity while keeping clear boundaries so individual modules can later be extracted.

```text
Browser / mobile browser
          |
          | HTTPS on LAN (reverse proxy in production)
          v
+----------------------+       private application network
| Next.js web console  | ------------------------------+
+----------------------+                               |
                                                       v
                                      +--------------------------+
                                      | FastAPI application      |
                                      | API + auth + orchestration|
                                      +--------------------------+
                                        |       |       |
                         private DB ----+       |       +---- host adapters
                                         v      v             (allowlisted)
                              +----------+  +---------+       |
                              | SQLite   |  | AI      |       v
                              | / Postgres|  | gateway |  Raspberry Pi
                              +----------+  +---------+  Docker/system metrics
                                         |      |
                                         |      +-- local provider (optional)
                                         +--------- external provider (optional)

                    external integrations are outbound-only and opt-in
```

### Milestone 1 implemented boundaries

- `apps/api` contains a minimal FastAPI process with environment-only startup validation.
- `/api/v1/health/live` reports process liveness without dependency checks.
- `/api/v1/health/ready` reports the configured storage boundary; database checks are deferred.
- `apps/web` contains a static Next.js shell with no authentication or feature data access.
- API and web Dockerfiles use ARM64-compatible bases and non-root runtime users.
- Compose binds development ports to loopback only and keeps deferred services private.

### Runtime boundaries

| Boundary | Responsibility | Must not do |
|---|---|---|
| Web console | Rendering, navigation, user interaction, local UI state | Hold provider secrets, access the database directly, execute host commands |
| API | Authentication, authorization, validation, orchestration, domain APIs | Render business-critical data only in an untyped pass-through |
| Domain modules | Domain rules and use cases | Reach into another module's tables or private internals |
| Repositories | Persistence queries and transactions | Contain HTTP, UI, or provider-specific behavior |
| AI gateway | Provider selection, normalized responses, tool-call loop | Bypass authorization or execute arbitrary shell commands |
| Tool registry | Typed, permissioned capabilities exposed to AI and UI | Expose unrestricted host access |
| Host adapters | Narrow system telemetry/actions | Accept arbitrary commands or user-provided shell strings |
| Worker/scheduler | Background jobs, reminders, backups, sync | Block API requests with long-running work |
| Reverse proxy | TLS termination, routing, security headers, static delivery | Become the source of application business logic |

## 4. Repository structure

The repository starts as a monorepo with independently testable frontend and backend packages.

```text
nexusos/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── .env.example
├── .gitignore
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── DATABASE.md
│   ├── AI_SYSTEM.md
│   ├── DEVELOPMENT.md
│   ├── SETUP.md
│   ├── DEPLOYMENT.md
│   ├── SECURITY.md
│   └── adr/
│       ├── 0001-modular-monolith.md
│       ├── 0002-sqlite-first.md
│       └── 0003-local-ai-gateway.md
├── apps/
│   ├── web/                         # Next.js application
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── lib/
│   │   ├── hooks/
│   │   ├── styles/
│   │   └── tests/
│   └── api/                         # FastAPI application
│       ├── app/
│       │   ├── main.py
│       │   ├── api/                 # versioned route adapters
│       │   ├── core/                # settings, security, lifecycle
│       │   ├── db/                  # engine, sessions, migrations
│       │   ├── domain/               # entities, ports, use cases
│       │   ├── modules/              # bounded feature modules
│       │   ├── ai/                   # gateway, memory, tool registry
│       │   ├── workers/              # jobs and scheduler adapters
│       │   └── observability/
│       └── tests/
├── packages/
│   ├── contracts/                   # generated/shared API types
│   ├── design-system/               # shared UI primitives/tokens
│   └── config/                      # lint, format, TypeScript conventions
├── plugins/
│   └── README.md                    # plugin contract, no arbitrary loading yet
├── infrastructure/
│   ├── compose/
│   │   ├── compose.yml
│   │   ├── compose.dev.yml
│   │   └── compose.pi.yml
│   ├── caddy/                       # or another approved reverse proxy
│   ├── docker/                      # Milestone 1 API/web images
│   ├── systemd/
│   └── healthchecks/
├── scripts/
│   ├── backup/
│   ├── restore/
│   ├── smoke/
│   └── pi/
└── data/                            # runtime mount; never committed
    ├── db/
    ├── backups/
    ├── uploads/
    ├── logs/
    └── cache/
```

### Module shape

Each backend module owns its API adapter, use cases, repository ports, persistence mappings, schemas, and tests.

```text
modules/tasks/
├── api.py
├── schemas.py
├── service.py
├── repository.py
├── models.py
└── tests/
```

A module may call another module only through an explicit service interface or event. It may not import another module's SQLAlchemy model or issue direct queries against another module's tables.

## 5. Domain modules and ownership

| Module | Owns | First release? |
|---|---|---:|
| `identity` | Users, sessions, roles, permissions, audit identity | Yes |
| `health` | Liveness/readiness and dependency checks | Yes |
| `system` | Pi metrics, services, logs, safe host actions | Yes, read-only first |
| `assistant` | Conversations, messages, model runs, tool calls | Yes |
| `tasks` | Tasks, homework, reminders, notifications | Yes |
| `notes` | Notes, tags, search metadata | Later foundation |
| `calendar` | Events and external calendar sync boundaries | Later |
| `files` | File metadata, recent files, search index boundary | Later |
| `projects` | Projects, workspaces, coding sessions | Later |
| `git` | Repository metadata and safe Git operations | Later |
| `docker` | Container inventory and allowlisted lifecycle actions | Later |
| `finance` | Watchlists, snapshots, portfolio data | Later |
| `media` | Jellyfin/Nextcloud integration status | Later |
| `plugins` | Signed, versioned extension metadata and permissions | Later |
| `search` | Cross-domain query orchestration | Later |
| `settings` | User and instance preferences | Yes, minimal |

A module is allowed to be read-only initially. Write actions are introduced only after validation, authorization, and audit logging exist.

## 6. Frontend architecture

### Navigation model

The web console is an app shell rather than a collection of unrelated pages:

- Persistent left rail on desktop; compact bottom/overlay navigation on mobile.
- Global command/search palette for keyboard-first navigation.
- Dashboard cards are module views, not separate visual systems.
- A shared notification center, assistant drawer, and system status indicator are available from the shell.
- Route-level loading, empty, error, and permission states are mandatory.

### Frontend layers

1. **App shell:** authenticated layout, navigation, command palette, theme, responsive breakpoints.
2. **Design system:** buttons, dialogs, cards, tables, forms, toasts, status indicators, charts.
3. **Feature views:** task board, assistant, system monitor, notes, files, and future modules.
4. **Data access:** typed API client, query cache, mutation helpers, auth/session hooks.
5. **Presentation state:** URL state and local state only; server data remains server-owned.

The frontend never embeds provider keys, directly calls the database, or decides whether a privileged operation is allowed.

### UI standards

- Dark mode is the default visual direction, with a light theme supported.
- Use a restrained neutral palette with one accent family for status and actions.
- Destructive actions use explicit confirmation dialogs and a reason/target summary.
- Keyboard navigation, visible focus, reduced motion, semantic landmarks, and sufficient color contrast are required.
- Motion is purposeful: status transitions, panel depth, and loading feedback; no animation should block use.

## 7. Backend architecture

FastAPI is the HTTP adapter around application services. Route handlers should be thin:

1. Parse and validate a request schema.
2. Resolve the authenticated principal.
3. Call a domain service/use case.
4. Return a response schema or a documented error.

### Backend layers

- `api`: HTTP routes, dependencies, response mapping, OpenAPI tags.
- `core`: settings, logging, security, error handling, lifecycle.
- `domain`: framework-independent entities, ports, commands, policies.
- `modules`: feature-specific application services and adapters.
- `db`: SQLAlchemy engine/session, model mappings, Alembic migrations.
- `ai`: provider gateway, tool registry, memory and retrieval interfaces.
- `workers`: scheduled jobs and asynchronous task execution.
- `observability`: metrics, structured events, health checks, audit events.

Long-running work such as AI generation, backups, scans, and sync jobs must be represented as jobs with status rather than blocking an HTTP request.

## 8. Database design

### Persistence strategy

Use SQLAlchemy 2.x and Alembic from the first schema. SQLite is the default deployment database; PostgreSQL is supported by changing configuration and validating migrations against both engines.

SQLite requirements:

- Store the database on the external SSD runtime mount.
- Enable WAL mode and foreign keys during connection setup.
- Use short transactions and avoid long write locks.
- Do not depend on SQLite-specific SQL in domain services.
- Use UTC timestamps and explicit IDs.

PostgreSQL requirements:

- Use the same repository interfaces and migration history.
- Validate all migrations in CI against a disposable PostgreSQL service before migration support is declared complete.

### Core tables/entities

| Entity | Important fields | Ownership |
|---|---|---|
| `users` | id, username, password_hash, status, created_at | identity |
| `roles` / `permissions` | id, key, description | identity |
| `user_roles` | user_id, role_id | identity |
| `sessions` | id, user_id, token_hash, expires_at, revoked_at | identity |
| `audit_events` | actor, action, target, result, metadata, created_at | identity/observability |
| `conversations` | id, user_id, title, model_policy, created_at | assistant |
| `messages` | id, conversation_id, role, content_ref, created_at | assistant |
| `model_runs` | id, conversation_id, provider, model, latency, status | assistant |
| `tool_calls` | id, run_id, tool_key, arguments, approval, result, status | assistant |
| `memories` | id, user_id, kind, content_ref, source, retention | assistant |
| `tasks` | id, user_id, title, status, due_at, priority | tasks |
| `reminders` | id, task_id, schedule, next_run_at, status | tasks |
| `notifications` | id, user_id, type, payload, read_at | tasks |
| `notes` | id, user_id, title, body_ref, archived_at | notes |
| `jobs` | id, kind, status, progress, error, started_at, finished_at | workers |
| `system_snapshots` | id, cpu, memory, storage, temperature, uptime, captured_at | system |
| `service_status` | id, service_key, state, metadata, checked_at | system |
| `settings` | scope, key, encrypted_value, updated_at | settings |
| `integration_accounts` | provider, encrypted_credentials_ref, enabled | integrations |

Large bodies, uploads, logs, and model artifacts belong in the filesystem/object-style data mount. Database rows store metadata, hashes, ownership, and references.

### Migration policy

- Every schema change is an Alembic revision with upgrade and downgrade paths.
- Migrations are reviewed before applying to a user database.
- Backups run before production migrations.
- A migration test creates a fresh database, upgrades to head, downgrades one revision, and upgrades again.
- Irreversible data transformations require a documented backup/restore plan and explicit approval.

## 9. API design

All application endpoints are versioned under `/api/v1`. Responses use JSON and a consistent error envelope:

```text
{ "error": { "code": "stable_code", "message": "safe message", "request_id": "...", "details": {} } }
```

OpenAPI is generated from FastAPI and published locally at `/docs` only when an authenticated administrator enables developer mode.

### Platform and auth

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/health/live` | Process liveness; no dependency checks |
| GET | `/api/v1/health/ready` | Readiness for database and required dependencies |
| POST | `/api/v1/auth/login` | Authenticate and establish an HttpOnly session cookie |
| POST | `/api/v1/auth/logout` | Revoke the current session |
| GET | `/api/v1/auth/me` | Return current user and permissions |
| GET | `/api/v1/auth/sessions` | List the current user's active sessions |
| DELETE | `/api/v1/auth/sessions/{id}` | Revoke one session |

### Assistant and AI

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/conversations` | List conversations owned by the user |
| POST | `/api/v1/conversations` | Create a conversation |
| GET | `/api/v1/conversations/{id}` | Fetch messages and metadata |
| POST | `/api/v1/conversations/{id}/messages` | Submit a message and create a model-run job |
| GET | `/api/v1/conversations/{id}/stream` | Authenticated SSE stream for an active generation |
| POST | `/api/v1/conversations/{id}/cancel` | Cancel an active generation/job |
| GET | `/api/v1/ai/providers` | Return enabled provider capabilities without secrets |
| GET | `/api/v1/ai/tools` | Return tools available to the current principal |
| POST | `/api/v1/ai/tool-calls/{id}/approve` | Approve a pending sensitive tool call |
| POST | `/api/v1/search` | Search approved notes, tasks, files, and conversations |

### Productivity

| Method | Route | Purpose |
|---|---|---|
| GET/POST | `/api/v1/tasks` | List/create tasks and homework |
| GET/PATCH/DELETE | `/api/v1/tasks/{id}` | Read/update/delete an owned task |
| GET/POST | `/api/v1/reminders` | Manage scheduled reminders |
| GET | `/api/v1/notifications` | List notifications |
| POST | `/api/v1/notifications/{id}/read` | Mark one notification read |
| GET/POST | `/api/v1/notes` | List/create notes |
| GET/PATCH/DELETE | `/api/v1/notes/{id}` | Manage one note |

### System and home server

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/system/overview` | CPU, RAM, storage, temperature, network, uptime |
| GET | `/api/v1/system/snapshots` | Historical telemetry within retention limits |
| GET | `/api/v1/system/services` | Status of allowlisted services and containers |
| GET | `/api/v1/system/logs` | Paginated, permissioned application/system log view |
| POST | `/api/v1/system/actions/{action}` | Request an allowlisted action with confirmation/audit |
| GET | `/api/v1/media/status` | Jellyfin, Nextcloud, and camera integration status |

`system/actions` never accepts a free-form command. The action key maps to a predefined adapter with validated parameters, required permissions, rate limits, and audit logging.

### Files, projects, Git, Docker, and finance

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/files/recent` | Recent file metadata |
| GET | `/api/v1/files/search` | Search indexed, approved paths |
| GET | `/api/v1/projects` | List coding/workspace projects |
| GET | `/api/v1/git/repositories` | List configured repositories |
| POST | `/api/v1/git/repositories/{id}/actions/{action}` | Run an allowlisted Git operation |
| GET | `/api/v1/docker/containers` | List container status |
| POST | `/api/v1/docker/containers/{id}/actions/{action}` | Restart/stop an allowlisted container |
| GET/POST | `/api/v1/finance/watchlists` | Manage watchlists and provider-neutral snapshots |
| POST | `/api/v1/finance/scans` | Start an asynchronous stock scan job |
| GET | `/api/v1/jobs/{id}` | Read status and result metadata for an asynchronous job |
| POST | `/api/v1/jobs/{id}/cancel` | Request cancellation of an owned cancellable job |

Detailed request/response schemas, permissions, status codes, pagination, SSE events, and examples are defined in [`docs/API.md`](API.md). This architecture document defines the resource boundaries; it does not generate implementation code.

### API contract conventions

Every endpoint must document its request schema, response schema, authentication requirement, required permission, status codes, and example errors in OpenAPI and `docs/API.md`.

- List endpoints use cursor pagination with a bounded default and maximum page size.
- Resource identifiers are opaque UUIDs; timestamps are ISO 8601 UTC.
- Mutations return the changed resource or a documented job envelope.
- Retried creates and actions accept an `Idempotency-Key` when the operation can have side effects.
- Long-running work returns `202 Accepted` with a job ID and is polled through a job-status endpoint.
- Streaming assistant responses use an authenticated server-sent events endpoint with reconnect/cancel semantics; the non-streaming JSON endpoint remains canonical.
- `401` means missing/invalid identity, `403` means insufficient permission, `404` does not reveal unauthorized resource existence, `409` means a version/conflict condition, and `422` means schema validation failure.
- Every response carries or can be correlated to a request ID; error messages never expose stack traces, secrets, or provider internals.

## 10. AI gateway and tool architecture

### Provider-neutral gateway

The assistant talks to an internal `ModelGateway` interface. Provider adapters translate between that interface and:

- NVIDIA NIM endpoints.
- OpenAI-compatible hosted endpoints.
- A local model endpoint when one is installed and suitable for the Pi.

Provider configuration is selected by policy, not by user-supplied URLs. The gateway records provider, model, latency, token metadata when available, and failure class without storing secrets in logs.

### Tool lifecycle

```text
user message
  -> intent/context assembly
  -> model response
  -> proposed typed tool call
  -> policy + permission check
  -> approval if sensitive
  -> tool adapter execution
  -> sanitized result
  -> model follow-up
  -> final response + audit event
```

Every tool declares:

- Stable key and version.
- Human-readable description.
- JSON input schema and output schema.
- Required permission.
- Risk level: read, reversible write, destructive.
- Whether confirmation is mandatory.
- Timeout, rate limit, and cancellation behavior.
- Audit fields and redaction rules.

### Initial safe tools

Read-only tools should be implemented before write tools:

- `system.get_overview`
- `system.get_service_status`
- `tasks.list_due`
- `notes.search`
- `files.list_recent`
- `projects.list`
- `docker.list_containers`
- `media.get_status`

Sensitive tools require user confirmation in the UI:

- `system.restart_service`
- `system.restart_docker`
- `system.reboot`
- `system.shutdown`
- `system.backup`
- `docker.restart_container`
- `git.write_operation`
- `files.delete`

No tool may execute arbitrary shell text from an AI response. Host actions use fixed adapters with allowlists and parameter validation.

### Plugin architecture

Plugins are deferred until the core trust boundary is proven. A plugin is a versioned manifest plus an explicitly approved adapter; it is not arbitrary Python or JavaScript loaded into the API process.

A plugin manifest must declare:

- Stable plugin ID, version, API compatibility range, publisher, and integrity hash.
- Requested capabilities and the data domains it can access.
- Routes, UI panels, scheduled jobs, and AI tools it contributes.
- Required configuration keys with secret/non-secret classification.
- Resource limits, health checks, and an uninstall/cleanup plan.

Plugin lifecycle: `discovered -> review_required -> enabled -> disabled -> removed`. Enabling requires an owner action and records the manifest hash and granted permissions in the audit log. Unsigned or hash-mismatched plugins remain disabled. Plugin data is namespaced and removed only through an explicit, documented cleanup operation.

The first plugin implementation should use an out-of-process adapter boundary with a narrow HTTP/JSON contract and a private Docker network. No plugin receives the Docker socket, host filesystem, database credentials, or arbitrary shell access. A future signed package format may be added after the boundary is tested; plugin code must never be treated as trusted merely because it is local.

### Memory and RAG

Memory is separated into explicit categories:

- **Conversation history:** messages and summaries tied to a conversation.
- **User preferences:** explicit settings with user-controlled deletion.
- **Task/notes retrieval:** authoritative domain data queried through domain services.
- **Semantic memory:** optional embeddings/index references with source and retention metadata.

RAG results must include source references and access checks. The model receives only the minimum approved context. Users can inspect and delete stored memories.

## 11. Authentication and authorization

### Authentication

- Passwords are hashed with Argon2id using an established library.
- Login creates a server-tracked session with a cryptographically random token identifier; only a hash of the identifier is stored.
- Access JWTs are short-lived (target: 10–15 minutes) and contain only subject, session ID, issued-at, expiry, and token version.
- A rotating refresh/session cookie is Secure, HttpOnly, and SameSite=Lax by default; Strict is preferred when the deployment flow allows it. Secure cookies require HTTPS in production. Local development may use an explicitly documented insecure-cookie mode bound to loopback only.
- Refresh rotates the session identifier and invalidates the previous identifier. Reuse of a revoked/rotated token revokes the entire session family and emits a high-priority audit event.
- Session revocation is checked server-side for privileged actions. Users can revoke individual sessions and all other sessions.
- Cookie-authenticated mutations require CSRF protection: an origin check plus a separate per-session CSRF token sent in a required header. SameSite is defense-in-depth, not the only CSRF control.
- Login has rate limiting, generic failure responses, and an account lockout/backoff policy that avoids permanent denial of service.
- Password reset/recovery is disabled until an owner-approved local recovery flow is designed; no email provider is assumed.
- Development-only bootstrap credentials are never enabled in production.

### Authorization

Start with one owner account but model roles from day one:

- `owner`: full instance administration.
- `member`: personal modules and non-destructive reads.
- `viewer`: read-only dashboard access.
- `service`: restricted machine-to-machine identity.

Permissions are action-oriented (`system.read`, `system.restart_service`, `notes.write`) and checked in the API and tool registry. The frontend only hides unavailable actions for usability; the backend remains authoritative.

### Security controls

- CSRF protection for cookie-authenticated state-changing requests.
- Strict CORS allowlist; no wildcard production origin.
- Content Security Policy and secure headers at the reverse proxy.
- Secrets supplied by environment files or Docker secrets, never committed.
- Encryption at rest for sensitive integration credentials where practical.
- Audit trail for login, permission changes, tool calls, system actions, and data deletion.
- No public exposure by default; remote access requires an explicitly selected VPN/tunnel design.

## 12. Docker and Raspberry Pi deployment

### Services

Initial Compose topology:

- `nexus-web`: Next.js production server.
- `nexus-api`: FastAPI application.
- `nexus-worker`: background jobs; may share the API image initially.
- `nexus-db`: optional PostgreSQL profile for migration/testing; SQLite remains the default Pi profile.
- `nexus-proxy`: reverse proxy for LAN HTTPS and headers.
- `nexus-ai`: optional local model service only when hardware and memory budgets allow it.

The application should use a private Docker network. Only the reverse proxy publishes a host port in normal deployment. Database and worker ports remain private.

### ARM64 rules

- Pin base image digests or reviewed major versions and verify ARM64 manifests before release.
- Verify Python 3.12 availability for the selected ARM64 base image; if the Pi base does not provide it reliably, build a documented compatible image rather than silently changing the runtime.
- Prefer slim images and multi-stage frontend builds.
- Build/test with `linux/arm64` in CI or on the Pi before a deployment tag.
- Apply CPU/memory limits so AI, indexing, and scans cannot starve the dashboard.
- Use healthchecks and `restart: unless-stopped` for long-running services.
- Persist database, uploads, backups, and logs on the external SSD.
- Keep model downloads out of the Git repository and outside the application image.
- NVIDIA NIM is treated as an external OpenAI-compatible provider, not as a default local inference container: a Raspberry Pi 5 has no NVIDIA GPU. Local inference is an optional provider endpoint with an explicit resource budget and quality expectation.
- The Pi deployment must remain useful with all AI providers disabled; dashboard, auth, tasks, notes, monitoring, and backups cannot depend on model availability.

### Startup and recovery

Docker Compose starts through a systemd unit after network and mounted SSD readiness. Healthchecks distinguish liveness from readiness. A failed dependency should make dependent services report not-ready rather than crash-loop indefinitely.

### Backups

- Daily encrypted database backup to the SSD backup directory.
- Rotating retention: daily, weekly, and monthly copies.
- Periodic restore verification, not just backup creation.
- Optional second destination configured later; never assume the Pi disk is a backup.
- Backup jobs emit a status and notification visible in Nexus.

## 13. Observability and operations

Minimum operational signals:

- Structured JSON application logs with request ID.
- API latency and error counters.
- Database connectivity and migration version.
- Worker queue/job status.
- CPU, memory, storage, temperature, uptime, and network.
- Container health and restart counts.
- Backup age and last restore verification.
- AI provider latency, failure rate, and selected model — never secret values.

The dashboard should show a concise health overview, while detailed logs remain paginated and permissioned. Logs must have retention limits and avoid storing full sensitive prompts by default.

### Operational acceptance criteria

A production milestone is not operationally complete until it demonstrates:

- Services restart automatically after process failure and after reboot, with readiness restored within a documented target (initial target: 120 seconds after dependencies are available).
- Healthchecks distinguish liveness from readiness and report dependency failures without hiding the root cause.
- CPU and memory limits are configured for every container; idle dashboard usage and peak job usage are recorded on the Pi before release.
- Storage alerts fire at defined thresholds (initial targets: warning at 75%, critical at 90%) and include the affected mount.
- Temperature alerts use the Pi's documented throttling range; the system reports cooling/thermal status instead of guessing.
- Backups report age, size, checksum, and result. A restore drill succeeds before a deployment is called production-ready.
- Backup retention, job timeouts, retry counts, and failure notifications are written in the deployment runbook before automation is enabled.
- A failed optional integration does not make the core API or dashboard unavailable.

## 14. Testing strategy

### Backend

- Unit tests for domain services and policy checks.
- Repository tests against SQLite and PostgreSQL where supported.
- API contract tests for auth, permissions, error envelopes, and pagination.
- Tool tests proving invalid parameters and unauthorized calls are rejected.
- Migration upgrade/downgrade tests.

### Frontend

- Component tests for design-system primitives and permission states.
- Page tests for loading, empty, error, and mobile layouts.
- Keyboard and accessibility checks.
- End-to-end smoke tests for login, dashboard loading, assistant message, and confirmation flows.

### Operations

- Compose config validation.
- ARM64 image build validation.
- Healthcheck and restart tests.
- Backup/restore drill.
- Resource-budget checks on the Pi.

A feature is not complete until its tests, documentation, and operational failure state are addressed.

## 15. Milestone plan

Each milestone is intentionally small and should produce something usable. Durations are estimates for one developer with an existing toolchain.

### Milestone 0 — Architecture and decisions (2–3 hours)

**Deliverable:** this document, repository conventions, initial README, approved open decisions.  
**No application code.**

### Milestone 1 — ARM64 foundation (3–5 hours)

**Status:** Implemented.

**Deliverable:** minimal Compose development stack, configuration contract, API liveness/readiness endpoints, web placeholder shell, healthcheck scripts, and local setup documentation.

**Success criteria:** one command starts the stack; API and web health checks pass; no secrets are required for local boot beyond the local signing secret; images build for ARM64.

### Milestone 2 — Identity and persistence (4–6 hours)

**Deliverable:** FastAPI database layer, first reversible migration, owner bootstrap flow, password login, secure session cookie, logout, current-user endpoint, and frontend auth boundary.

**Success criteria:** unauthenticated users cannot access the dashboard; invalid credentials are rate-limited; migrations pass upgrade/downgrade checks.

### Milestone 3 — Dashboard shell and design system (4–6 hours)

**Deliverable:** cohesive responsive app shell, navigation, theme tokens, command palette placeholder, status/header components, loading/error/empty states, and accessibility baseline.

**Success criteria:** authenticated user can navigate a polished shell on desktop and mobile with keyboard support.

### Milestone 4 — System read-only module (3–5 hours)

**Deliverable:** Pi telemetry adapter, system overview API, service/container read-only status, dashboard cards, and resource-safe polling.

**Success criteria:** CPU, RAM, storage, temperature, network, uptime, and allowlisted service status are visible without privileged write actions.

### Milestone 5 — Assistant gateway foundation (4–6 hours)

**Deliverable:** conversations/messages persistence, provider-neutral model gateway, streaming boundary, provider configuration, normalized errors, and a read-only tool registry.

**Success criteria:** user can send a message through one configured provider and see a traceable response; a read-only tool call is validated and audited.

### Milestone 6 — Tasks, homework, reminders (4–6 hours)

**Deliverable:** task CRUD, due-date views, reminders/jobs, notifications, assistant read/create task tools with confirmation rules.

**Success criteria:** user can manage homework and receive a reminder; assistant cannot write without the correct permission/policy.

### Milestone 7 — Notes and scoped search (4–6 hours)

**Deliverable:** notes module, tags, full-text search boundary, source-aware assistant retrieval, and user deletion controls.

**Success criteria:** user can search notes and ask the assistant a question whose answer includes source references.

### Milestone 8 — Safe host actions and operations (3–5 hours)

**Deliverable:** explicit confirmation UI, audited allowlisted service restart/backup actions, job status, and operational notifications.

**Success criteria:** dangerous actions cannot be triggered by arbitrary AI text and every action has an audit record.

### Milestone 9 — Files, projects, Git, and Docker views (4–6 hours)

**Deliverable:** recent files, approved-path explorer, project dashboard, repository metadata, safe Git status operations, and Docker read-only inventory.

**Success criteria:** user can find projects and inspect repository/container state without unrestricted host access.

### Milestone 10 — Deployment hardening (3–5 hours)

**Deliverable:** ARM64 production Compose profile, reverse proxy, systemd startup, SSD mounts, backup rotation, restore drill, logs, and upgrade runbook.

**Success criteria:** the stack recovers after reboot, backups restore, and no database/secrets/runtime data are committed.

### Milestone 11 — Integrations and expansion framework (4–6 hours)

**Deliverable:** calendar/media/finance integration ports, plugin manifest/permission contract, provider health UI, and documentation for adding modules.

**Success criteria:** an integration can be enabled or disabled without changing core modules, and failures degrade gracefully.

## 16. Documentation status

Present in this Phase 0/Phase 1 and Milestone 1 foundation:


- `README.md`
- `CHANGELOG.md`
- `LICENSE`
- `.gitignore`
- `.env.example`
- `.dockerignore`
- `docker-compose.yml`
- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/DATABASE.md`
- `docs/AI_SYSTEM.md`
- `docs/DEVELOPMENT.md`
- `docs/SETUP.md`
- `docs/DEPLOYMENT.md`
- `docs/SECURITY.md`
- `docs/ENVIRONMENT.md`
- `docs/adr/0001-modular-monolith.md`
- `docs/adr/0002-sqlite-first.md`
- `docs/adr/0003-local-ai-gateway.md`

Infrastructure skeleton documentation and Milestone 1 Dockerfiles are present under `infrastructure/`. Database migrations, authentication, and feature modules remain intentionally deferred until the next approved milestone. The database, AI system, and development handoff documents now live under `docs/` and must be updated with future milestones.

Documentation must be updated in the same commit as the feature or milestone it describes.

## 17. Open decisions requiring owner approval

These decisions should be answered before or during the next milestone that depends on them:

1. **Network exposure:** LAN-only initially, or remote access through a VPN/tunnel?
2. **Cooling:** is the Raspberry Pi actively cooled for sustained workloads?
3. **AI provider default:** hosted OpenAI-compatible/NVIDIA NIM first, or a local model endpoint first?
4. **Reverse proxy:** Caddy, Traefik, or another approved option?
5. **Backups:** SSD-only rotation initially, or a second backup destination from day one?
6. **Initial identity model:** one owner account only, or invite-ready roles in Milestone 2?
7. **External integrations:** which calendar, finance, media, and file providers are priorities?
8. **Data retention:** desired retention for conversations, telemetry, logs, and backups?
9. **Destructive actions:** which system actions should be enabled first, if any?

## 18. Decision summary

- Start as a modular monolith, not microservices.
- Keep the web console and API separate at runtime.
- Use SQLAlchemy + Alembic from the first database migration.
- Use SQLite on the Pi initially, with PostgreSQL validation and migration support.
- Put all AI providers behind an internal normalized gateway.
- Expose only typed, permissioned, auditable tools to the AI.
- Make read-only features precede system write actions.
- Treat the external SSD as primary runtime storage, never as the only backup.
- Keep the Pi deployment LAN-private by default.
- Do not generate the next milestone's feature code until its implementation plan is approved by the owner.
