# ADR-0006: Safe host actions and recovery boundary

- **Status:** Accepted
- **Date:** 2026-08-03
- **Milestone:** 8

## Context

NexusOS needs useful maintenance capabilities on a Raspberry Pi 5 without turning an authenticated browser or an AI provider into an arbitrary host-control interface. SQLite is the current persistence boundary, the API and worker run as non-root ARM64 services, and all previous mutations use permissions, CSRF protection, ownership checks, idempotency, and audit events.

## Decision

Milestone 8 implements a typed, server-owned action catalog with three capabilities:

- create a hot SQLite backup;
- verify a NexusOS-created backup; and
- run SQLite `integrity_check`.

Every action follows this lifecycle:

```text
request -> validate fixed key/input -> persist expiring proposal -> explicit user confirmation -> durable job -> fixed adapter -> audit result
```

Proposal creation is inert. Confirmation is mandatory for direct browser requests and assistant-originated requests. The assistant may create a backup proposal, but it cannot confirm it. Proposal, confirmation, rejection, success, and failure transitions are auditable and user-scoped.

Backups use Python's SQLite online backup API and are written only to the fixed `DATA_DIR/backups` directory. Metadata includes a relative path, byte size, SHA-256 digest, SQLite integrity result, and verification timestamp. The API never returns backup contents.

## Security boundary

The catalog does not accept arbitrary shell text, executable names, filesystem paths, Docker arguments, Docker socket access, SQL, reboot/shutdown requests, package management, systemd control, restore requests, or provider URLs. No subprocess is required for the implemented actions. The worker has no published port and remains non-root.

Any future privileged host operation requires a separate broker design with explicit capability isolation, absolute executable paths, fixed arguments, `shell=False`, resource limits, rollback behavior, and independent security review.

## Recovery limitations

Backups on the same SSD are not disaster recovery. Automated restore, encrypted/off-host replication, retention cleanup, last-backup deletion protection, and backup-before-migration orchestration remain deployment work. Restore is intentionally an operator-controlled procedure and is not exposed to the browser or assistant.

## Consequences

- Maintenance is useful and auditable while remaining Pi-compatible and low-resource.
- The worker can resume durable jobs after process restarts.
- The action surface is deliberately narrow; reboot and service management require a later milestone.
- Runtime Docker and Raspberry Pi validation remain release gates because the current development host lacks Docker and ARM64 hardware.
