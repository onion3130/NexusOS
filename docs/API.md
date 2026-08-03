# NexusOS API

**Current milestone:** v1.0 release hardening complete
**Status:** Health, identity/session, read-only system, assistant conversations and task actions, notes/search/retrieval, confirmation-gated maintenance actions, verified SQLite backups, and audit visibility are implemented. Restore replication, embeddings, files, and streaming remain planned.
**Base path:** `/api/v1`
**Last updated:** 2026-08-03

All browser-authenticated mutations require the readable CSRF cookie value in the `X-CSRF-Token` header. Bearer-authenticated clients may use the same routes without cookie CSRF. Mutation routes accept an `Idempotency-Key`; clients must reuse the key when retrying the same operation. Reusing a key with a different payload returns `422`. All feature resources are user-owned and unauthorized resources return `404`.

## Implemented API

### Health, identity, system, and assistant

The existing health, identity, system, and conversation routes remain as documented in the previous milestone. The assistant gateway is server-configured, provider credentials remain server-side, and `AI_PROVIDER=disabled` remains safe.

### Productivity routes

#### `GET /api/v1/tasks`

Lists current-user tasks. Supports `status_filter`, `priority`, `category`, `tag`, `include_completed`, `limit`, and `cursor`. Results exclude soft-deleted tasks and are bounded to 100 items.

#### `POST /api/v1/tasks`

Creates a task with title, description, UTC due date, priority, category, tags, constrained recurrence, and reminders. Relative reminders require a due date. Titles, tags, reminders, and recurrence inputs are bounded and validated.

#### `GET /api/v1/tasks/{id}`

Returns one owned task with category, tags, recurrence, and reminder information.

#### `PATCH /api/v1/tasks/{id}`

Updates owned task fields. Completing a task must use the explicit completion action. Due-date changes recalculate relative pending reminders.

#### `POST /api/v1/tasks/{id}/complete`

Completes one task occurrence and cancels its pending reminders. For a recurring task, one future occurrence is generated atomically.

#### `DELETE /api/v1/tasks/{id}`

Soft-deletes an owned task, cancels reminders, and preserves audit/history data.

#### `GET/POST /api/v1/tasks/{id}/reminders`

Lists or adds absolute/relative reminders for an owned task.

#### `PATCH/DELETE /api/v1/reminders/{id}`

Updates or cancels an owned reminder.

#### `GET/POST/DELETE /api/v1/task-categories`

Lists, creates, and removes user-owned categories. Existing task references are cleared by the database foreign-key policy.

#### `GET/POST/DELETE /api/v1/tags`

Lists, creates, and removes user-owned tags.

### Notes and search

#### `GET /api/v1/notes`

Lists owned notes with `status_filter=active|archived|all`, optional tag, bounded limit, and cursor filters.

#### `POST /api/v1/notes`

Creates a user-owned note with title, plain-text/Markdown-compatible content, tags, and active/archived status. Search projection and deterministic retrieval chunks are generated atomically.

#### `GET /api/v1/notes/{id}`

Returns one owned live note with content version and tags.

#### `PATCH /api/v1/notes/{id}`

Updates title, content, tags, or status. Source changes increment `content_version` and regenerate derived search/chunk data.

#### `POST /api/v1/notes/{id}/archive` / `POST /api/v1/notes/{id}/restore`

Perform explicit archive/restore transitions.

#### `DELETE /api/v1/notes/{id}`

Soft-deletes an owned note and removes it from normal search visibility.

#### `GET /api/v1/search`

Performs bounded SQLite FTS5 lexical search over owned note titles, content, and tags. Results include source type, source ID, chunk ID, excerpt, score, tags, and source version. Archived notes are excluded unless `include_archived=true`.

#### `GET /api/v1/notes/{id}/chunks`

Returns current-version deterministic retrieval chunks for one owned note.

#### `GET /api/v1/search/retrieve`

Returns bounded source-aware lexical retrieval results for future assistant/RAG context assembly.

### Notifications

#### `GET /api/v1/notifications`

Returns persistent in-app notifications and the unread count. Supports `unread_only` and bounded `limit` filters.

#### `POST /api/v1/notifications/{id}/read`

Marks one owned notification as read.

#### `POST /api/v1/notifications/read-all`

Marks all current-user notifications as read.

The dedicated worker converts due reminders into notifications using a deterministic reminder deduplication key. It runs separately from the API in Compose.

### Assistant task actions

The assistant registry supports the following read-only note tools and task tools:

- `notes.search` — bounded search over the user's owned notes
- `notes.read` — bounded read of one owned note as untrusted source material

- `tasks.list` — read-only task lookup
- `tasks.create` — confirmation-gated creation
- `tasks.update` — confirmation-gated update
- `tasks.complete` — confirmation-gated completion
- `tasks.delete` — confirmation-gated soft deletion

#### `POST /api/v1/ai/tool-calls/{id}/approve`

Approves and executes one owned, unexpired task mutation proposal after permission and input validation.

#### `POST /api/v1/ai/tool-calls/{id}/reject`

Rejects one owned task mutation proposal without executing it.

Task mutation proposals expire after a bounded period and all approvals, rejections, and task changes are audited.

### Safe host-action and maintenance routes

#### `GET /api/v1/system/actions`

Returns the server-owned allowlist of enabled maintenance actions. The current catalog contains database backup creation, backup verification, and live database integrity checking. It never exposes arbitrary executables, filesystem paths, Docker operations, reboot, shutdown, package management, or systemd controls.

#### `POST /api/v1/system/actions/proposals`

Creates a durable, expiring proposal without executing a host operation. The typed action key and action-specific input are validated server-side. Cookie-authenticated requests require CSRF, the `system.host_actions` permission, and an `Idempotency-Key`.

#### `GET /api/v1/system/actions/proposals` / `GET /api/v1/system/actions/proposals/{id}`

Lists or reads only the current user's proposals and their bounded lifecycle state.

#### `POST /api/v1/system/actions/proposals/{id}/confirm`

Explicitly confirms one unexpired proposal and queues one durable `host_action` worker job. Confirmation is required even when the request originated from the assistant.

#### `POST /api/v1/system/actions/proposals/{id}/reject`

Rejects a proposal without creating a job or invoking an executor.

#### `GET /api/v1/system/backups`

Lists verified/failed backup metadata owned by the current user. It returns relative NexusOS paths, size, SHA-256, status, integrity result, and timestamps; it never returns file contents or arbitrary paths.

#### `GET /api/v1/system/jobs/{id}`

Returns the status of a host-action job only when the job belongs to a proposal owned by the current user.

#### `GET /api/v1/system/audit`

Returns the current user's bounded host-action proposal, confirmation, rejection, and execution audit events. Secrets, command text, and database contents are excluded.

## Current API behavior

- Authentication supports HttpOnly access/refresh cookies and explicit bearer access tokens.
- Cookie-authenticated mutations require CSRF validation.
- CORS allows `PATCH` in addition to existing methods.
- Database migrations are explicit; startup never mutates schema.
- Readiness verifies the current Alembic head `0006_v1_hardening` and the notes FTS5 table.
- Notifications are persistent in-app records only.
- No API endpoint accepts arbitrary shell commands, Docker arguments, filesystem paths, reboot/shutdown requests, package operations, or provider URLs from a client.
- Destructive or state-changing host operations require a durable proposal and explicit confirmation; the assistant follows the same route and cannot approve on the user's behalf.

## Planned API groups

- `GET /api/v1/conversations/{id}/stream`
- `GET /api/v1/jobs/{id}`
- `GET /api/v1/files/recent`
- `GET /api/v1/projects`
- `GET /api/v1/git/repositories`
- `GET /api/v1/docker/containers`
- `POST /api/v1/system/actions/{action}` (superseded by typed proposals and confirmation)

Every future write action requires authentication, authorization, typed input, confirmation when risky, idempotency where appropriate, and an audit event.
