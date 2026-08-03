# NexusOS security baseline

**Status:** Milestone 7 notes, search, retrieval, task, reminder, notification, and assistant-action controls implemented; semantic AI and deployment hardening remain deferred.
**Last updated:** 2026-08-03

## Runtime boundaries

- The browser never receives provider keys, database credentials, Docker socket access, or unrestricted host paths.
- The API is the authorization boundary; frontend visibility is not authorization.
- Task and note services filter every owned entity by the authenticated user.
- FTS5 results are joined back to canonical notes with user and deletion filters; derived chunks carry a direct user boundary.
- The worker has no browser-facing port and performs only bounded database-backed reminder delivery.
- No arbitrary shell text, SQL, Docker arguments, filesystem paths, or provider URLs are accepted from model output or the browser.

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
- Encrypted backups, restore drills, TLS, systemd, resource limits, monitoring, and image pinning remain deployment work.

## Change checklist

Before merging a feature:

1. Identify new secrets/configuration and add placeholders only to `.env.example`.
2. Confirm no credential-shaped literals or personal data are present.
3. Confirm authentication, ownership, CSRF, permissions, and audit requirements.
4. Define timeout, retry, lease, deduplication, and redaction behavior.
5. Run backend tests, frontend typecheck/build, Compose validation, secret scanning, and `git diff --check`.
6. Review the complete diff and staged file list.
