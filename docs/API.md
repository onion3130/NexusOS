# NexusOS API

**Current milestone:** v1.3 — NVIDIA NIM provider support (v1.3.2 patch)
**Status:** Health, identity/session, read-only system, assistant conversations and task actions, notes/search/retrieval, optional embeddings, calendar, finance, media, confirmation-gated maintenance actions, verified SQLite backups, automated restore, retention cleanup, encryption key rotation, audit visibility, read-only workspace views, outbound email/push notification channels, and the out-of-process plugin boundary are implemented. Streaming remains planned.
**Base path:** `/api/v1`
**Last updated:** 2026-08-04

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

Returns bounded, ownership-scoped source-aware retrieval results. `mode=lexical` is the default; `mode=semantic` and `mode=hybrid` require `notes.semantic` and an explicitly configured embedding provider. If semantic retrieval is unavailable, the endpoint fails safe to lexical results. Responses include retrieval mode, lexical/semantic scores when available, source version, and provenance metadata.

#### `GET /api/v1/search/embeddings/status`

Returns aggregate semantic-index availability and counts for the authenticated user. It never returns vectors, note content, provider credentials, or upstream payloads.

### Notifications

#### `GET /api/v1/notifications`

Returns persistent in-app notifications and the unread count. Each item includes a bounded `channels` list describing outbound delivery state (`channel`, `status`, `delivered_at`, `error_code`). Supports `unread_only` and bounded `limit` filters.

#### `POST /api/v1/notifications/{id}/read`

Marks one owned notification as read.

#### `POST /api/v1/notifications/read-all`

Marks all current-user notifications as read.

#### `GET /api/v1/notifications/settings`

Returns redacted channel configuration: enabled flags, host/user/from/to fields, endpoint/topic, and boolean credential-presence markers. Requires the `notifications.settings` permission. Secret values are never returned.

#### `POST /api/v1/notifications/settings/test`

Sends one bounded test message through every enabled channel and returns per-channel `ok`/`error_code` results. Requires CSRF for cookies and the `notifications.settings` permission.

#### `POST /api/v1/notifications/{id}/resend`

Requeues outbound channel deliveries for one owned notification and returns the updated record. Requires CSRF and the `notifications.write` permission.

The dedicated worker converts due reminders into notifications using a deterministic reminder deduplication key, then enqueues one pending delivery row per enabled channel. A separate bounded worker cycle claims, delivers, retries (max three attempts), and audits each channel with processing leases. A channel disabled after enqueueing is skipped rather than sent. It runs separately from the API in Compose.

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

### Files, projects, Git, and Docker views

All workspace view routes require the `workspace_views.read` permission and expose metadata only. They never accept arbitrary paths or commands.

#### `GET /api/v1/files/recent`

Returns bounded recent file metadata from server-configured `WORKSPACE_ROOTS`. Sensitive credential filenames, symlinks, absolute host paths, and file contents are excluded.

#### `GET /api/v1/projects`

Returns project metadata discovered from safe marker files and direct-child Git roots beneath approved roots.

#### `GET /api/v1/git/repositories`

Returns branch, short commit, commit subject, clean/dirty state, and timestamps from fixed, bounded Git inspection commands. No Git mutation is available.

#### `GET /api/v1/docker/containers`

Returns sanitized container names, images, states, selected ports, creation times, and Compose service labels when an operator explicitly supplies a Docker Unix socket boundary. The default Compose stack does not mount the socket, so the response reports `docker_unavailable` by default.

### Calendar, finance, and media routes

The Calendar, Finance, and Media route groups are implemented under `/api/v1/calendar`, `/api/v1/finance`, and `/api/v1/media`; they enforce authentication, ownership, CSRF on browser mutations, permissions, bounded payloads, and idempotency. Calendar supports event/category CRUD and reminders. Finance supports account/transaction/category CRUD, period summaries, and strict all-or-nothing CSV imports using integer cents. Media supports bounded indexed-item listing, background rescan requests, and authenticated thumbnail/original streaming confined to configured `MEDIA_ROOTS`.

### Plugin routes

#### `GET /api/v1/plugins`

Lists registered non-deleted plugins, declared capabilities, status, version, bounded last error, and run count. Requires `plugins.read`.

#### `GET /api/v1/plugins/{name}` / `GET /api/v1/plugins/{name}/runs`

Returns one plugin or bounded newest run history. Requires `plugins.read`.

#### `POST /api/v1/plugins/{name}/invoke`

This endpoint is intentionally confirmation-gated and returns `requires_assistant_confirmation`; it never executes plugin code directly. All plugin capabilities, including read-labeled capabilities, run through the always-confirmed assistant `plugins.invoke` tool so a plugin’s self-declared risk label cannot bypass the host-action safety invariant. Plugin manifests and entrypoints are server-owned; the route never accepts a path or executable.

### Safe host-action and maintenance routes

#### `GET /api/v1/system/deployment`

Returns bounded authenticated operational metadata: whether encrypted replication is configured, whether production TLS is expected, and the current migration head. It never returns keys, paths, certificates, or provider details.

#### `GET /api/v1/system/actions`

Returns the server-owned allowlist of enabled maintenance actions. The catalog contains database backup/recovery actions plus confirmed plugin rescan, enable, disable, and uninstall lifecycle actions. It never exposes arbitrary executables, filesystem paths, Docker operations, reboot, shutdown, package management, or systemd controls.

#### `POST /api/v1/system/actions/proposals`

Creates a durable, expiring proposal without executing a host operation. The typed action key and action-specific input are validated server-side. Cookie-authenticated requests require CSRF, the `system.host_actions` permission, and an `Idempotency-Key`.

#### `GET /api/v1/system/actions/proposals` / `GET /api/v1/system/actions/proposals/{id}`

Lists or reads only the current user's proposals and their bounded lifecycle state.

#### `POST /api/v1/system/actions/proposals/{id}/confirm`

Explicitly confirms one unexpired proposal and queues one durable `host_action` worker job. Confirmation is required even when the request originated from the assistant.

#### `POST /api/v1/system/actions/proposals/{id}/reject`

Rejects a proposal without creating a job or invoking an executor.

#### `GET /api/v1/system/backups`

Lists non-pruned backup metadata owned by the current user. It returns relative NexusOS paths, size, SHA-256, status, integrity result, timestamps, the `restored_at` marker, and (after retention cleanup) the `pruned_at` marker; it never returns file contents or arbitrary paths.

#### `GET /api/v1/system/backups/retention-preview`

Read-only preview of what the configured retention policy (`BACKUP_RETENTION_COUNT` / `BACKUP_RETENTION_DAYS`) would prune. Returns the policy and bounded `to_prune` / `retained` backup lists. Requires `system.backups.read`; nothing is deleted by this endpoint.

#### `POST /api/v1/system/actions/proposals` with `maintenance.restore_backup`

Proposes restoring the live database from one owned, verified backup. The only accepted input is `{"backup_id": "<id>"}`. Confirmation queues a durable worker job that: creates a verified safety backup of the current database (rollback guarantee), stages the restore source (the local verified backup, or the decrypted off-host artifact when `BACKUP_REPLICATION_DESTINATION` and `BACKUP_REPLICATION_KEY` are configured), re-verifies SHA-256 and SQLite integrity before touching anything, records a restore marker and restore audit row inside the staged database, swaps it in atomically, and cleans stale WAL/SHM/journal sidecars. A successful restore requires an API/worker restart afterward; the proposal result and the Maintenance UI state this explicitly. The restored backup's `restored_at` is set through the restore itself (the pre-restore database is superseded).

#### `GET /api/v1/system/jobs/{id}`

Returns the status of a host-action job only when the job belongs to a proposal owned by the current user.

#### `GET /api/v1/system/audit`

Returns the current user's bounded host-action proposal, confirmation, rejection, and execution audit events. Secrets, command text, and database contents are excluded.

## Current API behavior

- Authentication supports HttpOnly access/refresh cookies and explicit bearer access tokens.
- Cookie-authenticated mutations require CSRF validation.
- CORS allows `PATCH` in addition to existing methods.
- Database migrations are explicit; startup never mutates schema.
- Readiness verifies the current Alembic head `0016_embeddings` and the notes FTS5 table.
- Notifications are persistent records; optional outbound email/push channels are server-configured and delivery is worker-side only.
- No API endpoint accepts arbitrary shell commands, Docker arguments, filesystem paths, reboot/shutdown requests, package operations, or provider URLs from a client.
- Destructive or state-changing host operations require a durable proposal and explicit confirmation; the assistant follows the same route and cannot approve on the user's behalf. Restore is the highest-risk action and additionally requires a verified source, a fresh safety backup, staged digest/integrity verification, and an atomic swap. Retention cleanup accepts no input and prunes only per the server policy with last-backup protection; key rotation accepts no input and uses only environment-configured keys.

## Planned API groups

- `GET /api/v1/conversations/{id}/stream`
- `GET /api/v1/jobs/{id}`
- `POST /api/v1/system/actions/{action}` (superseded by typed proposals and confirmation)

Every future write action requires authentication, authorization, typed input, confirmation when risky, idempotency where appropriate, and an audit event.
