# Healthcheck contract

Healthchecks are part of the deployment contract, not a substitute for application tests.

## Current endpoints

- `GET /api/v1/health/live`: process liveness; no database dependency.
- `GET /api/v1/health/ready`: Milestone 1 storage readiness; database and migration checks are deferred.

Readiness failures must identify a safe dependency code without exposing credentials, connection strings, stack traces, or internal network details. Compose healthchecks should distinguish liveness from readiness and use bounded timeouts/retries.

Milestone 1 Compose uses the API liveness endpoint for the API container healthcheck. The web, proxy, worker, and opt-in AI placeholders use bounded process/service checks until their real implementations exist.
