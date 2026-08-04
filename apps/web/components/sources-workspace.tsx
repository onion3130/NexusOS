"use client";

import { useCallback, useEffect, useState } from "react";
import { archiveSource, deleteSource, importApprovedFile, listApprovedFiles, listSources, reindexSource, restoreSource, uploadSource, type ApprovedFile, type Source } from "../lib/sources";

function formatBytes(value: number) { return value < 1024 * 1024 ? `${Math.round(value / 1024)} KB` : `${(value / 1024 / 1024).toFixed(1)} MB`; }

export function SourcesWorkspace() {
  const [items, setItems] = useState<Source[]>([]);
  const [approved, setApproved] = useState<ApprovedFile[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return <section aria-labelledby="sources-heading" className="workspace-view section-block sources-workspace">
    <div className="section-heading"><div><p className="eyebrow">Private knowledge base</p><h2 id="sources-heading">Sources</h2></div><div className="notes-actions"><label className="primary-button file-button">{busy === "upload" ? "Uploading…" : "Upload text file"}<input accept=".txt,.md,.markdown,text/plain,text/markdown" disabled={busy !== null} onChange={(event) => void upload(event)} type="file" /></label><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div></div>
    <div className="workspace-boundary"><strong>Read-only reference sources</strong><span>Text and Markdown sources are parsed in the worker, versioned, chunked, and made available to scoped search and the Assistant. Imported content is never treated as instructions.</span></div>
    {error && <div className="inline-state error-state" role="alert"><strong>Sources unavailable.</strong><span>{error}</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div>}
    <div className="sources-toolbar"><label className="checkbox-label"><input checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} type="checkbox" /> Show archived</label><span>{items.length} source{items.length === 1 ? "" : "s"}</span></div>
    {approved.length > 0 && <div className="source-import-panel"><div><strong>Approved workspace files</strong><span>Only server-discovered text files beneath configured roots are shown.</span></div><div className="approved-file-list">{approved.slice(0, 12).map((file) => <button className="approved-file" disabled={busy !== null} key={file.file_id} onClick={() => void importFile(file)} type="button"><strong>{file.name}</strong><span>{file.relative_path} · {formatBytes(file.size_bytes)}</span></button>)}</div></div>}
    {loading ? <div className="task-list-placeholder" role="status">Loading sources…</div> : items.length === 0 ? <div className="empty-state task-empty"><span className="empty-icon">◇</span><strong>No external sources yet</strong><span>Upload a UTF-8 text or Markdown file to make it searchable.</span></div> : <div className="source-list">{items.map((item) => <article className="source-card" key={item.id}><div className={`workspace-card-icon ${item.status === "ready" ? "workspace-ok" : item.status === "failed" ? "workspace-warning" : ""}`} aria-hidden="true">◇</div><div className="source-card-body"><div className="source-card-heading"><div><strong>{item.title}</strong><span>{item.original_name} · {formatBytes(item.size_bytes)} · {item.kind === "approved_file" ? "Approved file" : "Upload"}</span></div><span className={`plugin-status plugin-status-${item.status}`}>{item.status}</span></div><small>{item.status === "processing" ? "Ingestion is running in the background." : item.status === "failed" ? `Ingestion failed: ${item.last_error_code ?? "unknown error"}` : item.status === "ready" ? `Indexed version ${item.current_version}` : "Archived"}</small><div className="source-card-actions">{item.status === "processing" && <span className="workspace-help">Retry after the worker finishes.</span>}{item.status === "failed" && <button className="text-button" disabled={busy !== null} onClick={() => void run(item.id, () => reindexSource(item.id))} type="button">Retry ingestion</button>}{item.status === "archived" ? <button className="text-button" disabled={busy !== null} onClick={() => void run(item.id, () => restoreSource(item.id))} type="button">Restore</button> : <button className="text-button" disabled={busy !== null} onClick={() => void run(item.id, () => archiveSource(item.id))} type="button">Archive</button>}<button className="text-button danger-text" disabled={busy !== null} onClick={() => void remove(item)} type="button">Delete</button></div></div></article>)}</div>}
  </section>;
}
