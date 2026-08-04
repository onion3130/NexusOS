# Environment contract

`.env.example` is the public, placeholder-only contract. `.env` is local-only and ignored by Git. The API and worker read process environment variables only.

| Variable | Required | Example/template | Secret | Purpose |
|---|---:|---|---:|---|
| `NEXUS_ENV` | yes | `development` | no | Runtime environment |
| `TZ` | yes | `UTC` | no | Process timezone |
| `DATA_DIR` | yes | `./data` | no | Persistent data root |
| `DB_TYPE` | yes | `sqlite` | no | SQLite persistence policy |
| `DATABASE_URL` | yes | `sqlite:////var/lib/nexus/data/nexus.db` | no | SQLite database URL |
| `JWT_SECRET` | yes | placeholder only | yes | JWT signing material |
| `SESSION_COOKIE_SECURE` | yes | `false` | no | Must be true in production |
| `CORS_ORIGINS` | optional | local origins | no | Credential-safe browser origins |
| `AI_PROVIDER` | yes | `disabled` | no | Server-side provider policy (`nvidia_nim` enables NVIDIA NIM defaults) |
| `AI_BASE_URL` | optional | empty | no | Approved public provider endpoint; hosted NIM defaults to `https://integrate.api.nvidia.com/v1/chat/completions` |
| `AI_API_KEY` | conditional | placeholder only | yes | Provider credential; NIM may use `NVIDIA_API_KEY` |
| `AI_MODEL` | optional | placeholder only | no | Provider model identifier, required when AI is enabled |
| `AI_TIMEOUT_SECONDS` | optional | `20` | no | Bounded provider timeout |
| `AI_MAX_CONTEXT_MESSAGES` | optional | `20` | no | Context bound |
| `AI_MAX_OUTPUT_TOKENS` | optional | `512` | no | Output bound |
| `AI_MAX_RESPONSE_BYTES` | optional | `1048576` | no | Response memory bound |
| `EMBEDDING_PROVIDER` | optional | `disabled` | no | Optional semantic retrieval provider (`nvidia_nim` enables the hosted NIM default) |
| `EMBEDDING_BASE_URL` | optional | empty | no | Explicit public HTTP(S) embeddings endpoint; hosted NIM defaults to `https://integrate.api.nvidia.com/v1/embeddings` |
| `EMBEDDING_API_KEY` | optional | empty | yes | Server-side embeddings credential; NIM uses `NVIDIA_API_KEY` |
| `EMBEDDING_MODEL` | optional | empty | no | Provider embedding model, required when embeddings are enabled |
| `EMBEDDING_TIMEOUT_SECONDS` | optional | `30` | no | Embedding call timeout, 1–120 seconds |
| `EMBEDDING_BATCH_SIZE` | optional | `8` | no | Bounded embedding worker batch, 1–32 |
| `EMBEDDING_MAX_CHUNK_LENGTH` | optional | `4000` | no | Maximum text sent per embedding request |
| `TASK_WORKER_INTERVAL_SECONDS` | optional | `30` | no | Worker polling interval, 5–3600 |
| `TASK_WORKER_BATCH_SIZE` | optional | `50` | no | Reminder batch size, 1–200 |
| `WORKSPACE_ROOTS` | optional | empty | no | Approved absolute roots or paths relative to `DATA_DIR` for read-only Files, Projects, and Git views |
| `DOCKER_SOCKET_PATH` | optional | empty | no | Optional Docker Unix socket path; disabled unless explicitly configured and mounted |
| `MEDIA_ROOTS` | optional | empty | no | Approved media roots for the derived index |
| `MEDIA_THUMBNAIL_MAX_DIMENSION` | optional | `320` | no | Thumbnail bound, 64–1024 pixels |
| `MEDIA_INDEX_MAX_SIZE_MB` | optional | `200` | no | Largest indexed file, 1–1024 MB |
| `PLUGINS_DIR` | optional | empty | no | Absolute operator-owned plugin directory; empty disables discovery |
| `PLUGIN_INVOKE_TIMEOUT_SECONDS` | optional | `20` | no | Plugin subprocess wall-time bound, 1–120 seconds |
| `BACKUP_REPLICATION_HOST_PATH` | optional | empty | no | Hardened Compose host path mounted as the replication destination |
| `BACKUP_REPLICATION_DESTINATION` | optional | empty | no | Absolute runtime destination for encrypted backup artifacts; hardened Compose sets `/var/lib/nexus/replication` |
| `BACKUP_ENCRYPTION_KEY` | conditional | empty | yes | 64-character hexadecimal AES-256 key; required with replication destination |
| `BACKUP_RETENTION_COUNT` | optional | `7` | no | Newest verified backups always retained, 1–100 |
| `BACKUP_RETENTION_DAYS` | optional | `30` | no | Retention window in days, 1–3650 |
| `BACKUP_REPLICATION_KEY_PREVIOUS` | optional | empty | yes | Previous AES-256 key for the confirmed rotation action; must differ from the current key and is removed after rotation |
| `NOTIFICATION_EMAIL_ENABLED` | optional | `false` | no | Enable the outbound SMTP email channel |
| `NOTIFICATION_EMAIL_SMTP_HOST` | conditional | empty | no | SMTP relay host; required when email is enabled |
| `NOTIFICATION_EMAIL_SMTP_PORT` | conditional | `587` | no | SMTP port, 1–65535 |
| `NOTIFICATION_EMAIL_SMTP_USER` | optional | empty | no | SMTP user; must be paired with the password |
| `NOTIFICATION_EMAIL_SMTP_PASSWORD` | optional | empty | yes | SMTP password; never returned or logged |
| `NOTIFICATION_EMAIL_FROM` | conditional | empty | no | Sender address; required when email is enabled |
| `NOTIFICATION_EMAIL_TO` | conditional | empty | no | Recipient address; required when email is enabled |
| `NOTIFICATION_EMAIL_USE_TLS` | optional | `true` | no | Use STARTTLS for the SMTP session |
| `NOTIFICATION_PUSH_ENABLED` | optional | `false` | no | Enable the outbound ntfy-compatible push channel |
| `NOTIFICATION_PUSH_URL` | conditional | empty | no | Absolute HTTP(S) push base URL; required when push is enabled |
| `NOTIFICATION_PUSH_TOPIC` | conditional | empty | no | ntfy-safe topic name; required when push is enabled |
| `NOTIFICATION_PUSH_TOKEN` | optional | empty | yes | Push bearer token; never returned or logged |
| `NOTIFICATION_DELIVERY_BATCH_SIZE` | optional | `20` | no | Outbound delivery batch size, 1–100 |

Milestone 10 adds optional encrypted backup replication through the bounded worker. Replication activates only when both `BACKUP_REPLICATION_DESTINATION` and `BACKUP_ENCRYPTION_KEY` are configured; the destination must be outside `DATA_DIR`. In the hardened Compose profile, set `BACKUP_REPLICATION_HOST_PATH` to a host-mounted off-host/NFS destination and let the overlay provide the container destination. The key is never returned or logged. The v1.0 release uses the existing bounded worker and SQLite data volume for fixed backup/integrity actions. Milestones 9 and 10 add optional workspace-view and encrypted-replication settings. Docker inspection is disabled when `DOCKER_SOCKET_PATH` is empty. Neither workspace setting grants browser access or introduces a new secret, but a Docker socket remains a powerful host-control boundary. Backups are stored beneath `DATA_DIR/backups`; configure the Milestone 10 destination and key pair for encrypted off-host replication.

Milestone 13 adds backup retention and key rotation. Retention cleanup (a confirmed Maintenance action) keeps the newest `BACKUP_RETENTION_COUNT` verified backups and everything younger than `BACKUP_RETENTION_DAYS`; the newest verified backup is always retained and pruning is digest-checked and audited. Key rotation re-encrypts every replicated artifact from `BACKUP_REPLICATION_KEY_PREVIOUS` to the current `BACKUP_ENCRYPTION_KEY`; the previous key must differ from the current key, is never returned or logged, and should be removed from the environment after the rotation completes.

Milestone 11 adds Calendar, Finance, Media, and the optional out-of-process plugin boundary. `MEDIA_ROOTS` is a comma-separated approved-root contract; the media indexer creates rebuildable metadata and Pillow thumbnails without accepting request paths. `PLUGINS_DIR` must be an absolute operator-owned directory. Compose mounts it read-only at `/var/lib/nexus/plugins` into API and worker, and plugin subprocesses receive no application secrets. Plugin lifecycle changes require confirmation; direct HTTP invocation is read-risk only, while write/dangerous capabilities are assistant-confirmed. Plugins are trusted operator-installed code rather than a hostile-code sandbox. Milestone 11 also adds optional outbound notification channels. Email activates only when `NOTIFICATION_EMAIL_ENABLED=true` with `NOTIFICATION_EMAIL_SMTP_HOST`, `NOTIFICATION_EMAIL_FROM`, and `NOTIFICATION_EMAIL_TO` configured; the SMTP user and password must be configured together. Push activates only when `NOTIFICATION_PUSH_ENABLED=true` with an absolute `NOTIFICATION_PUSH_URL` and ntfy-safe `NOTIFICATION_PUSH_TOPIC`. Push URLs must not embed credentials or target loopback, link-local, multicast, reserved, or metadata hosts; private LAN addresses are allowed for self-hosted ntfy servers. Passwords and tokens are never returned or logged. The dedicated worker delivers reminders through every enabled channel with bounded batches, leases, and a three-attempt retry limit.

## Rules

- Never log environment values or return them from the API.
- Production rejects placeholder/short JWT secrets and insecure cookies.
- Provider keys are required only when AI is enabled.
- Worker settings are bounded to preserve Raspberry Pi resource use.
- External source uploads are stored beneath `DATA_DIR/sources`; source ingestion is bounded by the worker and does not require a separate search service.
- Future integration credentials use Docker secrets or an approved encrypted credential boundary, not ordinary settings rows. The owner admin panel can configure hosted NVIDIA NIM through the authenticated same-origin API: the key is encrypted into `DATA_DIR/runtime/nvidia-nim.enc` using the server JWT secret, never stored in SQLite, browser storage, logs, or API responses. Browser-managed setup takes precedence over environment defaults until disabled; restart the API and worker after changes.
- Channel credentials are required only when the corresponding channel is enabled.
