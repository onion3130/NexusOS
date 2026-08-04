import { authenticatedFetch } from "./auth";

export type Note = {
  id: string;
  title: string;
  content: string;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  content_version: number;
  tags: string[];
};

export type SearchResult = {
  source_type: "note";
  source_id: string;
  chunk_id: string | null;
  title: string;
  excerpt: string;
  score: number;
  lexical_score?: number | null;
  semantic_score?: number | null;
  retrieval_mode?: "lexical" | "semantic" | "hybrid";
  updated_at: string;
  source_version: number;
  tags: string[];
};

export type EmbeddingStatus = {
  enabled: boolean;
  provider: string;
  model: string | null;
  dimensions: number | null;
  pending: number;
  ready: number;
  stale: number;
  failed: number;
};

type NoteInput = {
  title: string;
  content: string;
  tags?: string[];
  status?: Note["status"];
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Notes request failed with ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function idempotencyKey(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

export async function listNotes(status = "active"): Promise<Note[]> {
  const response = await authenticatedFetch(`/api/v1/notes?status_filter=${encodeURIComponent(status)}`, { cache: "no-store" });
  return (await parse<{ items: Note[] }>(response)).items;
}

export async function createNote(input: NoteInput): Promise<Note> {
  return parse<Note>(await authenticatedFetch("/api/v1/notes", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function updateNote(id: string, input: Partial<NoteInput>): Promise<Note> {
  return parse<Note>(await authenticatedFetch(`/api/v1/notes/${encodeURIComponent(id)}`, { method: "PATCH", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function archiveNote(id: string): Promise<Note> {
  return parse<Note>(await authenticatedFetch(`/api/v1/notes/${encodeURIComponent(id)}/archive`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey() } }));
}

export async function restoreNote(id: string): Promise<Note> {
  return parse<Note>(await authenticatedFetch(`/api/v1/notes/${encodeURIComponent(id)}/restore`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey() } }));
}

export async function deleteNote(id: string): Promise<void> {
  await parse<void>(await authenticatedFetch(`/api/v1/notes/${encodeURIComponent(id)}`, { method: "DELETE", headers: { "Idempotency-Key": idempotencyKey() } }));
}

export async function searchNotes(query: string, includeArchived = false, tag?: string): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query, include_archived: String(includeArchived) });
  if (tag) params.set("tag", tag);
  const response = await authenticatedFetch(`/api/v1/search?${params.toString()}`, { cache: "no-store" });
  return (await parse<{ items: SearchResult[] }>(response)).items;
}

export async function retrieveNotes(query: string, mode: "lexical" | "semantic" | "hybrid", includeArchived = false, limit = 8): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query, mode, include_archived: String(includeArchived), limit: String(limit) });
  return parse<SearchResult[]>(await authenticatedFetch(`/api/v1/search/retrieve?${params.toString()}`, { cache: "no-store" }));
}

export async function getEmbeddingStatus(): Promise<EmbeddingStatus> {
  return parse<EmbeddingStatus>(await authenticatedFetch("/api/v1/search/embeddings/status", { cache: "no-store" }));
}
