import { authenticatedFetch } from "./auth";

export type AssistantProviderStatus = {
  provider: "disabled" | "openai" | "openai_compatible" | "nvidia_nim";
  label: string;
  state: "configured" | "disabled";
  model: string | null;
  detail: string;
};

export type ConversationSummary = {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type GroundingOptions = {
  enabled: boolean;
  mode: "lexical" | "semantic" | "hybrid";
  limit: number;
};

export type SourceReference = {
  source_type: "note" | "external_source";
  source_id: string;
  chunk_id: string;
  title: string;
  source_version: number;
  retrieval_mode: "lexical" | "semantic" | "hybrid";
  rank: number;
  content_hash: string | null;
  lexical_score: number | null;
  semantic_score: number | null;
};

export type Message = {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  sequence: number;
  created_at: string;
  sources: SourceReference[];
};

export type Conversation = ConversationSummary & { messages: Message[] };

export type AssistantResult = {
  user_message: Message;
  assistant_message: Message;
  model_run: { id: string; provider: string; model: string | null; status: "started" | "succeeded" | "failed" | "disabled"; latency_ms: number | null; error_code: string | null };
  tool_calls: Array<{ id: string; tool_key: string; status: "proposed" | "validated" | "executed" | "failed"; error_code: string | null; requires_confirmation: boolean; arguments: Record<string, unknown> }>;
};

const FRIENDLY_ERRORS: Record<string, string> = {
  ai_tool_not_allowed: "That assistant action is unavailable. Notes are read-only in the Assistant; create the note from the Notes workspace.",
  ai_provider_disabled: "AI is disabled. Connect NVIDIA NIM in Admin to send messages.",
  ai_provider_timeout: "The model took too long. Try a shorter question, or raise AI_TIMEOUT_SECONDS.",
  ai_provider_unavailable: "The AI provider is unreachable or rejected the request. Check NIM settings in Admin.",
  assistant_unavailable: "Assistant hit an internal error. Try a new conversation.",
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
    const code = typeof detail?.detail === "string" ? detail.detail : "";
    if (code && FRIENDLY_ERRORS[code]) {
      throw new Error(FRIENDLY_ERRORS[code]);
    }
    if (response.status === 504) {
      throw new Error(FRIENDLY_ERRORS.ai_provider_timeout);
    }
    if (response.status === 502 || response.status === 500) {
      throw new Error(
        "Assistant proxy timed out or failed while waiting for the model. Slow NIM models need a longer proxy timeout.",
      );
    }
    throw new Error(code || `Assistant request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function readAssistantProvider(): Promise<AssistantProviderStatus> {
  return parse<AssistantProviderStatus>(await authenticatedFetch("/api/v1/system/assistant/provider", { cache: "no-store" }));
}

export async function listConversations(): Promise<ConversationSummary[]> { return parse<ConversationSummary[]>(await authenticatedFetch("/api/v1/conversations", { cache: "no-store" })); }
export async function createConversation(title?: string): Promise<ConversationSummary> { return parse<ConversationSummary>(await authenticatedFetch("/api/v1/conversations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) })); }
export async function readConversation(id: string): Promise<Conversation> { return parse<Conversation>(await authenticatedFetch(`/api/v1/conversations/${encodeURIComponent(id)}`, { cache: "no-store" })); }
function idempotencyKey(): string { return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`; }
export async function approveToolCall(id: string): Promise<void> { const response = await authenticatedFetch(`/api/v1/ai/tool-calls/${encodeURIComponent(id)}/approve`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey() } }); if (!response.ok) { const detail = (await response.json().catch(() => null)) as { detail?: string } | null; const code = typeof detail?.detail === "string" ? detail.detail : ""; throw new Error(FRIENDLY_ERRORS[code] ?? `Approval failed with ${response.status}`); } }
export async function rejectToolCall(id: string): Promise<void> { const response = await authenticatedFetch(`/api/v1/ai/tool-calls/${encodeURIComponent(id)}/reject`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey() } }); if (!response.ok) throw new Error(`Rejection failed with ${response.status}`); }
export async function sendMessage(id: string, content: string, grounding: GroundingOptions = { enabled: true, mode: "hybrid", limit: 6 }): Promise<AssistantResult> { return parse<AssistantResult>(await authenticatedFetch(`/api/v1/conversations/${encodeURIComponent(id)}/messages`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content, grounding }) })); }

export async function sendMessageStream(
  id: string,
  content: string,
  grounding: GroundingOptions,
  onUserMessage: (message: Message) => void,
  onDelta: (content: string) => void,
): Promise<AssistantResult> {
  const response = await authenticatedFetch(`/api/v1/conversations/${encodeURIComponent(id)}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream", "Idempotency-Key": idempotencyKey() },
    body: JSON.stringify({ content, grounding }),
  });
  if (!response.ok) return parse<AssistantResult>(response);
  if (!response.body) throw new Error(FRIENDLY_ERRORS.assistant_unavailable);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: AssistantResult | null = null;
  let streamError: string | null = null;

  const consume = (block: string) => {
    const lines = block.split("\n");
    const data = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
    if (!data) return;
    const parsed = JSON.parse(data) as { type?: string; content?: string; user_message?: Message; assistant_message?: Message; model_run?: AssistantResult["model_run"]; tool_calls?: AssistantResult["tool_calls"]; code?: string };
    if (parsed.type === "meta" && parsed.user_message) onUserMessage(parsed.user_message);
    if (parsed.type === "delta" && typeof parsed.content === "string") onDelta(parsed.content);
    if (parsed.type === "done" && parsed.assistant_message && parsed.model_run) {
      result = { user_message: parsed.user_message ?? ({} as Message), assistant_message: parsed.assistant_message, model_run: parsed.model_run, tool_calls: parsed.tool_calls ?? [] };
    }
    if (parsed.code) streamError = parsed.code;
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    blocks.forEach(consume);
    if (done) break;
  }
  if (buffer.trim()) consume(buffer);
  if (streamError) throw new Error(FRIENDLY_ERRORS[streamError] ?? FRIENDLY_ERRORS.assistant_unavailable);
  if (!result) throw new Error(FRIENDLY_ERRORS.assistant_unavailable);
  return result;
}
