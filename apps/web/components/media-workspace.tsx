"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { formatBytes, listMedia, mediaStreamUrl, mediaThumbnailUrl, rescanMedia, type MediaItem } from "../lib/media";

export function MediaWorkspace() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [extension, setExtension] = useState("");
  const [rescanState, setRescanState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [rescans, setRescans] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { setItems(await listMedia(extension.trim() || undefined)); setError(null); } catch (reason) { setError(reason instanceof Error ? reason.message : "Media library unavailable"); } finally { setLoading(false); }
  }, [extension]);
  useEffect(() => { void refresh(); }, [refresh]);

  const imageItems = useMemo(() => items.filter((item) => item.has_thumbnail), [items]);
  const otherItems = useMemo(() => items.filter((item) => !item.has_thumbnail), [items]);
  const extensions = useMemo(() => Array.from(new Set(items.map((item) => item.extension))).sort(), [items]);

  async function triggerRescan() {
    if (rescans) return;
    setRescans(true); setRescanState(null); setError(null);
    try {
      const result = await rescanMedia();
      setRescanState(result.roots_configured ? (result.queued ? "Rescan queued — it will run in the background." : "A rescan is already running.") : "No media roots configured. Set MEDIA_ROOTS in the environment.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to queue a rescan"); } finally { setRescans(false); }
  }

  return <section aria-labelledby="media-heading" className="media-workspace section-block">
    <div className="section-heading"><div><p className="eyebrow">Approved media roots</p><h2 id="media-heading">Media</h2></div><div className="media-toolbar"><select aria-label="Filter by file type" onChange={(event) => setExtension(event.target.value)} value={extension}><option value="">All types</option>{extensions.map((item) => <option key={item} value={item}>.{item}</option>)}</select><button className="refresh-button" disabled={loading || rescans} onClick={() => void triggerRescan()} type="button">{rescans ? "Queuing…" : "Rescan library"}</button><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div></div>
    {rescanState && <div className="inline-state"><strong>Media library.</strong><span>{rescanState}</span></div>}
    {error && <div className="inline-state error-state" role="alert"><strong>Media unavailable.</strong><span>{error}</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div>}
    {loading ? <div className="task-list-placeholder" role="status">Scanning your library…</div> : items.length === 0 ? <div className="empty-state task-empty"><span className="empty-icon">▣</span><strong>No media indexed</strong><span>Configure MEDIA_ROOTS and trigger a rescan to index your library.</span></div> : <>
      {imageItems.length > 0 && <div className="media-grid">{imageItems.map((item) => <figure className="media-card" key={item.id}><a className="media-preview" href={mediaStreamUrl(item.id)} target="_blank" rel="noopener noreferrer"><img alt={item.file_name} loading="lazy" src={mediaThumbnailUrl(item.id)} /></a><figcaption><strong>{item.file_name}</strong><span>{item.width && item.height ? `${item.width}×${item.height}` : "image"} · {formatBytes(item.size_bytes)}</span><span className="media-path">{item.relative_path}</span></figcaption></figure>)}</div>}
      {otherItems.length > 0 && <div className="media-list">{otherItems.map((item) => <article className="finance-row" key={item.id}><span aria-hidden="true" className="media-file-icon">▤</span><div className="finance-row-copy"><strong>{item.file_name}</strong><span>{item.mime_type} · {formatBytes(item.size_bytes)} · {item.relative_path}</span></div><a className="text-button" href={mediaStreamUrl(item.id)} rel="noopener noreferrer" target="_blank">Open</a></article>)}</div>}
    </>}
  </section>;
}
