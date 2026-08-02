# ADR 0003: Provider-neutral AI gateway

- **Status:** Accepted for Phase 1 design; implementation requires owner approval.
- **Date:** 2026-08-02

## Decision

All hosted, NVIDIA NIM, and optional local model providers connect through an internal normalized gateway. The gateway owns provider selection, credentials, retries, streaming normalization, redaction, and usage metadata.

## Rationale

Nexus must remain useful when AI is disabled, avoid coupling domain modules to vendor APIs, and support a Raspberry Pi without assuming local GPU inference.

## Consequences

- Provider credentials stay server-side and outside ordinary logs.
- Tool authorization remains in Nexus, never in model output.
- Provider-specific features require explicit capability negotiation and tests.
