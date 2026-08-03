# NexusOS security baseline

**Status:** v1.0 application security controls implemented for safe host actions, backups, audit, notes, search, retrieval, tasks, reminders, notifications, and assistant actions; public-internet deployment hardening remains deferred.
**Last updated:** 2026-08-03

## Runtime boundaries

- The browser never receives provider keys, database credentials, Docker socket access, or unrestricted host paths.
- The API is the authorization boundary; frontend visibility is not authorization.
- Task and note services filter every owned entity by the authenticated user.
- FTS5 results are joined back to canonical notes with user and deletion filters; derived chunks carry a direct user boundary.
- The worker has no browser-facing port and performs only bounded database-backed reminder delivery.
- No arbitrary shell text, SQL, Docker arguments, filesystem paths, reboot/shutdown requests, package operations, systemd controls, or provider URLs are accepted from model output or the browser.
- Host-action execution uses fixed Python/SQLite adapters, not subprocesses. If future subprocess actions are proposed, they require a separate privileged-broker design, absolute executable paths, `shell=False`, fixed argument allowlists, and independent review.

## Notes, search, and retrieval controls

- Notes require `notes.read` for reads/search, `notes.write` for create/update/archive/restore, and `notes.delete` for soft deletion.
- Note mutations require CSRF for cookie-authenticated clients, payload-bound idempotency, ownership checks, and audit events.
- Search queries are bounded, parameterized, and normalized; raw FTS5 syntax is not exposed.
- Note content is rendered as text and is never trusted HTML.
- Retrieved note content is untrusted source material and cannot change system instructions, permissions, or tool authorization.

## Task and assistant mutation controls

- Task, category, tag, reminder, and notification mutations require authentication.
- Cookie-authenticated mutations require CSRF headers.
- Task routes require action-specific permissions.
- Assistant task writes require `assistant.task_actions` plus task permissions.
- Assistant proposals expire after a bounded period and require explicit approval.
- Rejection never invokes the task service.
- Task deletion is soft deletion and is audited.
- All task changes, reminder changes, notification state changes, and assistant approvals/rejections create bounded audit events.

## Host-action and recovery controls

- `system.host_actions`, `system.backups.read`, and `system.audit.read` are enforced server-side.
- Proposal creation never executes an operation. Every enabled action requires explicit confirmation, even when proposed by the assistant.
- Proposals expire after ten minutes, are user-scoped, and use idempotency keys to prevent duplicate queues.
- Worker jobs are durable, bounded, claimable, and audited at proposal, confirmation, rejection, success, and failure transitions.
- Backup files are created only beneath `DATA_DIR/backups`; clients cannot supply a path or filename.
- Backup metadata includes a SHA-256 digest and SQLite `integrity_check` result. Backup contents are never returned by the API.
- Restore through the API/assistant, backup deletion, retention cleanup, encrypted replication, and off-host upload are not enabled.
- The worker remains non-root with no published port, no Docker socket, and no privileged host mount.

## Input and data safety

- Titles, descriptions, tags, categories, reminders, notification bodies, list limits, and recurrence structures are bounded.
- Persisted timestamps must include timezone offsets and are normalized to UTC.
- Recurrence supports only the version-one daily, weekly, and monthly structure; arbitrary RRULE text is not accepted.
- Notifications use deterministic deduplication keys to prevent worker restart duplicates.
- Search projections and retrieval chunks are derived from canonical notes and are rebuildable rather than authoritative.
- Task and notification content is rendered as text, not trusted HTML.
- Secrets, tokens, provider keys, raw authorization headers, and raw upstream payloads are never persisted in task records or ordinary logs.

## Authentication and deployment

- Passwords use Argon2id.
- Sessions are tracked, rotated, revocable, and protected by CSRF for cookies.
- Production cookies must be Secure and HttpOnly.
- The worker and API run as non-root ARM64 containers on a private network.
- Ports remain loopback-only in the development topology.
- The external SSD is primary storage, not the only backup.

## Remaining hardening

- Idempotency keys cover task, reminder, category, tag, notification, and assistant approval mutations; callers must reuse the same key when retrying a request, and payload mismatches are rejected.
- Standard error envelopes and request IDs remain future hardening.
- Automated restore, encrypted/off-host backup replication, retention cleanup, backup-before-migration orchestration, TLS, systemd, resource limits, monitoring, and image pinning remain deployment work.

## Change checklist

Before merging a feature:

1. Identify new secrets/configuration and add placeholders only to `.env.example`.
2. Confirm no credential-shaped literals or personal data are present.
3. Confirm authentication, ownership, CSRF, permissions, and audit requirements.
4. Define timeout, retry, lease, deduplication, and redaction behavior.
5. Run backend tests, frontend typecheck/build, Compose validation, secret scanning, and `git diff --check`.
6. Review the complete diff and staged file list.
