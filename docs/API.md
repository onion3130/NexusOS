# NexusOS API

**Current milestone:** v1.7.0 — richer document parsing and source expansion (stable)
**Status:** Health, identity/session, read-only system, assistant conversations and task actions, bounded SSE streaming, notes/search/retrieval, optional embeddings, PDF/HTML/URL source ingestion, calendar, finance, media, confirmation-gated maintenance actions, verified SQLite backups, automated restore, retention cleanup, encryption key rotation, audit visibility, read-only workspace views, outbound email/push notification channels, and the out-of-process plugin boundary are implemented.
**Base path:** `/api/v1`
**Last updated:** 2026-08-06

All browser-authenticated mutations require the readable CSRF cookie value in the `X-CSRF-Token` header. Bearer-authenticated clients may use the same routes without cookie CSRF. Mutation routes accept an `Idempotency-Key`; clients must reuse the key when retrying the same operation. Reusing a key with a different payload returns `422` on standard resource mutations; the streaming Assistant route rejects that conflict with `409`. All feature resources are user-owned and unauthorized resources return `404`.

## Implemented API

### Health, identity, system, and assistant

#### `GET /api/v1/system/assistant/provider`

Returns the authenticated user's configured assistant provider state, label, model identifier, and safe setup guidance. It requires `assistant.task_actions` and never returns provider URLs, API keys, or environment values.

#### `GET /api/v1/system/admin/status`

Returns redacted owner-only status cards for system readiness, the configured chat AI provider, optional embedding provider, SQLite storage, application version, migration head, and whether NVIDIA NIM is configured by the browser, environment, or not at all. A configured provider means validated server settings are present; the endpoint does not claim that a remote service is healthy unless a separate test was run. It requires `admin.manage_users` and never returns credentials, provider URLs, database URLs, filesystem paths, or environment values.

#### `GET /api/v1/system/admin/nvidia-nim/options`

Owner-only offline fallback model presets and beginner setup guidance for hosted NVIDIA NIM. Returns OpenAI-compatible base URL metadata and recommended chat/embedding model choices without contacting NVIDIA or exposing secrets.

#### `POST /api/v1/system/admin/nvidia-nim/models`

Owner-only, CSRF-protected live model catalog. Accepts optional `{ "api_key" }` or reuses a saved browser-managed/environment key. Calls the fixed hosted OpenAI-compatible endpoint `GET https://integrate.api.nvidia.com/v1/models` with SSRF-safe transport and returns chat/embedding model lists without echoing the key.

#### `POST /api/v1/system/admin/nvidia-nim/test`

Owner-only, CSRF-protected connection test. Accepts optional `{ "api_key", "model" }` or reuses a saved browser-managed key. Sends one bounded hosted chat request and returns only `{ ok, detail, model, embeddings_tested }`. The key is never returned.

#### `POST /api/v1/system/admin/nvidia-nim`

Owner-only, CSRF-protected setup endpoint. Accepts `{ "api_key?", "model", "embeddings_enabled", "embedding_model?" }`, encrypts the key into the server data volume, reloads the API settings cache, marks the configuration active, and returns redacted status only. On later updates, `api_key` may be omitted to keep the previously saved key. It does not store the key in SQLite or expose it in the response. The worker reloads browser-managed NIM settings each cycle, so SSH restarts are not required.

#### `DELETE /api/v1/system/admin/nvidia-nim`

Owner-only, CSRF-protected endpoint that removes browser-managed NIM configuration and returns redacted status. Environment-provided NIM configuration is not modified.

#### `GET /api/v1/system/admin/update`

Owner-only software-update status for the host agent handshake. Returns redacted state (`idle`, `queued`, `running`, `succeeded`, `failed`, `agent_missing`), optional commit SHAs, a short log tail, and whether a new request is allowed. It never returns host paths or shell output secrets.

#### `POST /api/v1/system/admin/update`

Owner-only, CSRF-protected queue endpoint. Accepts `{ "action": "check" | "apply", "confirm": true }` (`confirm` is required for `apply`). Writes a request file for the host update agent and returns status. The API process does not execute git or Docker commands.

The existing health, identity, system, and conversation routes remain as documented in the previous milestone. The assistant gateway is server-configured, provider credentials remain server-side, and `AI_PROVIDER=disabled` remains safe. Preferred beginner setup is the Admin workspace; environment variables remain supported for operators. When NIM is enabled, the Assistant uses NVIDIA's OpenAI-compatible chat endpoint. Grounded responses can retrieve owned notes through bounded lexical, semantic, or hybrid retrieval when the request enables grounding and the authenticated user has the required note permissions. Retrieved material is untrusted context and responses expose server-derived source provenance.

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

#### `GET /api/v1/conversations/{conversation_id}/messages/{message_id}/sources`

Returns bounded, server-derived source provenance for one owned assistant message. The endpoint returns note source and chunk identifiers, title, version, retrieval mode, rank, and bounded scores; it never returns arbitrary note content or provider payloads. Conversation and message ownership are enforced.

#### `GET /api/v1/notes/{id}/chunks`

Returns current-version deterministic retrieval chunks for one owned note.

#### `GET /api/v1/search/retrieve`

Returns bounded, ownership-scoped source-aware retrieval results. `mode=lexical` is the default; `mode=semantic` and `mode=hybrid` require `notes.semantic` and an explicitly configured embedding provider. If semantic retrieval is unavailable, the endpoint fails safe to lexical results. Responses include retrieval mode, lexical/semantic scores when available, source version, and provenance metadata.

#### `GET /api/v1/search/embeddings/status`

Returns aggregate semantic-index availability and counts for the authenticated user. It never returns vectors, note content, provider credentials, or upstream payloads.

### External sources

#### `GET /api/v1/sources`

Lists owned external sources. `status_filter=active|archived|all` and bounded pagination are supported.

#### `POST /api/v1/sources/upload`

Uploads one bounded `.txt`, `.md`, `.markdown`, or `.pdf` source (≤ 10 MB). The browser sends the file bytes with `X-Source-Filename`; the server validates the extension, size, and (for text) UTF-8 content, stores it under a generated name beneath `DATA_DIR/sources`, and queues worker ingestion. PDFs are parsed only in the worker with a page cap and text bound; encrypted, malformed, or oversized documents are rejected with stable error codes. Arbitrary binary files are rejected.

#### `POST /api/v1/sources/url`

Creates an inert URL source from `{ "url", "title?" }` and queues a worker `source_fetch` job. The endpoint validates the scheme and target at request time for fast feedback; the actual fetch runs only in the worker through a pinned-address, DNS-rebinding-resistant transport with bounded redirects, timeout, size, and a content-type allowlist (HTML, Markdown, text, PDF). Private, loopback, link-local, multicast, reserved, metadata, and credential-bearing targets are rejected; every redirect hop is re-validated. Fetched bytes are stored under a server-generated name and processed by the existing ingestion pipeline. Responses include `source_url` for URL sources.

#### `GET /api/v1/sources/approved-files`

Lists bounded text files discovered beneath server-configured `WORKSPACE_ROOTS`. Responses contain opaque file IDs, not absolute paths.

#### `POST /api/v1/sources/import-approved-file`

Imports one approved file by opaque `file_id`. The server rescans and revalidates root confinement, symlink state, size, hash, and UTF-8 content before copying it into private source storage.

#### `GET /api/v1/sources/{id}` / `GET /api/v1/sources/{id}/versions` / `GET /api/v1/sources/{id}/chunks`

Return owned source metadata, immutable ingestion versions, or current-version bounded chunks.

#### `POST /api/v1/sources/{id}/reindex`

Queues a bounded source re-ingestion job.

#### `GET /api/v1/sources/{id}/sync`

Returns redacted synchronization status for an approved-file source. The response contains only enabled state, bounded interval, timestamps, next check time, and a safe error code; it never returns paths or file content.

#### `POST /api/v1/sources/{id}/sync`

Enables or updates approved-root synchronization. Accepts `{ "enabled": true, "interval_seconds": 3600 }`; intervals are limited to 15 minutes through 24 hours. The server revalidates the existing opaque approved-file reference.

#### `DELETE /api/v1/sources/{id}/sync`

Disables synchronization while retaining bounded status metadata.

#### `POST /api/v1/sources/{id}/sync-now`

Queues one worker-side synchronization check and returns a bounded job status. File reading and ingestion never occur in the request process.

#### `POST /api/v1/sources/{id}/archive` / `POST /api/v1/sources/{id}/restore` / `DELETE /api/v1/sources/{id}`

Perform owned source lifecycle transitions. Delete is soft deletion and never accepts a path.

The dedicated worker processes at most a small bounded source batch, verifies the stored SHA-256, parses text, Markdown, PDF, or normalized HTML into bounded text, creates a version and deterministic chunks, and records success/failure audit events. URL sources are fetched first by the worker-only `source_fetch` cycle and then enter the same ingestion pipeline.

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

### Grounded assistant responses

#### `POST /api/v1/conversations/{conversation_id}/messages`

Accepts `content` plus optional bounded `grounding` controls (`enabled`, `mode=lexical|semantic|hybrid`, and `limit`). Grounding requires `notes.read`; semantic and hybrid retrieval additionally require `notes.semantic`. Retrieved note material is explicitly delimited as untrusted reference context, and the response persists server-derived source provenance. Grounding is skipped when `AI_PROVIDER=disabled`. This buffered endpoint remains the path for tool-intent requests and confirmation-gated actions.

#### `POST /api/v1/conversations/{conversation_id}/messages/stream`

Requires an `Idempotency-Key` header. Returns authenticated, ownership-scoped Server-Sent Events for ordinary text-only assistant prompts. Events include a persisted user-message `meta` event, bounded `delta` text events, a final `done` event with the persisted assistant message, model-run metadata, and source provenance, followed by a `close` event. The route requires CSRF for cookie-authenticated browser mutations, never exposes provider credentials, never attaches tools, and preserves the buffered endpoint for local lookups and mutating actions. Provider-disabled or upstream failures are emitted as a bounded `error` event. Browser clients send an `Idempotency-Key`; an identical completed retry is replayed without duplicating messages, while a different payload with the same key is rejected.

#### `GET /api/v1/conversations/{conversation_id}/messages/{message_id}/sources`

Returns bounded source provenance for one owned assistant message, including note/chunk identifiers, title, source version, retrieval mode, rank, and bounded scores. It never returns arbitrary provider payloads or bypasses note ownership.

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
- Readiness verifies the current Alembic head `0020_source_expansion` and the notes FTS5 table.
- Notifications are persistent records; optional outbound email/push channels are server-configured and delivery is worker-side only.
- No API endpoint accepts arbitrary shell commands, Docker arguments, filesystem paths, reboot/shutdown requests, package operations, or provider URLs from a client.
- Destructive or state-changing host operations require a durable proposal and explicit confirmation; the assistant follows the same route and cannot approve on the user's behalf. Restore is the highest-risk action and additionally requires a verified source, a fresh safety backup, staged digest/integrity verification, and an atomic swap. Retention cleanup accepts no input and prunes only per the server policy with last-backup protection; key rotation accepts no input and uses only environment-configured keys.

## Planned API groups

- `GET /api/v1/jobs/{id}`
- `POST /api/v1/system/actions/{action}` (superseded by typed proposals and confirmation)

Every future write action requires authentication, authorization, typed input, confirmation when risky, idempotency where appropriate, and an audit event.
