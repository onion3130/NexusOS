# NexusOS database

**Current milestone:** v1.4 — grounded assistant notes (unreleased)
**Current status:** Identity, assistant, task, notes, lexical search/retrieval, optional embeddings, calendar, finance, media, plugin registry/run history, host-action proposals, backup metadata, restore markers, retention pruning markers, workspace permissions, encrypted replication metadata, and outbound notification channel deliveries are implemented through Alembic revisions `0001_identity` through `0017_assistant_grounding`.
**Last updated:** 2026-08-04

## Current database state

The API uses SQLAlchemy 2.x with SQLite on the Raspberry Pi. SQLite foreign keys, WAL mode, a bounded busy timeout, and composite worker-claim indexes are configured for the v1.0 workload. Startup does not run migrations automatically. Run Alembic or the owner-bootstrap command explicitly.

## Implemented persistence boundary

- `apps/api/app/db/base.py` defines the declarative base and UTC timestamp helper.
- `apps/api/app/db/models.py` defines identity, assistant, task, reminder, notification, job, and audit models.
- `apps/api/app/db/session.py` creates the engine/session boundary and checks the current migration head.
- `0001_identity` creates identity and audit tables.
- `0002_assistant` creates conversations, messages, model runs, and tool calls.
- `0003_tasks_notifications` creates categories, tags, task series, tasks, task tags, reminders, notifications, jobs, and approval lifecycle columns, including recoverable assistant-processing leases.
- `0005_host_actions` creates expiring host-action proposals and verified backup metadata, and seeds owner permissions for host actions, backups, and audit history.
- `0006_v1_hardening` adds composite claim indexes for bounded reminder and host-action worker queries.
- `0007_workspace_views` seeds the dedicated `workspace_views.read` permission; workspace host metadata itself is not persisted.
- `0008_deployment_hardening` adds encryption and replication metadata to `backup_records`; encrypted artifacts themselves remain outside the application database.
- `0009_notification_channels` creates `notification_channel_deliveries` and seeds the `notifications.settings` owner permission.
- `0010_restore` adds `backup_records.restored_at` to track the most recent restore of a verified backup artifact.
- `0011_backup_lifecycle` adds `backup_records.pruned_at` so retention cleanup can soft-delete records (status `deleted`) while preserving audit history.
- `0012_calendar` adds calendar categories, events, reminders, and calendar permissions.
- `0013_finance` adds integer-cent finance accounts, categories, transactions, and finance permissions.
- `0014_media` adds the derived media index and media permissions; thumbnails remain rebuildable files beneath `DATA_DIR`.
- `0015_plugins` adds registered plugin manifests, bounded run history, and plugin permissions. Plugin code and artifacts remain outside the database.
- `0016_embeddings` adds optional provider-scoped serialized vectors for versioned note chunks and the `notes.semantic` permission. Vectors are private derived data and can be rebuilt from canonical chunks.
- `0017_assistant_grounding` adds user-scoped, server-derived `assistant_source_references` for bounded provenance attached to grounded assistant messages. The table stores source identifiers and retrieval metadata, not provider payloads or unrestricted note content.

## Milestone 7 tables

| Entity | Owner | Purpose |
|---|---|---|
| `notes` | user | Canonical user-authored note sources |
| `note_tags` | note/tag ownership | Reuses Milestone 6 user-owned tags |
| `note_search_documents` | derived note | Rebuildable title/content/tag search projection |
| `notes_fts` | derived SQLite FTS5 | Bounded lexical search index |
| `note_chunks` | user/note | Versioned source-aware retrieval chunks |

`notes` is authoritative. Search projections, chunks, and embeddings are derived and can be rebuilt. FTS5 remains available as the lexical fallback; serialized vectors are bounded and provider-scoped.

## Milestone 6 tables

| Entity | Owner | Purpose |
|---|---|---|
| `task_categories` | user | User-owned categories |
| `tags` | user | User-owned tags |
| `task_series` | user | Constrained recurring-task definitions |
| `tasks` | user | Task occurrences and completion history |
| `task_tags` | task/tag ownership | Task/tag many-to-many relation |
| `reminders` | user/task | Scheduled reminder state and worker leases |
| `notifications` | user | Persistent notification records |
| `notification_channel_deliveries` | notification | One pending/delivered/failed row per enabled outbound channel with leases and retry metadata |
| `jobs` | system | Durable worker job metadata for future expansion |

Task deletion is soft deletion through `deleted_at`. Recurring completion creates one future occurrence while retaining the completed occurrence. Reminder delivery is idempotent through a unique `notifications.dedupe_key`.

## Milestone 8 tables

| Entity | Owner | Purpose |
|---|---|---|
| `host_action_proposals` | user | Expiring typed proposals, confirmation state, and linked worker job |
| `backup_records` | user/system | Relative path, size, hash, integrity, verification, encryption/replication, restore, and retention/prune metadata for NexusOS-created backups |

The live SQLite database and backup files remain the authoritative storage artifacts. A proposal is not execution: only confirmation queues a worker job. Backups are created beneath the configured data directory's fixed `backups/` child; client input cannot select paths.

## Recurrence

The API accepts version-one structured recurrence JSON supporting daily, weekly, and monthly schedules with bounded intervals. It does not accept arbitrary RRULE strings. All persisted instants are UTC; recurrence configuration retains a timezone label for future calculations.

## Migration rules

Every schema change must include:

1. An Alembic upgrade and downgrade revision.
2. Fresh-database upgrade coverage.
3. Downgrade and re-upgrade coverage.
4. Repository/service tests for ownership and invalid states.
5. SQLite validation and PostgreSQL validation when compatibility is claimed.
6. A backup and recovery note for data transformations.

Back up before production migrations. The task migration is reversible, but production data still requires a tested backup and restore procedure.

## Security and ownership

Every user-owned table includes a user boundary directly or through an owned parent. Services and routes filter by the authenticated user; frontend visibility is never used as authorization. Secrets, tokens, and provider payloads are not persisted.

## Notes and retrieval

Note content changes increment `content_version`. Current chunks retain the source note ID, version, offsets, content hash, and chunk index. Search results are joined back to canonical notes with user ownership and deletion filters. Search input is normalized into a safe parameterized FTS5 query; raw FTS syntax is not exposed.

Milestone 9 intentionally adds no host metadata tables. Files, projects, Git, and Docker views are live read-only adapter results; only the `workspace_views.read` permission is migration-backed.

Milestone 11 delivery rows are derived from owned notifications and deduplicated by `(notification_id, channel)`. Delivery status is bounded (`pending`, `processing`, `delivered`, `failed`, `skipped`, `cancelled`); channel credentials are never persisted.

## Plugin tables

| Entity | Owner | Purpose |
|---|---|---|
| `plugins` | operator/user metadata | Approved manifest, entrypoint, capability JSON, lifecycle status, and last bounded error |
| `plugin_runs` | plugin | Bounded invocation status, method, duration, and error code |

Plugin arguments, subprocess output, credentials, and executable code are not persisted. Run history is pruned transactionally to the newest bounded entries per plugin.

## Remaining database work

- PostgreSQL compatibility remains a tested future claim, not an assumption.
- Backup-before-migration orchestration and notification retention cleanup remain deployment work.
- Permanent task and backup-record deletion remain future policy work.
