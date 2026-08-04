"use client";

import { useCallback, useEffect, useState } from "react";
import { readAdminStatus, type AdminStatus, type AdminStatusCard } from "../lib/admin";

function StatusMetric({ label, card, tone }: { label: string; card: AdminStatusCard; tone: string }) {
  return <article className="metric-card admin-status-metric">
    <div className={`metric-indicator ${tone} ${card.state === "degraded" ? "warning" : ""}`} />
    <p>{label}</p>
    <strong>{card.value}</strong>
    <span>{card.detail}</span>
  </article>;
}

export function AdminStatusPanel() {
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setStatus(await readAdminStatus());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Admin status unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  return <section aria-labelledby="admin-status-heading" className="section-block admin-status-panel">
    <div className="section-heading">
      <div><p className="eyebrow">Owner controls</p><h2 id="admin-status-heading">Admin status</h2></div>
      <button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Checking…" : "Refresh"}</button>
    </div>
    <p className="admin-status-copy">Read-only operational status. AI credentials and runtime configuration stay on the server.</p>
    {error && !status ? <div className="inline-state error-state" role="alert"><strong>Admin status unavailable.</strong><span>Check the authenticated API connection and try again.</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div> : loading && !status ? <div className="metric-grid" role="status" aria-label="Loading admin status">{["System", "AI provider", "Storage"].map((label) => <div className="metric-card skeleton-card" key={label}><span className="skeleton-line short" /><span className="skeleton-line" /><span className="skeleton-line tiny" /></div>)}</div> : status ? <>
      {error && <div className="inline-state warning-state" role="status"><strong>Showing the last successful status.</strong><span>Refresh failed; automatic retry remains enabled.</span></div>}
      <div className="metric-grid">
        <StatusMetric card={status.system} label="System status" tone="green" />
        <StatusMetric card={status.ai_provider} label="AI provider" tone="purple" />
        <StatusMetric card={status.storage} label="Storage" tone="blue" />
        <StatusMetric card={status.embedding_provider} label="Embeddings" tone="orange" />
      </div>
      <div className="admin-status-footnote"><span>Version {status.version}</span><span>Migration {status.migration_head}</span><span>Checked {new Date(status.checked_at).toLocaleTimeString()}</span></div>
    </> : null}
  </section>;
}
