# NexusOS API

**Current milestone:** Milestone 5 — assistant gateway
**Status:** Health, identity/session, read-only system, and bounded assistant conversation endpoints below are implemented. Other API sections are planned contracts.
**Base path:** `/api/v1`
**Last updated:** 2026-08-02

This document is an agent handoff. Do not call or implement a planned endpoint as if it already exists. The FastAPI route files and tests are authoritative for current behavior.

## Implemented API

### `GET /api/v1/health/live`

Public process liveness endpoint. It performs no storage or database check.

Response `200`:

```json
{
  "status": "ok",
  "service": "nexus-api",
  "version": "0.1.0"
}
```

### `GET /api/v1/health/ready`

Public development readiness endpoint. It checks the configured `DATA_DIR`:

1. The directory exists.
2. Disk usage can be read.
3. The API user can create and delete a temporary file.
4. The configured SQLite database is reachable and includes the identity migration head.

It never performs migrations, authenticates a caller, or contacts an AI provider.

Ready response `200`:

```json
{
  "status": "ready",
  "checks": {
    "storage": {
      "status": "ok",
      "free_bytes": 123456789
    },
    "database": {
      "status": "ok"
    }
  },
  "checked_at": "2026-08-02T18:30:00+00:00"
}
```

Missing or unavailable storage returns `503` with `status: "not_ready"` and a safe reason such as `data_dir_missing` or `storage_unavailable`. Paths, credentials, and stack traces are not returned.

## Implemented identity API

### `POST /api/v1/auth/login`

Creates an authenticated session from an owner account. Sets access, refresh, and readable CSRF cookies. Invalid credentials return a generic `401`; repeated failures receive bounded `429` backoff.

### `POST /api/v1/auth/refresh`

Requires the refresh cookie and matching CSRF cookie/header. Rotates refresh and CSRF secrets and issues a new access token.

### `POST /api/v1/auth/logout`

Requires the authenticated access cookie and matching CSRF header. Revokes the current session and clears auth cookies.

### `GET /api/v1/auth/me`

Returns the authenticated user, roles, and permissions without secret material.

### `GET /api/v1/auth/sessions`

Lists the authenticated user's session metadata without token values.

### `DELETE /api/v1/auth/sessions/{id}`

Requires CSRF for cookie authentication and revokes an owned session.

## Implemented system API

### `GET /api/v1/system/overview`

Authenticated read-only Raspberry Pi telemetry. Returns CPU, memory, configured storage-volume usage, thermal reading, uptime, network counters, and an explicit unavailable service/container status boundary. The route reads fixed host-provided sources only; it does not execute commands, accept paths, mount Docker, or mutate the host.

A `200` response may have `status: "degraded"` when one or more sources are unavailable. Safe source reasons include `cpu_unavailable`, `memory_unavailable`, `storage_unavailable`, `temperature_unavailable`, `uptime_unavailable`, `network_unavailable`, and `service_status_unavailable`.

## Implemented assistant API

### `POST /api/v1/conversations`

Create an authenticated conversation owned by the current user. The optional title is bounded to 120 characters.

### `GET /api/v1/conversations`

List up to 100 conversations owned by the current user, newest first.

### `GET /api/v1/conversations/{id}`

Return one owned conversation and up to 200 ordered messages. Unauthorized ownership is represented as `404`.

### `POST /api/v1/conversations/{id}/messages`

Persist a bounded user message, call the configured server-side gateway outside the SQLite transaction, and persist normalized model/tool metadata and the assistant response. With `AI_PROVIDER=disabled`, the user message and a safe disabled model-run record are retained while the endpoint returns `503` with `ai_provider_disabled`.

The only registered tool is `system.get_overview`; it requires `system.read_overview`, accepts no arguments, and never executes commands, accesses Docker, or accepts filesystem paths. Provider targets are server-side and protected by literal/runtime SSRF checks with validated-IP connections; response bodies are bounded and provider keys/upstream payloads never reach the browser.

Streaming, jobs, approvals, tasks, notes, files, and host-action endpoints remain planned rather than live.

## Current API behavior

- Authentication supports HttpOnly access/refresh cookies and explicit bearer access tokens.
- Cookie-authenticated mutations require `X-CSRF-Token` matching the readable CSRF cookie.
- Database migrations are explicit; application startup never mutates schema.
- There is no error-envelope middleware or request-ID middleware yet.
- The only feature route is the authenticated read-only system overview; domain feature routes remain unimplemented.
- FastAPI's development OpenAPI endpoints may be available locally; production exposure is not configured.

## Planned API conventions

Future endpoints will remain under `/api/v1` and should use:

- JSON request/response bodies.
- Opaque UUID resource IDs.
- ISO 8601 UTC timestamps.
- Cursor pagination with bounded limits.
- `401` for missing identity, `403` for insufficient permission, `404` without leaking unauthorized existence, `409` for conflicts, `422` for validation, and `503` for unavailable dependencies.
- A safe error shape:

```json
{
  "error": {
    "code": "stable_machine_code",
    "message": "Safe human-readable message.",
    "request_id": "request-id",
    "details": {}
  }
}
```

These conventions are design targets until implemented and tested.

## Planned API groups

The following are not live routes. They are the intended order after identity and persistence exist:

### Identity

The identity routes are implemented above. Future identity work must extend the existing authentication boundary rather than create a parallel one.

### Assistant and jobs

The conversation and message routes are implemented above. The following remain planned:

- `GET /api/v1/conversations/{id}/stream`
- `GET /api/v1/jobs/{id}`
- `POST /api/v1/ai/tool-calls/{id}/approve`

### Productivity

- `GET/POST /api/v1/tasks`
- `GET/PATCH/DELETE /api/v1/tasks/{id}`
- `GET/POST /api/v1/reminders`
- `GET /api/v1/notifications`
- `GET/POST /api/v1/notes`

### System and integrations

- `GET /api/v1/system/overview`
- `GET /api/v1/system/services`
- `GET /api/v1/system/logs`
- `POST /api/v1/system/actions/{action}`
- `GET /api/v1/files/recent`
- `GET /api/v1/projects`
- `GET /api/v1/git/repositories`
- `GET /api/v1/docker/containers`

Every planned write action requires authentication, authorization, typed input, confirmation when risky, idempotency where appropriate, and an audit event. No future route may accept arbitrary shell commands, Docker arguments, absolute filesystem paths, or provider URLs from the client.

See [`DATABASE.md`](DATABASE.md), [`AI_SYSTEM.md`](AI_SYSTEM.md), and [`ROADMAP.md`](ROADMAP.md) before implementing a new route.
