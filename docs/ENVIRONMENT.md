# Environment contract

`.env.example` is the public, placeholder-only contract. `.env` is local-only and ignored by Git. The Milestone 2 API reads these names from the process environment and fails startup with value-free errors when required values are missing or invalid. The web shell has no provider or database credentials. The template `DATABASE_URL` is container-oriented; host-only Uvicorn development should override it with `sqlite:///./data/nexus.db`.

| Variable | Required | Example/template | Secret | Purpose |
|---|---:|---|---:|---|
| `NEXUS_ENV` | yes | `development` | no | `development`, `test`, or `production` |
| `TZ` | yes | `UTC` | no | Runtime timezone |
| `DATA_DIR` | yes | `./data` | no | Persistent data root; Docker maps it to the API data mount |
| `DB_TYPE` | yes | `sqlite` | no | SQLite persistence policy for Milestone 2 |
| `DATABASE_URL` | yes | `sqlite:////var/lib/nexus/data/nexus.db` | no | SQLite identity database URL; use a local path for host-only development |
| `JWT_SECRET` | yes | placeholder only in template | yes | Session/JWT signing material |
| `SESSION_COOKIE_SECURE` | yes | `false` | no | Must be `true` in production |
| `CORS_ORIGINS` | optional | `http://localhost:3000,http://127.0.0.1:3000` | no | Comma-separated browser origins |
| `AI_PROVIDER` | yes | `disabled` | no | Reserved provider policy |
| `AI_BASE_URL` | optional | empty | no | Reserved approved provider endpoint |
| `AI_API_KEY` | conditional | placeholder only | yes | Reserved generic AI provider credential |
| `AI_MODEL` | optional | placeholder only | no | Reserved provider model identifier |
| `NVIDIA_API_KEY` | conditional | placeholder only | yes | Reserved NVIDIA NIM credential |
| `OPENAI_API_KEY` | conditional | placeholder only | yes | Reserved OpenAI-compatible credential |

## Rules

- Never log environment values or include them in API responses.
- Process environment variables are the only API runtime source; Docker/CI controls precedence.
- Production rejects placeholder or short JWT secrets and insecure session cookies.
- Provider keys are required only when the corresponding provider is enabled in a future AI milestone.
- Future integration credentials use Docker secrets or the approved encrypted credential boundary, not ordinary settings rows.
