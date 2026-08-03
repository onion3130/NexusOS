# Healthcheck contract

Healthchecks are part of the deployment contract, not a substitute for application tests.

## Current endpoints

- `GET /api/v1/health/live`: process liveness; no database dependency.
- `GET /api/v1/health/ready`: storage plus current Alembic migration-head readiness.

Readiness failures use safe dependency codes and never expose credentials, connection strings, stack traces, or internal network details. The current readiness head is `0003_tasks_notifications`.

The API and web Compose healthchecks use bounded timeouts. The real worker uses a bounded process healthcheck and no published port. Worker correctness is validated through reminder/notification tests and restart smoke tests rather than an HTTP endpoint.
