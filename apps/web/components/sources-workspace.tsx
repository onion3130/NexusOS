"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { archiveSource, createUrlSource, deleteSource, disableSourceSync, importApprovedFile, listApprovedFiles, listSources, reindexSource, restoreSource, syncSourceNow, updateSourceSync, uploadSource, type ApprovedFile, type Source } from "../lib/sources";

function formatBytes(value: number) { return value < 1024 * 1024 ? `${Math.round(value / 1024)} KB` : `${(value / 1024 / 1024).toFixed(1)} MB`; }

export function SourcesWorkspace() {
  const [items, setItems] = useState<Source[]>([]);
  const [approved, setApproved] = useState<ApprovedFile[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [urlDraft, setUrlDraft] = useState("");

  async function addFromUrl(event: FormEvent) {
    event.preventDefault();
    const url = urlDraft.trim();
    if (!url || busy) return;
    await run("url", async () => { await createUrlSource(url); });
    setUrlDraft("");
  }

  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try { const [sources, files] = await Promise.all([listSources(showArchived ? "all" : "active"), listApprovedFiles()]); setItems(sources); setApproved(files); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Sources unavailable"); }
    finally { setLoading(false); }
  }, [showArchived]);
  useEffect(() => { void refresh(); }, [refresh]);

  async function run(action: string, operation: () => Promise<Source | void>) { setBusy(action); setError(null); try { await operation(); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Source action failed"); } finally { setBusy(null); } }
  async function upload(event: React.ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; event.target.value = ""; if (!file) return; await run("upload", () => uploadSource(file)); }
  async function importFile(file: ApprovedFile) { await run(file.file_id, () => importApprovedFile(file.file_id)); }
  async function remove(item: Source) { if (!window.confirm(`Delete “${item.title}”?`)) return; await run(item.id, () => deleteSource(item.id)); }
  async function toggleSync(item: Source) { const enabled = !item.sync?.enabled; await run(`sync-${item.id}`, async () => { await updateSourceSync(item.id, enabled, item.sync?.interval_seconds ?? 3600); }); }
  async function syncNow(item: Source) { await run(`sync-now-${item.id}`, async () => { await syncSourceNow(item.id); }); }

  return <section aria-labelledby="sources-heading" className="workspace-view section-block sources-workspace">
    <div className="section-heading"><div><p className="eyebrow">Private knowledge base</p><h2 id="sources-heading">Sources</h2></div><div className="notes-actions"><label className="primary-button file-button">{busy === "upload" ? "Uploading…" : "Upload document"}<input accept=".txt,.md,.markdown,.pdf,text/plain,text/markdown,application/pdf" disabled={busy !== null} onChange={(event) => void upload(event)} type="file" /></label><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div></div>
    <div className="workspace-boundary"><strong>Read-only reference sources</strong><span>Text, Markdown, and PDF files plus single-page URLs are parsed in the worker, versioned, chunked, and made available to scoped search and the Assistant. Imported content is never treated as instructions.</span></div>
    <form className="source-url-form" onSubmit={(event) => void addFromUrl(event)}>
      <input aria-label="Source URL" onChange={(event) => setUrlDraft(event.target.value)} placeholder="Add a single page by URL — https://…" type="url" value={urlDraft} />
      <button className="primary-button" disabled={busy !== null || !urlDraft.trim()} type="submit">{busy === "url" ? "Adding…" : "Add from URL"}</button>
    </form>
    {error && <div className="inline-state error-state" role="alert"><strong>Sources unavailable.</strong><span>{error}</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div>}
    <div className="sources-toolbar"><label className="checkbox-label"><input checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} type="checkbox" /> Show archived</label><span>{items.length} source{items.length === 1 ? "" : "s"}</span></div>
    {approved.length > 0 && <div className="source-import-panel"><div><strong>Approved workspace files</strong><span>Only server-discovered text files beneath configured roots are shown.</span></div><div className="approved-file-list">{approved.slice(0, 12).map((file) => <button className="approved-file" disabled={busy !== null} key={file.file_id} onClick={() => void importFile(file)} type="button"><strong>{file.name}</strong><span>{file.relative_path} · {formatBytes(file.size_bytes)}</span></button>)}</div></div>}
    {loading ? <div className="task-list-placeholder" role="status">Loading sources…</div> : items.length === 0 ? <div className="empty-state task-empty"><span className="empty-icon">◇</span><strong>No external sources yet</strong><span>Upload a UTF-8 text, Markdown, or PDF file — or add a single page URL — to make it searchable.</span></div> : <div className="source-list">{items.map((item) => <article className="source-card" key={item.id}><div className={`workspace-card-icon ${item.status === "ready" ? "workspace-ok" : item.status === "failed" ? "workspace-warning" : ""}`} aria-hidden="true">◇</div><div className="source-card-body"><div className="source-card-heading"><div><strong>{item.title}</strong><span>{item.original_name} · {formatBytes(item.size_bytes)} · {item.kind === "approved_file" ? "Approved file" : item.kind === "url" ? "Page URL" : "Upload"}</span>{item.source_url ? <span className="workspace-help">{item.source_url}</span> : null}</div><span className={`plugin-status plugin-status-${item.status}`}>{item.status}</span></div><small>{item.status === "processing" ? "Ingestion is running in the background." : item.status === "failed" ? `Ingestion failed: ${item.last_error_code ?? "unknown error"}` : item.status === "ready" ? `Indexed version ${item.current_version}` : "Archived"}</small><div className="source-card-actions">{item.status === "processing" && <span className="workspace-help">Ingestion is running in the background.</span>}{item.status === "failed" && <button className="text-button" disabled={busy !== null} onClick={() => void run(item.id, () => reindexSource(item.id))} type="button">Retry ingestion</button>}{item.kind === "approved_file" && <><button className="text-button" disabled={busy !== null} onClick={() => void toggleSync(item)} type="button">{item.sync?.enabled ? "Disable sync" : "Enable sync"}</button><button className="text-button" disabled={busy !== null} onClick={() => void syncNow(item)} type="button">Sync now</button><span className="workspace-help">{item.sync?.enabled ? `Every ${Math.round((item.sync.interval_seconds ?? 3600) / 60)} min` : "Manual import only"}{item.sync?.last_error_code ? ` · ${item.sync.last_error_code}` : ""}</span></>}{item.status === "archived" ? <button className="text-button" disabled={busy !== null} onClick={() => void run(item.id, () => restoreSource(item.id))} type="button">Restore</button> : <button className="text-button" disabled={busy !== null} onClick={() => void run(item.id, () => archiveSource(item.id))} type="button">Archive</button>}<button className="text-button danger-text" disabled={busy !== null} onClick={() => void remove(item)} type="button">Delete</button></div></div></article>)}</div>}
  </section>;
}
