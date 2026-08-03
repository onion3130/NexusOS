# NexusOS API

**Current milestone:** Milestone 1
**Status:** Only the health endpoints below are implemented. All other API sections are planned contracts.
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

It does not open `DATABASE_URL`, perform migrations, authenticate a caller, or contact an AI provider.

Ready response `200`:

```json
{
  "status": "ready",
  "checks": {
    "storage": {
      "status": "ok",
      "free_bytes": 123456789
    }
  },
  "checked_at": "2026-08-02T18:30:00+00:00"
}
```

Missing or unavailable storage returns `503` with `status: "not_ready"` and a safe reason such as `data_dir_missing` or `storage_unavailable`. Paths, credentials, and stack traces are not returned.

## Current API behavior

- There is no authentication middleware.
- There is no database dependency.
- There is no error-envelope middleware yet.
- There is no request-ID middleware yet.
- There are no feature routes beyond health.
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

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/sessions`
- `DELETE /api/v1/auth/sessions/{id}`

### Assistant and jobs

- `GET/POST /api/v1/conversations`
- `GET /api/v1/conversations/{id}`
- `POST /api/v1/conversations/{id}/messages`
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
