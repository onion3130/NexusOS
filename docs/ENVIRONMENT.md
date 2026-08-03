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
| `AI_PROVIDER` | yes | `disabled` | no | Server-side provider policy |
| `AI_BASE_URL` | optional | empty | no | Approved provider endpoint |
| `AI_API_KEY` | conditional | placeholder only | yes | Provider credential |
| `AI_MODEL` | optional | placeholder only | no | Provider model identifier |
| `AI_TIMEOUT_SECONDS` | optional | `20` | no | Bounded provider timeout |
| `AI_MAX_CONTEXT_MESSAGES` | optional | `20` | no | Context bound |
| `AI_MAX_OUTPUT_TOKENS` | optional | `512` | no | Output bound |
| `AI_MAX_RESPONSE_BYTES` | optional | `1048576` | no | Response memory bound |
| `TASK_WORKER_INTERVAL_SECONDS` | optional | `30` | no | Worker polling interval, 5–3600 |
| `TASK_WORKER_BATCH_SIZE` | optional | `50` | no | Reminder batch size, 1–200 |

The v1.0 release uses the existing bounded worker and SQLite data volume for fixed backup/integrity actions; no new service, secret, or environment variable is required. Backups are stored beneath `DATA_DIR/backups` and must still be replicated off-host for production recovery.

## Rules

- Never log environment values or return them from the API.
- Production rejects placeholder/short JWT secrets and insecure cookies.
- Provider keys are required only when AI is enabled.
- Worker settings are bounded to preserve Raspberry Pi resource use.
- Future integration credentials use Docker secrets or an approved encrypted credential boundary, not ordinary settings rows.
