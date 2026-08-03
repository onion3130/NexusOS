# NexusOS AI system

**Current milestone:** Milestone 1
**Status:** Design only. No model provider, AI route, conversation storage, memory system, RAG pipeline, or tool registry is implemented.
**Last updated:** 2026-08-02

## Current behavior

The API accepts AI configuration fields so the public environment contract can be prepared:

- `AI_PROVIDER=disabled` is the supported current setting.
- `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL` are reserved configuration fields.
- `NVIDIA_API_KEY` and `OPENAI_API_KEY` are placeholder-only provider credentials.

The API does not call an upstream model, store prompts, stream responses, make tool calls, or expose AI endpoints. The web shell only displays that AI is disabled.

NVIDIA NIM is an external provider option, not a default Raspberry Pi service. A Pi 5 is not assumed to have an NVIDIA GPU. Local inference remains optional and must have an explicit resource budget.

## Future architecture

```text
Assistant API
    -> conversation/policy service
        -> authorized context assembly
            -> ModelGateway
                ├── NVIDIA NIM adapter
                ├── OpenAI-compatible adapter
                └── optional local endpoint
            -> ToolRegistry
                -> typed domain or host adapter
```

`ModelGateway` will normalize provider requests, responses, timeouts, retries, and error classes. Provider selection will be server-side policy; users and model output will not supply arbitrary upstream URLs or credentials.

## Tool-calling lifecycle

```text
user message
  -> validate and persist
  -> assemble authorized context
  -> model proposes typed call
  -> validate schema and permissions
  -> request confirmation for risky action
  -> execute fixed adapter
  -> sanitize result
  -> model follow-up
  -> final response and audit event
```

Every tool must declare a stable key/version, JSON input/output schemas, required permission, risk level, confirmation requirement, timeout, cancellation behavior, rate limit, and redaction rules.

Start with read-only tools such as `system.get_overview`, `tasks.list_due`, `notes.search`, and `files.list_recent`. Add writes only after identity, authorization, jobs, confirmation UI, and auditing exist. No tool may execute arbitrary shell text, SQL, Docker commands, or filesystem paths.

## Memory and retrieval design

Future memory must separate:

- Conversation history and bounded summaries.
- Explicit user preferences.
- Authoritative task, note, and file data.
- Optional semantic memory with owner, source, and retention metadata.

Retrieval must check access before returning content and include source references. Embeddings are indexes, not an authorization layer. Users must be able to inspect and delete durable memories. Model guesses must not become durable user facts without an explicit policy.

## Privacy and failure rules

- Provider keys never reach the browser.
- Provider errors degrade the assistant without taking down health or core dashboard services.
- Retries are bounded and side effects are idempotent where possible.
- Logs record provider/model/latency metadata only when safe; never keys, authorization headers, or unbounded sensitive prompts.
- AI output is untrusted input and must be validated/escaped by downstream consumers.
- Optional providers are outbound-only and must be protected against SSRF.
- Destructive operations require explicit user confirmation and an audit record.

## Implementation order

1. Milestone 2: identity and persistence primitives.
2. Milestone 5: conversation persistence, gateway, provider configuration, streaming job boundary, and read-only tools.
3. Milestone 6: task/reminder assistant actions with policy checks.
4. Milestone 7: source-aware retrieval and optional semantic memory.
5. Milestone 8: audited host actions.

See [`API.md`](API.md), [`DATABASE.md`](DATABASE.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), and [`ROADMAP.md`](ROADMAP.md).
