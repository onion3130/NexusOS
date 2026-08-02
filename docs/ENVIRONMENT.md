# Environment contract

`.env.example` is the public, placeholder-only contract. `.env` is local-only and ignored by Git. The future application runtime must load these names from the process environment and fail startup with value-free errors when required values are missing.

| Variable | Required | Example/template | Secret | Purpose |
|---|---:|---|---:|---|
| `NEXUS_ENV` | yes | `development` | no | `development`, `test`, or `production` |
| `TZ` | yes | `UTC` | no | Runtime timezone |
| `DATA_DIR` | yes | `./data` | no | Persistent data root; Pi uses the SSD |
| `DB_TYPE` | yes | `sqlite` | no | Initial persistence mode |
| `DATABASE_URL` | yes | `sqlite:////var/lib/nexus/data/nexus.db` | no | Database connection |
| `JWT_SECRET` | yes | placeholder only in template | yes | Session/JWT signing material |
| `SESSION_COOKIE_SECURE` | yes | `false` | no | Must be `true` in production |
| `AI_PROVIDER` | yes | `disabled` | no | Provider policy |
| `AI_BASE_URL` | optional | empty | no | Approved provider endpoint |
| `AI_API_KEY` | conditional | placeholder only | yes | Generic AI provider credential |
| `AI_MODEL` | optional | placeholder only | no | Provider model identifier |
| `NVIDIA_API_KEY` | conditional | placeholder only | yes | NVIDIA NIM credential |
| `OPENAI_API_KEY` | conditional | placeholder only | yes | OpenAI-compatible credential |

## Rules

- Never log environment values or include them in API responses.
- Process environment variables take precedence over a local dotenv file in CI/containers.
- Production rejects placeholder or short JWT secrets and insecure session cookies.
- Provider keys are required only when the corresponding provider is enabled.
- Future integration credentials use Docker secrets or the approved encrypted credential boundary, not ordinary settings rows.
