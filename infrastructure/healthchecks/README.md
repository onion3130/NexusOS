# Healthcheck contract

Healthchecks are part of the deployment contract, not a substitute for application tests.

## Required endpoints once the API exists

- `GET /api/v1/health/live`: process liveness; no database dependency.
- `GET /api/v1/health/ready`: readiness for required dependencies, storage, and migrations.

Readiness failures must identify a safe dependency code without exposing credentials, connection strings, stack traces, or internal network details. Compose healthchecks should distinguish liveness from readiness and use bounded timeouts/retries.

The current Compose placeholders use a process-level healthcheck only because no API process exists yet.
