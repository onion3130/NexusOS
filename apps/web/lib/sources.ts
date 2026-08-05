import { authenticatedFetch } from "./auth";

export type Source = {
  id: string; kind: "upload" | "approved_file"; title: string; original_name: string; mime_type: string; size_bytes: number; sha256: string;
  status: "processing" | "ready" | "failed" | "archived"; current_version: number; last_ingested_at: string | null; last_error_code: string | null;
  created_at: string; updated_at: string; archived_at: string | null; sync: SourceSync | null;
};
export type ApprovedFile = { file_id: string; root_key: string; relative_path: string; name: string; mime_type: string; size_bytes: number; sha256: string };
export type SourceSync = { id: string; enabled: boolean; interval_seconds: number; last_checked_at: string | null; last_changed_at: string | null; last_success_at: string | null; last_error_code: string | null; next_check_at: string | null };

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) { const body = await response.json().catch(() => null) as { detail?: string } | null; throw new Error(body?.detail ?? `Sources request failed with ${response.status}`); }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
function key() { return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`; }
export async function listSources(status = "active"): Promise<Source[]> { return (await parse<{ items: Source[] }>(await authenticatedFetch(`/api/v1/sources?status_filter=${status}`, { cache: "no-store" }))).items; }
export async function listApprovedFiles(): Promise<ApprovedFile[]> { return (await parse<{ items: ApprovedFile[] }>(await authenticatedFetch("/api/v1/sources/approved-files", { cache: "no-store" }))).items; }
export async function uploadSource(file: File, title?: string): Promise<Source> { const headers: Record<string, string> = { "Idempotency-Key": key(), "Content-Type": file.type || "text/plain", "X-Source-Filename": file.name }; if (title?.trim()) headers["X-Source-Title"] = title.trim(); return parse<Source>(await authenticatedFetch("/api/v1/sources/upload", { method: "POST", headers, body: file })); }
export async function importApprovedFile(fileId: string, title?: string): Promise<Source> { return parse<Source>(await authenticatedFetch("/api/v1/sources/import-approved-file", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key() }, body: JSON.stringify({ file_id: fileId, title }) })); }
export async function archiveSource(id: string): Promise<Source> { return parse<Source>(await authenticatedFetch(`/api/v1/sources/${encodeURIComponent(id)}/archive`, { method: "POST", headers: { "Idempotency-Key": key() } })); }
export async function restoreSource(id: string): Promise<Source> { return parse<Source>(await authenticatedFetch(`/api/v1/sources/${encodeURIComponent(id)}/restore`, { method: "POST", headers: { "Idempotency-Key": key() } })); }
export async function reindexSource(id: string): Promise<Source> { return parse<Source>(await authenticatedFetch(`/api/v1/sources/${encodeURIComponent(id)}/reindex`, { method: "POST", headers: { "Idempotency-Key": key() } })); }
export async function deleteSource(id: string): Promise<void> { await parse<void>(await authenticatedFetch(`/api/v1/sources/${encodeURIComponent(id)}`, { method: "DELETE", headers: { "Idempotency-Key": key() } })); }
export async function updateSourceSync(id: string, enabled: boolean, intervalSeconds: number): Promise<SourceSync> { return parse<SourceSync>(await authenticatedFetch(`/api/v1/sources/${encodeURIComponent(id)}/sync`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key() }, body: JSON.stringify({ enabled, interval_seconds: intervalSeconds }) })); }
export async function disableSourceSync(id: string): Promise<SourceSync> { return parse<SourceSync>(await authenticatedFetch(`/api/v1/sources/${encodeURIComponent(id)}/sync`, { method: "DELETE", headers: { "Idempotency-Key": key() } })); }
export async function syncSourceNow(id: string): Promise<{ id: string; source_id: string; status: string }> { return parse<{ id: string; source_id: string; status: string }>(await authenticatedFetch(`/api/v1/sources/${encodeURIComponent(id)}/sync-now`, { method: "POST", headers: { "Idempotency-Key": key() } })); }
