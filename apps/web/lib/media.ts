import { authenticatedFetch } from "./auth";

export type MediaItem = {
  id: string;
  root_key: string;
  relative_path: string;
  file_name: string;
  extension: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  width: number | null;
  height: number | null;
  has_thumbnail: boolean;
  indexed_at: string;
  updated_at: string;
};

export type MediaRescan = {
  queued: boolean;
  job_id: string | null;
  roots_configured: boolean;
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Media request failed with ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export async function listMedia(extension?: string, folder?: string): Promise<MediaItem[]> {
  const params = new URLSearchParams();
  if (extension) params.set("extension", extension);
  if (folder) params.set("folder", folder);
  const query = params.toString();
  const response = await authenticatedFetch(`/api/v1/media/items${query ? `?${query}` : ""}`, { cache: "no-store" });
  const body = await parse<{ items: MediaItem[] }>(response);
  return body.items;
}

export async function rescanMedia(): Promise<MediaRescan> {
  return parse<MediaRescan>(await authenticatedFetch("/api/v1/media/rescan", { method: "POST", headers: { "Idempotency-Key": typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}` } }));
}

export function mediaThumbnailUrl(id: string): string {
  return `/api/v1/media/items/${encodeURIComponent(id)}/thumbnail`;
}

export function mediaStreamUrl(id: string): string {
  return `/api/v1/media/items/${encodeURIComponent(id)}/stream`;
}
