"use client";

import { useCallback, useEffect, useState } from "react";
import { listRecentFiles, type FileEntry } from "../lib/workspace-views";
import { formatViewBytes, formatViewDate, ViewEmpty, ViewError, ViewLoading } from "./workspace-view-shared";

export function FilesWorkspace() {
  const [items, setItems] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => { setLoading(true); try { const result = await listRecentFiles(); setItems(result.items); setError(result.available ? null : result.reason ?? "No approved roots configured"); } catch (reason) { setError(reason instanceof Error ? reason.message : "Files unavailable"); } finally { setLoading(false); } }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return <section aria-labelledby="files-heading" className="workspace-view section-block"><div className="section-heading"><div><p className="eyebrow">Read-only host view</p><h2 id="files-heading">Files</h2></div><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div><div className="workspace-boundary"><strong>Metadata only</strong><span>Only approved roots are scanned. File contents and sensitive credential files stay private.</span></div>{error && <ViewError label="Files" message={error} onRetry={() => void refresh()} />}{loading ? <ViewLoading label="files" /> : items.length === 0 ? <ViewEmpty title="No recent files" description="Configure an approved workspace root or add files beneath the current data root." /> : <div className="workspace-card-list">{items.map((item) => <article className="workspace-card" key={`${item.source}:${item.path}`}><div className="workspace-card-icon" aria-hidden="true">▤</div><div><strong>{item.name}</strong><span>{item.path}</span><small>{formatViewBytes(item.size_bytes)} · {formatViewDate(item.modified_at)} · {item.source}</small></div></article>)}</div>}</section>;
}
