# ADR 0001: Start as a modular monolith

- **Status:** Accepted for Phase 1 design; implementation requires owner approval.
- **Date:** 2026-08-02

## Decision

Start NexusOS as a layered modular monolith with separate web and API runtime containers. Domain modules communicate through explicit service interfaces/events, not direct table access.

## Rationale

The Raspberry Pi target favors low idle overhead and simple operations. Clear module boundaries preserve future extraction options without imposing microservice networking, deployment, and observability costs before the product is proven.

## Consequences

- One backend deployment is simpler to test and back up.
- Boundaries and contracts must be enforced through code review and tests.
- A module may later be extracted only after its interface and operational needs are documented.
