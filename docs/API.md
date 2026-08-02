# NexusOS API Contract

**Status:** Proposed — implementation begins after architecture approval  
**Version:** `/api/v1`  
**Transport:** JSON over HTTPS; authenticated assistant streaming uses Server-Sent Events (SSE)

This document defines the contract that implementations must follow. FastAPI OpenAPI output is the executable source of truth once Milestone 1 begins; changes to this document and the implementation must land together.

## 1. Common rules

### Base URL and headers

```text
/api/v1
```

Clients should send:

```http
Accept: application/json
Content-Type: application/json
X-Request-ID: optional-client-correlation-id
```

State-changing requests using cookie authentication must also send:

```http
Origin: https://nexus.local
X-CSRF-Token: session-csrf-token
```

The server returns `X-Request-ID` on every response. A client-provided request ID may be replaced when invalid or too long.

### Authentication and permissions

Unless marked public, endpoints require the authenticated session cookie. Each endpoint documents a permission key. The server is authoritative; UI visibility is not authorization.

Common permission examples:

- `identity.read_self`
- `tasks.read`, `tasks.write`
- `notes.read`, `notes.write`
- `assistant.use`, `assistant.approve_tool`
- `system.read`, `system.action`
- `files.read`, `git.read`, `docker.read`
- `admin.manage_users`, `admin.manage_integrations`

### JSON conventions

- IDs are opaque UUID strings.
- Timestamps are ISO 8601 UTC strings, for example `2026-08-02T18:30:00Z`.
- Optional values are omitted or explicitly `null` according to each schema; one convention must be selected consistently during implementation.
- Unknown request fields are rejected unless an endpoint explicitly supports an extension object.
- Response objects include a stable `type` or resource shape where polymorphism exists.
- Secrets, password hashes, raw provider credentials, and internal stack traces never appear in API responses.

## 2. Error envelope

All non-success responses use this shape:

```json
{
  "error": {
    "code": "stable_machine_code",
    "message": "Safe human-readable message.",
    "request_id": "req_01J...",
    "details": {}
  }
}
```

`details` contains safe field-level validation information when useful. It must not disclose whether an unauthorized resource exists.

Standard status codes:

| Status | Meaning |
|---:|---|
| 200 | Successful read or completed mutation |
| 201 | Resource created |
| 202 | Accepted asynchronous job |
| 204 | Successful operation with no response body |
| 400 | Malformed request or unsupported action |
| 401 | Missing, expired, or invalid authentication |
| 403 | Authenticated but not permitted |
| 404 | Resource not found or intentionally undisclosed |
| 409 | Conflict, stale version, duplicate idempotency key, or invalid state transition |
| 422 | Schema validation failure |
| 429 | Rate limit or retry backoff |
| 500 | Unexpected server failure; safe generic message only |
| 503 | Dependency unavailable or service not ready |

## 3. Pagination and filtering

List endpoints use cursor pagination:

```http
GET /api/v1/tasks?limit=25&cursor=opaque-cursor&status=open&sort=due_at
```

```json
{
  "items": [],
  "page": {
    "limit": 25,
    "next_cursor": "opaque-cursor-or-null",
    "has_more": false
  }
}
```

Rules:

- Default page size: 25.
- Maximum page size: 100.
- Cursors are opaque and may expire.
- Sorting must be deterministic; ties use the resource ID.
- Filters are endpoint-specific and documented in OpenAPI.
- Search endpoints return a `source` or `resource_type` field when results span domains.

## 4. Health and authentication

### `GET /health/live`

**Permission:** public on the private network.  
**Purpose:** process liveness only; must not require the database.

Response `200`:

```json
{ "status": "ok", "service": "nexus-api", "version": "0.1.0" }
```

### `GET /health/ready`

**Permission:** public on the private network.  
**Purpose:** readiness of required dependencies.

Response `200`:

```json
{
  "status": "ready",
  "checks": {
    "database": { "status": "ok", "latency_ms": 3 },
    "storage": { "status": "ok", "free_bytes": 123456789 }
  }
}
```

Response `503` has the same shape with `status: "not_ready"`; sensitive connection details are omitted.

### `POST /auth/login`

**Permission:** public, rate-limited.  
**Request:**

```json
{ "username": "owner", "password": "user-entered-password" }
```

Response `200` sets the Secure, HttpOnly session/refresh cookie and returns:

```json
{
  "user": { "id": "uuid", "username": "owner", "roles": ["owner"] },
  "expires_at": "2026-08-02T18:45:00Z"
}
```

Invalid credentials return the same generic `401` response regardless of whether the username exists.

### `POST /auth/logout`

**Permission:** authenticated session.  
Response `204`; revokes the current session and clears the cookie.

### `GET /auth/me`

**Permission:** authenticated.  
Response `200`:

```json
{
  "id": "uuid",
  "username": "owner",
  "roles": ["owner"],
  "permissions": ["system.read", "tasks.write"],
  "session": { "id": "uuid", "expires_at": "2026-08-02T18:45:00Z" }
}
```

### `GET /auth/sessions` and `DELETE /auth/sessions/{id}`

**Permission:** authenticated; users may manage only their sessions.  
List returns paginated session metadata without token values. Delete revokes the selected session and returns `204`.

## 5. Generic asynchronous jobs

Long-running work never blocks an HTTP request until completion.

### Job envelope

```json
{
  "job": {
    "id": "uuid",
    "kind": "finance.stock_scan",
    "status": "queued",
    "progress": 0,
    "created_at": "2026-08-02T18:30:00Z",
    "started_at": null,
    "finished_at": null,
    "result_type": null,
    "error_code": null
  }
}
```

Allowed statuses: `queued`, `running`, `succeeded`, `failed`, `cancel_requested`, `cancelled`, `expired`.

### `GET /jobs/{id}`

**Permission:** job owner or an authorized administrator.  
Response `200` returns the job envelope. Results are referenced by `result_type` and a domain-specific result endpoint; large results are not embedded by default.

### `POST /jobs/{id}/cancel`

**Permission:** job owner or authorized administrator; job must be cancellable.  
Request may include an idempotency key.  
Response `202` returns the updated job envelope with `cancel_requested`, or `409` if cancellation is not valid for the current state.

## 6. Assistant API

### `GET /conversations`

**Permission:** `assistant.use`; returns conversations owned by the user using cursor pagination.

### `POST /conversations`

**Permission:** `assistant.use`.  
Request:

```json
{ "title": "Optional title", "model_policy": "default" }
```

Response `201` returns a conversation resource with an empty message list.

### `GET /conversations/{id}`

**Permission:** `assistant.use` on the conversation.  
Returns conversation metadata, paginated messages, and active job metadata.

### `POST /conversations/{id}/messages`

**Permission:** `assistant.use`.  
Request:

```json
{
  "content": "Show homework due tomorrow.",
  "client_message_id": "client-generated-id",
  "response_mode": "job"
}
```

Response `202`:

```json
{
  "message": {
    "id": "uuid",
    "role": "user",
    "content": "Show homework due tomorrow.",
    "created_at": "2026-08-02T18:30:00Z"
  },
  "job": { "id": "uuid", "kind": "assistant.completion", "status": "queued" }
}
```

The request is idempotent for the same authenticated user, conversation, and `client_message_id`.

### `GET /conversations/{id}/stream`

**Permission:** `assistant.use` on the conversation.  
**Content type:** `text/event-stream`.  
**Query:** `job_id` is required and must belong to the conversation.

Events:

```text
event: message.delta
data: {"job_id":"uuid","text":"Homework"}

 event: tool.pending
data: {"tool_call_id":"uuid","tool_key":"tasks.list_due","requires_approval":false}

 event: job.completed
data: {"job_id":"uuid","message_id":"uuid"}

 event: job.failed
data: {"job_id":"uuid","error_code":"provider_unavailable"}
```

The stream sends periodic comments/heartbeats, supports `Last-Event-ID`, and closes after a terminal event. Reconnects replay only retained events for the authorized job. The client can cancel through `POST /conversations/{id}/cancel`.

### `POST /conversations/{id}/cancel`

**Permission:** `assistant.use`.  
Request: `{ "job_id": "uuid" }`.  
Response `202` returns the job envelope; `409` means it is already terminal.

### `GET /ai/providers` and `GET /ai/tools`

**Permission:** authenticated; return capabilities only. Provider secrets and raw upstream URLs are never returned.

Tools include key, version, description, risk level, required permission, and enabled state. Tool arguments are not accepted from this endpoint.

### `POST /ai/tool-calls/{id}/approve`

**Permission:** `assistant.approve_tool`.  
Request:

```json
{ "decision": "approve", "confirmation_text": "Restart Jellyfin" }
```

Allowed decisions: `approve`, `deny`. The server verifies the pending call has not expired, changed arguments, or been executed already. Response `202` returns the related job envelope.

### AI memory and summaries

Memory endpoints are user-scoped and require explicit permissions. The assistant may retrieve approved memory through the service layer, but model output is never the authorization layer.

- `GET /ai/memories` with `assistant.memory_read` returns cursor-paginated memory metadata: ID, kind, source reference, created/updated time, retention, and a redacted preview.
- `POST /ai/memories` with `assistant.memory_write` accepts `{ "kind": "preference", "content": "...", "source": "user_explicit" }` and returns `201`. Implicit model guesses cannot be persisted as user memory without an explicit policy.
- `DELETE /ai/memories/{id}` with `assistant.memory_delete` permanently removes the selected memory and embeddings, returning `204`.
- `POST /conversations/{id}/summaries` with `assistant.use` creates a bounded `assistant.summary` job and returns `202`; the job stores a summary reference, source message range, model metadata, and retention policy.
- `GET /conversations/{id}/summaries` with `assistant.use` returns cursor-paginated summaries and source ranges; unauthorized conversations are not disclosed.
- `POST /ai/retrieval` with the relevant domain read permissions accepts `{ "query": "...", "domains": ["notes", "memories"], "limit": 10 }` and returns source IDs, snippets, scores, and access-checked citations. It never returns hidden content merely because a semantic index matched it.

Memory writes and deletions create audit events. Retention cleanup is an asynchronous job and does not delete user data outside the declared retention scope.

## 7. Productivity resources

### Tasks

`GET /tasks` supports `status`, `due_before`, `due_after`, and `assignee` filters.  
`POST /tasks` request:

```json
{
  "title": "Finish chemistry worksheet",
  "description": "Optional details",
  "due_at": "2026-08-03T23:00:00Z",
  "priority": "normal",
  "source": "manual"
}
```

Response `201` returns the task resource. `PATCH /tasks/{id}` accepts a partial update plus optional `expected_version` for optimistic concurrency. `DELETE /tasks/{id}` is soft-delete by default and returns `204`.

Allowed task statuses: `open`, `in_progress`, `completed`, `cancelled`.

### Reminders and notifications

- `GET /reminders` with `tasks.read` returns cursor-paginated reminders with task/notification target, schedule, timezone, next run, status, and last result.
- `POST /reminders` with `tasks.write` accepts `{ "task_id": "uuid", "schedule": "2026-08-03T15:00:00Z", "timezone": "America/Chicago", "channel": "dashboard" }` and returns `201`.
- `PATCH /reminders/{id}` with `tasks.write` accepts partial schedule/status changes plus `expected_version`, returning `200` or `409` for a stale version.
- `DELETE /reminders/{id}` with `tasks.write` is idempotent and returns `204`.
- `GET /notifications` with `notifications.read` returns cursor-paginated notifications containing ID, type, title, safe body, source reference, created time, read time, and optional action metadata.
- `POST /notifications/{id}/read` with `notifications.read` is idempotent and returns `204`.
- `POST /notifications/read-all` with `notifications.read` marks the user's visible notifications read and returns `204`.

Reminder execution creates a notification, pending approval, or a documented non-destructive result. It must not silently execute a destructive action. Failed delivery records a bounded error code and retry state; it never stores provider credentials in the notification payload.

A reminder schedule uses UTC internally and retains the user timezone for display. Disabling/deleting a reminder cancels future runs but does not rewrite historical notifications.

### Notes

`GET/POST /notes`, `GET/PATCH/DELETE /notes/{id}` follow the common resource and pagination rules. Note search returns source IDs and snippets, not hidden notes owned by another user.

## 8. System and integration resources

### `GET /system/overview`

**Permission:** `system.read`.  
Returns CPU load, memory totals/usage, storage mounts and thresholds, temperature, network summary, uptime, and capture timestamp. Values may be `null` when an adapter is unavailable; the response includes per-field status.

### `GET /system/snapshots`

**Permission:** `system.read`.  
Returns cursor-paginated historical telemetry with `{ captured_at, cpu_percent, memory_used_bytes, storage, temperature_celsius, network, uptime_seconds }`. Retention and sampling intervals are instance settings; unavailable sensors use explicit `null` plus a field status.

### `GET /system/services`

**Permission:** `system.read`.  
Returns only configured service/container identifiers, state, health, restart count, and last check. It does not expose arbitrary host process details by default.

### `GET /system/logs`

**Permission:** `system.logs_read`.  
Returns cursor-paginated, redacted log entries with `{ timestamp, level, source, message, request_id }`. Filters include source, level, and time range. Raw secrets, tokens, full prompts, and unbounded stack traces are excluded.

### `GET /system/processes`

**Permission:** `system.process_read`.  
Returns a bounded, sampled list of process metadata `{ pid, name, cpu_percent, memory_bytes, user, started_at }`. Command-line arguments and environment variables are omitted by default. The endpoint never accepts a PID action from the client.

### `POST /system/actions/{action}`

**Permission:** `system.action`; confirmation required for all write actions.  
Request includes a typed parameter object and an idempotency key. `action` is selected from a server allowlist; arbitrary shell strings are rejected. Response `202` returns a job envelope.

Initial actions:

- `restart_service`: owner or approved admin; typed `service_key`; returns `system.restart_service` job.
- `restart_docker`: owner-only; no arbitrary arguments; returns `system.restart_docker` job.
- `backup_data`: owner or approved admin; typed backup profile; returns `system.backup` job.
- `run_scheduled_task`: owner or approved admin; typed scheduler job ID; returns `system.scheduled_task` job.
- `reboot`: owner-only, explicit confirmation phrase, maintenance-window warning; returns `system.reboot` job and may terminate the API connection.
- `shutdown`: owner-only, explicit confirmation phrase, second confirmation step, and no active critical job; returns `system.shutdown` job.

Reboot and shutdown requests are rejected with `409` when a conflicting maintenance/backup job is active. Every action is audited before execution and the adapter must use a fixed implementation, never a shell string supplied by the client or model.

### Files and cross-domain search

Configured filesystem roots are server-side records. Clients send a root ID and relative path; absolute paths, `..` traversal, symlink escapes, and unapproved roots are rejected.

#### `GET /files/recent`

**Permission:** `files.read`.  
Cursor-paginated response:

```json
{
  "items": [
    {
      "id": "uuid",
      "root_id": "uuid",
      "relative_path": "projects/nexus/README.md",
      "name": "README.md",
      "kind": "file",
      "size_bytes": 2408,
      "modified_at": "2026-08-02T18:30:00Z",
      "content_hash": "sha256:..."
    }
  ],
  "page": { "limit": 25, "next_cursor": null, "has_more": false }
}
```

`GET /files/search` accepts `q`, optional `root_id`, `kind`, and cursor pagination. Search is limited to indexed approved roots and returns snippets only when the caller has access. `GET /files/{id}` returns metadata; file content is a separate bounded download/read endpoint and is never executed by the server.

`POST /files/index-jobs` accepts `{ "root_id": "uuid", "mode": "incremental" }` and returns `202` with a `files.index` job. `DELETE /files/{id}` is disabled by default; when enabled it requires `files.delete`, explicit confirmation, an idempotency key, and creates an auditable `files.delete` job. It never accepts a shell command or arbitrary path.

#### `POST /search`

**Permission:** authenticated plus domain read permissions.  
Request:

```json
{ "query": "chemistry", "domains": ["notes", "tasks", "files"], "limit": 20 }
```

Response `200`:

```json
{
  "items": [
    {
      "resource_type": "note",
      "resource_id": "uuid",
      "title": "Chemistry review",
      "snippet": "...bond polarity...",
      "score": 0.91,
      "source_url": "/notes/uuid"
    }
  ],
  "page": { "limit": 20, "next_cursor": null, "has_more": false }
}
```

The server removes domains the principal cannot read; it does not use the AI model as the authorization layer.

### Projects and Git

Projects are logical workspaces that reference configured repositories and filesystem roots; they do not grant new filesystem access.

#### `GET /projects` and `POST /projects`

**Permissions:** `projects.read` / `projects.write`.  
Create request:

```json
{
  "name": "NexusOS",
  "description": "Personal AI operating system",
  "repository_id": "uuid",
  "root_id": "uuid"
}
```

Response `201` returns the project resource. `GET /projects/{id}` returns metadata and latest safe status; project deletion is a soft archive and returns `204`.

#### `GET /git/repositories`

**Permission:** `git.read`.  
Returns only configured repository metadata:

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "NexusOS",
      "path_ref": "configured-root-relative-path",
      "default_branch": "main",
      "remote_host": "github.com",
      "last_checked_at": "2026-08-02T18:30:00Z"
    }
  ],
  "page": { "limit": 25, "next_cursor": null, "has_more": false }
}
```

#### `GET /git/repositories/{id}/status`

**Permission:** `git.read`.  
Response `200` includes branch, ahead/behind counts, dirty-file count, and bounded file status entries. Credentials, remote URLs containing tokens, and arbitrary paths are omitted.

#### `POST /git/repositories/{id}/actions/{action}`

**Permission:** `git.write`; owner confirmation required.  
Allowed initial actions: `fetch`, `pull`, `create_branch`, `commit`, `push`. The request contains typed fields such as `{ "branch": "feature/name", "message": "...", "expected_branch": "main" }`; arbitrary Git arguments are rejected. Response `202` returns a `git.action` job. `push`, force options, history rewriting, and destructive reset actions are disabled by default and must never be enabled through an AI-generated argument alone.

### Docker

Nexus uses a restricted Docker adapter. The API does not expose the Docker socket to the web container or plugins; only a dedicated host adapter may access it.

#### `GET /docker/containers`

**Permission:** `docker.read`.  
Cursor-paginated response:

```json
{
  "items": [
    {
      "id": "container-id-prefix",
      "name": "nexus-api",
      "image": "reviewed-image-reference",
      "state": "running",
      "health": "healthy",
      "restart_count": 0,
      "started_at": "2026-08-02T18:00:00Z"
    }
  ],
  "page": { "limit": 25, "next_cursor": null, "has_more": false }
}
```

Only containers in the configured allowlist are returned.

#### `POST /docker/containers/{id}/actions/{action}`

**Permission:** `docker.action`; owner confirmation required.  
Allowed actions: `restart`, `stop`, `start`. Request may include a typed timeout and idempotency key. Response `202` returns a `docker.action` job; unknown containers, arbitrary container IDs, image pulls, privileged flags, and host mounts are rejected.

### Media integrations

Media adapters are outbound-only and optional. Credentials are stored as encrypted integration references and never returned.

#### `GET /media/status`

**Permission:** `media.read`.  
Response `200`:

```json
{
  "integrations": [
    {
      "key": "jellyfin",
      "enabled": true,
      "reachable": true,
      "version": "10.x",
      "active_users": 1,
      "last_checked_at": "2026-08-02T18:30:00Z"
    },
    {
      "key": "nextcloud",
      "enabled": false,
      "reachable": null,
      "error_code": null,
      "last_checked_at": null
    }
  ]
}
```

`GET /media/{integration}/health` returns a bounded provider health result.

`GET /media/{integration}/libraries` returns cursor-paginated library metadata with `media.read`. `GET /media/{integration}/items/{id}` returns sanitized item metadata. `POST /media/{integration}/playback` accepts `{ "item_id": "provider-item-id", "client_id": "configured-client" }`, requires `media.control`, and returns `202` with a `media.playback` job. `POST /media/{integration}/sync` requires `media.sync`, an idempotency key, and returns a `media.sync` job. `GET /media/{integration}/cameras` returns configured camera metadata without credentials; `GET /media/{integration}/cameras/{id}/snapshot` requires `media.camera_read`, returns a bounded image response, and never exposes snapshots to the AI context without an explicit user request.

All provider item IDs are scoped to the configured integration account. Playback, snapshot, and sync operations return `503` with a stable dependency error when unavailable; provider URLs, tokens, and full upstream payloads are never returned.

### Finance

Finance data is treated as sensitive personal data. Provider credentials are encrypted references, market data is timestamped, and no endpoint presents financial information as investment advice.

#### `GET /finance/watchlists` and `POST /finance/watchlists`

**Permissions:** `finance.read` / `finance.write`.  
Create request:

```json
{
  "name": "Long term",
  "symbols": ["AAPL", "MSFT"],
  "provider": "configured-market-provider"
}
```

Response `201` returns the watchlist and symbol metadata, not live prices unless explicitly requested.

#### `GET /finance/watchlists/{id}/snapshot`

**Permission:** `finance.read`.  
Response `200`:

```json
{
  "watchlist_id": "uuid",
  "as_of": "2026-08-02T18:30:00Z",
  "currency": "USD",
  "quotes": [
    { "symbol": "AAPL", "price": 0.0, "change": 0.0, "source": "provider", "delayed": true }
  ]
}
```

Unavailable or delayed values are explicit; the API does not fabricate quotes.

#### `POST /finance/scans`

**Permission:** `finance.scan`; owner confirmation if the scan can create external-provider cost.  
Request:

```json
{ "watchlist_id": "uuid", "criteria": { "max_results": 50 }, "provider": "default" }
```

Response `202` returns a `finance.stock_scan` job. `GET /finance/scans/{job_id}/results` returns cursor-paginated, timestamped result rows only after the job succeeds. Results include a disclaimer that they are informational, not financial advice.

#### `GET /finance/portfolio`

**Permission:** `finance.read`; disabled until an owner-approved provider and data model exist. When enabled, it returns holdings metadata and valuation snapshots with explicit data freshness. Mutating trades are out of scope and prohibited in the initial API.

External provider failures return stable dependency errors and do not expose credentials, request URLs, or full upstream payloads.

### Calendar

Calendar data is owned by the authenticated user and scoped to configured calendar integrations.

- `GET /calendar/calendars` with `calendar.read` returns configured calendars and read/write capability flags.
- `GET /calendar/events?calendar_id={id}&from={utc}&to={utc}` with `calendar.read` returns cursor-paginated event summaries.
- `POST /calendar/events` with `calendar.write` accepts `{ "calendar_id": "uuid", "title": "...", "starts_at": "...", "ends_at": "...", "timezone": "UTC", "description": null }` and returns `201` with the event resource.
- `PATCH /calendar/events/{id}` with `calendar.write` requires `expected_version` and returns `200`; stale updates return `409`.
- `DELETE /calendar/events/{id}` with `calendar.write` and an idempotency key returns `204` or `202` with a `calendar.delete` job when the provider is asynchronous.
- `POST /calendar/sync` with `calendar.sync` returns a `calendar.sync` job and never blocks on provider I/O.

Provider conflicts return `409`; unavailable integrations return `503`. Events from calendars the user cannot read are not disclosed.

### Downloads

Downloads are server-created jobs, not arbitrary URL fetches. An allowlisted integration or user-approved URL policy must provide the source.

- `GET /downloads` with `files.read` returns cursor-paginated jobs and sanitized metadata.
- `POST /downloads` with `files.write` accepts `{ "source_type": "integration", "source_id": "uuid", "destination_root_id": "uuid", "relative_path": "downloads/item.bin" }` and returns `202` with a `files.download` job.
- `GET /downloads/{id}` with `files.read` returns the job envelope plus byte progress.
- `POST /downloads/{id}/cancel` with `files.write` returns `202` or `409` for a terminal job.

Destination roots and relative paths use the same traversal/symlink protections as `/files`. The API rejects arbitrary shell commands, unrestricted URLs, private-network SSRF targets, and destinations outside configured roots.

### Integration accounts

Integration credentials are never accepted in general-purpose resource requests.

- `GET /integrations` with `admin.manage_integrations` returns provider keys, enabled state, capabilities, last health check, and credential status — never credential values.
- `POST /integrations` with `admin.manage_integrations` accepts a provider-specific validated configuration reference and returns `201` with redacted metadata.
- `POST /integrations/{id}/test` returns `202` with an `integration.health_check` job.
- `PATCH /integrations/{id}` enables/disables an integration and returns `200`.
- `DELETE /integrations/{id}` revokes the credential reference and returns `204` after dependent jobs are stopped or marked failed.

Provider-specific secrets are supplied through a secret-management boundary, not persisted in ordinary request logs or returned by the API.

### Settings and user profiles

- `GET /settings` with `settings.read` returns non-secret user/instance settings and their scopes.
- `PATCH /settings` with `settings.write` accepts a typed map of approved keys and returns the changed settings; unknown or secret keys are rejected.
- `GET /profiles/me` with `identity.read_self` returns username, display name, timezone, locale, theme, reduced-motion preference, and notification preferences.
- `PATCH /profiles/me` with `identity.write_self` accepts partial profile updates and returns `200`.
- `GET /admin/users` with `admin.manage_users` is cursor-paginated and returns redacted user status/role metadata.
- `PATCH /admin/users/{id}` with `admin.manage_users` changes status or roles and returns `200` with an audit event.

Password hashes, session tokens, and integration credentials are never settings or profile fields.

### Plugin management

Plugin APIs manage manifests and permissions; they do not execute plugin code inside the API process.

- `GET /plugins` with `plugins.read` returns manifest metadata, lifecycle state, requested/granted capabilities, integrity status, and health.
- `POST /plugins` with `plugins.manage` accepts a reviewed manifest reference and returns `201` in `review_required` state; unsigned or hash-mismatched manifests are rejected.
- `POST /plugins/{id}/enable` with `plugins.manage` requires owner confirmation and returns `202` with a `plugin.enable` job.
- `POST /plugins/{id}/disable` with `plugins.manage` returns `202` with a `plugin.disable` job.
- `DELETE /plugins/{id}` with `plugins.manage` returns `202` with a `plugin.remove` job after a namespaced cleanup plan is confirmed.
- `GET /plugins/{id}/health` with `plugins.read` returns a bounded health result from the private adapter network.

Plugin routes and tools are only registered after enablement and permission checks. Plugins never receive the Docker socket, host filesystem, database credentials, or arbitrary shell access.

## 9. Compatibility and evolution

- Breaking changes require a new `/api/vN` version or a documented migration period.
- Additive response fields are allowed; clients must ignore unknown response fields.
- Request fields become required only in a new version unless a safe default exists.
- Deprecated routes return a warning header and remain available for the documented migration window.
- Every API change updates OpenAPI, `docs/API.md`, frontend contracts, tests, and `CHANGELOG.md` in the same milestone commit.
