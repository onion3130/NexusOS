"use client";

import { useCallback, useEffect, useState } from "react";
import { listGitRepositories, type GitRepositoryView } from "../lib/workspace-views";
import { formatViewDate, ViewEmpty, ViewError, ViewLoading } from "./workspace-view-shared";

export function GitWorkspace() {
  const [items, setItems] = useState<GitRepositoryView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => { setLoading(true); try { const result = await listGitRepositories(); setItems(result.items); setError(result.available ? null : result.reason ?? "No repositories available"); } catch (reason) { setError(reason instanceof Error ? reason.message : "Git unavailable"); } finally { setLoading(false); } }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return <section aria-labelledby="git-heading" className="workspace-view section-block"><div className="section-heading"><div><p className="eyebrow">Safe repository status</p><h2 id="git-heading">Git</h2></div><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div><div className="workspace-boundary"><strong>Read-only Git inspection</strong><span>No checkout, commit, pull, push, reset, or arbitrary command operations are available.</span></div>{error && <ViewError label="Git" message={error} onRetry={() => void refresh()} />}{loading ? <ViewLoading label="repositories" /> : items.length === 0 ? <ViewEmpty title="No Git repositories found" description="Repositories are discovered only beneath approved workspace roots." /> : <div className="workspace-card-list">{items.map((item) => <article className="workspace-card" key={item.id}><div className={`workspace-card-icon ${item.clean === true ? "workspace-ok" : item.clean === false ? "workspace-warning" : ""}`} aria-hidden="true">⌘</div><div><strong>{item.name}</strong><span>{item.branch ? `Branch ${item.branch}` : "Detached or unavailable"} · {item.clean === true ? "Clean" : item.clean === false ? "Changes present" : "Status unavailable"}</span><small>{item.commit ? `${item.commit} · ${item.subject ?? "No commit subject"}` : item.reason ?? "Repository status unavailable"} · {formatViewDate(item.modified_at)}</small></div></article>)}</div>}</section>;
}
