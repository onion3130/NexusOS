"use client";

import { useCallback, useEffect, useState } from "react";
import { listProjects, type ProjectView } from "../lib/workspace-views";
import { formatViewDate, ViewEmpty, ViewError, ViewLoading } from "./workspace-view-shared";

export function ProjectsWorkspace() {
  const [items, setItems] = useState<ProjectView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => { setLoading(true); try { const result = await listProjects(); setItems(result.items); setError(result.available ? null : result.reason ?? "No approved roots configured"); } catch (reason) { setError(reason instanceof Error ? reason.message : "Projects unavailable"); } finally { setLoading(false); } }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return <section aria-labelledby="projects-heading" className="workspace-view section-block"><div className="section-heading"><div><p className="eyebrow">Configured workspace roots</p><h2 id="projects-heading">Projects</h2></div><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div><div className="workspace-boundary"><strong>Read-only project metadata</strong><span>NexusOS does not execute, edit, or delete project files from this view.</span></div>{error && <ViewError label="Projects" message={error} onRetry={() => void refresh()} />}{loading ? <ViewLoading label="projects" /> : items.length === 0 ? <ViewEmpty title="No projects found" description="Projects are discovered from approved roots using safe marker files and Git metadata." /> : <div className="workspace-grid">{items.map((item) => <article className="workspace-card project-card" key={item.id}><div className="workspace-card-icon" aria-hidden="true">◈</div><div><strong>{item.name}</strong><span>{item.project_type} · {item.path}</span><small>{item.repository_id ? "Git repository detected" : "Project metadata only"} · {formatViewDate(item.modified_at)}</small></div></article>)}</div>}</section>;
}
