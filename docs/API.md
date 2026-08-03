# NexusOS API

**Current milestone:** Milestone 6 — tasks, reminders, and notifications
**Status:** Health, identity/session, read-only system, assistant conversations, task management, reminders, notifications, and assistant approval routes are implemented. Notes, files, host actions, and streaming remain planned.
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

### Notifications

#### `GET /api/v1/notifications`

Returns persistent in-app notifications and the unread count. Supports `unread_only` and bounded `limit` filters.

#### `POST /api/v1/notifications/{id}/read`

Marks one owned notification as read.

#### `POST /api/v1/notifications/read-all`

Marks all current-user notifications as read.

The dedicated worker converts due reminders into notifications using a deterministic reminder deduplication key. It runs separately from the API in Compose.

### Assistant task actions

The assistant registry supports the following task tools:

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

## Current API behavior

- Authentication supports HttpOnly access/refresh cookies and explicit bearer access tokens.
- Cookie-authenticated mutations require CSRF validation.
- CORS allows `PATCH` in addition to existing methods.
- Database migrations are explicit; startup never mutates schema.
- Readiness verifies the current Alembic head `0003_tasks_notifications`.
- Notifications are persistent in-app records only.
- No API endpoint accepts arbitrary shell commands, Docker arguments, filesystem paths, or provider URLs from a client.

## Planned API groups

- `GET /api/v1/conversations/{id}/stream`
- `GET /api/v1/jobs/{id}`
- `GET/POST /api/v1/notes`
- `GET /api/v1/files/recent`
- `GET /api/v1/projects`
- `GET /api/v1/git/repositories`
- `GET /api/v1/docker/containers`
- `POST /api/v1/system/actions/{action}`

Every future write action requires authentication, authorization, typed input, confirmation when risky, idempotency where appropriate, and an audit event.
