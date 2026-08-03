# NexusOS AI system

**Status:** Design only; no model provider, conversation persistence, tool registry, RAG pipeline, or AI endpoint is implemented in Milestone 1.
**Last updated:** 2026-08-02

This document gives a future coding agent the AI boundaries, safety rules, and planned sequence. It is not evidence that the planned AI features are available today.

## Current implementation

The Milestone 1 API accepts an `AI_PROVIDER` configuration value and optional provider credential placeholders so the public environment contract is stable. `AI_PROVIDER=disabled` is the supported state. The API does not call an upstream model, expose AI routes, store prompts, or execute tools.

The Raspberry Pi has no NVIDIA GPU by default. NVIDIA NIM is therefore an optional external OpenAI-compatible provider, not a default local container. The core dashboard must remain useful with all AI providers disabled.

## Goals and non-goals

The future assistant should answer questions about approved Nexus data, create useful summaries, and request typed internal tools when needed. It must remain an orchestrator behind API authorization, never an authority over permissions.

The AI system must not:

- Receive provider secrets in the browser.
- Decide whether a user is authorized.
- Execute arbitrary shell text, Python, SQL, Docker commands, or filesystem paths.
- Treat retrieved text or model output as trusted instructions.
- Persist inferred personal facts as durable memory without an explicit policy.
- Make destructive changes without a typed tool, authorization, confirmation, and audit event.

## Planned components

```text
HTTP assistant route
      |
      v
Conversation service -> context/policy assembly -> ModelGateway
                              |                         |
                              |                         +-- NVIDIA NIM adapter
                              |                         +-- OpenAI-compatible adapter
                              |                         +-- optional local endpoint
                              v
                         ToolRegistry
                              |
                 permission + risk + approval policy
                              |
                   typed domain/host adapter
```

### ModelGateway

`ModelGateway` is an internal interface that accepts normalized messages, a model policy, bounded context, and enabled tool schemas. It returns normalized text/tool events and provider-neutral failure classes. Provider adapters own HTTP details, retries, timeouts, model naming, and response normalization.

Provider selection comes from server-side policy and validated configuration. A user message must not supply an arbitrary upstream URL or credential. Logs may record provider, model identifier, latency, and bounded error class, but never keys, authorization headers, or full sensitive prompts by default.

### Context assembly

Context is assembled from the minimum authorized sources:

1. Current user message and conversation window.
2. Explicit user preferences allowed by policy.
3. Domain results fetched through domain services.
4. Source-aware retrieval results, if enabled.
5. Tool schemas permitted for the authenticated principal.

The model receives citations/source references where retrieval is used. Authorization is performed before context assembly and again when a proposed tool executes.

## Tool-calling lifecycle

```text
user message
  -> validate and persist request
  -> assemble authorized context
  -> model response
  -> validate typed tool proposal
  -> permission/risk policy
  -> user confirmation when required
  -> execute fixed adapter
  -> sanitize bounded result
  -> model follow-up
  -> final response + audit event
```

Every tool declares:

- Stable key and version.
- JSON input and output schemas.
- Required permission.
- Risk level: read, reversible write, or destructive.
- Confirmation requirement.
- Timeout, cancellation, rate limit, and retry policy.
- Audit fields and redaction rules.

Start with read-only tools such as `system.get_overview`, `tasks.list_due`, `notes.search`, and `files.list_recent`. Add write tools only after identity, authorization, jobs, confirmation UI, and audit logging are implemented.

No tool adapter may accept a free-form command. Host actions map typed values to fixed implementations and allowlists.

## Memory and retrieval

Memory is not one undifferentiated transcript. Keep separate policies for:

- Conversation history and bounded summaries.
- Explicit user preferences.
- Authoritative task/note/file data.
- Optional semantic memory with source, owner, and retention metadata.

Users must be able to inspect and delete durable memories. Retrieval results must pass domain access checks and include source references. Embeddings are indexes, not an authorization layer. Retention cleanup is an asynchronous, auditable job.

## Failure and privacy behavior

- Provider timeouts and rate limits return stable safe error codes.
- Optional AI outages do not make the health endpoint or core dashboard unavailable.
- Streaming responses support cancellation and reconnect behavior through the job contract.
- Retries are bounded and idempotent where side effects are possible.
- Prompt, completion, tool arguments, and results have explicit retention/redaction policies before logging.
- Provider endpoints are outbound-only and configured by the server; SSRF protections reject arbitrary user-controlled destinations.
- AI-generated content is untrusted input and is escaped/validated by downstream consumers.

## Implementation sequence

1. Milestone 2: identity and persistence primitives needed for ownership and sessions.
2. Milestone 5: conversation persistence, `ModelGateway`, provider configuration, normalized errors, streaming job boundary, and read-only tools.
3. Milestone 6+: assistant/task integration with explicit confirmation rules.
4. Milestone 7+: source-aware notes retrieval and optional semantic memory.
5. Milestone 8+: audited host actions and operational notifications.
6. Later: plugin-contributed tools only through the out-of-process plugin boundary.

## Configuration contract

The public names are documented in [`ENVIRONMENT.md`](ENVIRONMENT.md). Keep `AI_PROVIDER=disabled` until a provider is intentionally selected and its credential is configured locally. Never put real values in `.env.example`, source code, tests, documentation, screenshots, or commits.

## Related documents

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system boundaries and milestones.
- [`API.md`](API.md) — planned assistant, stream, job, memory, and tool contracts.
- [`SECURITY.md`](SECURITY.md) — trust boundaries and public-repository rules.
- [`DATABASE.md`](DATABASE.md) — planned conversation, run, and tool-call persistence.
