import { authenticatedFetch } from "./auth";

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
  source_type: "note";
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

export type Conversation = ConversationSummary & {
  messages: Message[];
};

export type AssistantResult = {
  user_message: Message;
  assistant_message: Message;
  model_run: {
    id: string;
    provider: string;
    model: string | null;
    status: "started" | "succeeded" | "failed" | "disabled";
    latency_ms: number | null;
    error_code: string | null;
  };
  tool_calls: Array<{
    id: string;
    tool_key: string;
    status: "proposed" | "validated" | "executed" | "failed";
    error_code: string | null;
    requires_confirmation: boolean;
    arguments: Record<string, unknown>;
  }>;
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(detail?.detail ?? `Assistant request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function listConversations(): Promise<ConversationSummary[]> {
  return parse<ConversationSummary[]>(await authenticatedFetch("/api/v1/conversations", { cache: "no-store" }));
}

export async function createConversation(title?: string): Promise<ConversationSummary> {
  return parse<ConversationSummary>(await authenticatedFetch("/api/v1/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  }));
}

export async function readConversation(id: string): Promise<Conversation> {
  return parse<Conversation>(await authenticatedFetch(`/api/v1/conversations/${encodeURIComponent(id)}`, { cache: "no-store" }));
}

function idempotencyKey(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

export async function approveToolCall(id: string): Promise<void> {
  const response = await authenticatedFetch(`/api/v1/ai/tool-calls/${encodeURIComponent(id)}/approve`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey() } });
  if (!response.ok) throw new Error(`Approval failed with ${response.status}`);
}

export async function rejectToolCall(id: string): Promise<void> {
  const response = await authenticatedFetch(`/api/v1/ai/tool-calls/${encodeURIComponent(id)}/reject`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey() } });
  if (!response.ok) throw new Error(`Rejection failed with ${response.status}`);
}

export async function sendMessage(id: string, content: string, grounding: GroundingOptions = { enabled: true, mode: "hybrid", limit: 6 }): Promise<AssistantResult> {
  return parse<AssistantResult>(await authenticatedFetch(`/api/v1/conversations/${encodeURIComponent(id)}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, grounding }),
  }));
}
