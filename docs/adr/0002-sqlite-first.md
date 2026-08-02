# ADR 0002: SQLite first, PostgreSQL-compatible interfaces

- **Status:** Accepted for Phase 1 design; implementation requires owner approval.
- **Date:** 2026-08-02

## Decision

Use SQLite on the Raspberry Pi initially, with SQLAlchemy/Alembic repositories and migrations designed for PostgreSQL compatibility. Validate migrations against both engines before declaring PostgreSQL support complete.

## Rationale

SQLite minimizes idle resource use and operational dependencies on a single-user local system. Repository boundaries and migration discipline preserve a path to PostgreSQL as concurrency or multi-user needs grow.

## Consequences

- WAL mode, foreign keys, short transactions, and SSD storage are required.
- SQLite-specific SQL must not leak into domain services.
- PostgreSQL compatibility is a tested claim, not an assumption.
