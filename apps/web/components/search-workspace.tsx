"use client";

import { useEffect, useState } from "react";
import { getEmbeddingStatus, retrieveNotes, type EmbeddingStatus, type SearchResult } from "../lib/notes";

export function SearchWorkspace({ onOpenNote, onBack }: { onOpenNote: (id: string) => void; onBack: () => void }) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [mode, setMode] = useState<"lexical" | "semantic" | "hybrid">("lexical");
  const [embeddingStatus, setEmbeddingStatus] = useState<EmbeddingStatus | null>(null);

  useEffect(() => {
    void getEmbeddingStatus().then(setEmbeddingStatus).catch(() => setEmbeddingStatus(null));
  }, []);

  useEffect(() => {
    const normalized = query.trim();
    if (normalized.length < 2) { setItems([]); setLoading(false); return; }
    const timer = window.setTimeout(() => {
      setLoading(true); setError(null);
      void retrieveNotes(normalized, mode, includeArchived).then(setItems).catch((reason) => {
        setError(reason instanceof Error ? reason.message : "Search unavailable");
        if (mode !== "lexical") setMode("lexical");
      }).finally(() => setLoading(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [includeArchived, mode, query]);

  const semanticAvailable = Boolean(embeddingStatus?.enabled);
  const selectedMode = semanticAvailable ? mode : "lexical";

  return <section aria-labelledby="search-heading" className="search-workspace section-block">
    <div className="section-heading"><div><p className="eyebrow">Source-aware retrieval</p><h2 id="search-heading">Search</h2></div><button className="text-button" onClick={onBack} type="button">Back to notes</button></div>
    <div className="search-bar"><span aria-hidden="true">⌕</span><input aria-label="Search notes" autoFocus maxLength={200} onChange={(event) => setQuery(event.target.value)} placeholder="Search your notes…" value={query} /></div>
    <div className="search-options">
      <label className="checkbox-label"><input checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} type="checkbox" /> Include archived</label>
      <label className="search-mode-label" htmlFor="retrieval-mode">Retrieval mode</label>
      <select aria-label="Retrieval mode" id="retrieval-mode" onChange={(event) => setMode(event.target.value as typeof mode)} value={selectedMode}>
        <option value="lexical">Lexical</option>
        <option disabled={!semanticAvailable} value="hybrid">Hybrid{semanticAvailable ? "" : " · unavailable"}</option>
        <option disabled={!semanticAvailable} value="semantic">Semantic{semanticAvailable ? "" : " · unavailable"}</option>
      </select>
      <span>{query.trim().length < 2 ? "Type at least two characters" : `${items.length} result${items.length === 1 ? "" : "s"}`}</span>
    </div>
    {!semanticAvailable && <div className="inline-state" role="status"><strong>Lexical search active.</strong><span>Semantic retrieval is disabled or still being configured on the server.</span></div>}
    {error && <div className="inline-state error-state" role="alert"><strong>Search unavailable.</strong><span>{error}</span></div>}
    {loading ? <div className="task-list-placeholder" role="status">Searching your notes with {selectedMode} retrieval…</div> : query.trim().length >= 2 && items.length === 0 && !error ? <div className="empty-state task-empty"><span className="empty-icon">⌕</span><strong>No matching notes</strong><span>Try a different phrase or tag.</span></div> : <div aria-live="polite" className="search-results">{items.map((item) => <button className="search-result" key={`${item.source_id}-${item.chunk_id ?? "note"}`} onClick={() => onOpenNote(item.source_id)} type="button"><div className="search-result-top"><span className="source-badge">{item.retrieval_mode ?? selectedMode}</span><small>{new Date(item.updated_at).toLocaleDateString()}</small></div><strong>{item.title}</strong><p>{item.excerpt}</p><div className="task-meta">{item.tags.map((tag) => <span key={tag}>#{tag}</span>)}<span>Source v{item.source_version}</span></div></button>)}</div>}
  </section>;
}
