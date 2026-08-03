"use client";

import { useCallback, useEffect, useState } from "react";
import { listDockerContainers, type DockerContainerView } from "../lib/workspace-views";
import { formatViewDate, ViewEmpty, ViewError, ViewLoading } from "./workspace-view-shared";

export function DockerWorkspace() {
  const [items, setItems] = useState<DockerContainerView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => { setLoading(true); try { const result = await listDockerContainers(); setItems(result.items); setError(result.available ? null : result.reason ?? "Docker metadata unavailable"); } catch (reason) { setError(reason instanceof Error ? reason.message : "Docker unavailable"); } finally { setLoading(false); } }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return <section aria-labelledby="docker-heading" className="workspace-view section-block"><div className="section-heading"><div><p className="eyebrow">Safe runtime metadata</p><h2 id="docker-heading">Docker</h2></div><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div><div className="workspace-boundary"><strong>Inspection only</strong><span>NexusOS can inspect approved container metadata, but cannot start, stop, remove, or modify containers here.</span></div>{error && <ViewError label="Docker" message={error} onRetry={() => void refresh()} />}{loading ? <ViewLoading label="containers" /> : items.length === 0 ? <ViewEmpty title="Docker metadata unavailable" description="The API needs an explicitly configured read-only Docker socket boundary to inspect containers." /> : <div className="workspace-grid">{items.map((item) => <article className="workspace-card project-card" key={item.id}><div className={`workspace-card-icon ${item.state === "running" ? "workspace-ok" : "workspace-warning"}`} aria-hidden="true">▣</div><div><strong>{item.name}</strong><span>{item.state}{item.health ? ` · ${item.health}` : ""} · {item.image}</span><small>{item.compose_service ? `Compose ${item.compose_service} · ` : ""}{item.ports.length ? item.ports.join(", ") : "No published ports"} · {formatViewDate(item.created_at)}</small></div></article>)}</div>}</section>;
}
