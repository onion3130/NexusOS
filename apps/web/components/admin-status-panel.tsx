"use client";

import { useCallback, useEffect, useState } from "react";
import { readAdminStatus, type AdminStatus, type AdminStatusCard } from "../lib/admin";

function StatusMetric({ label, card, tone }: { label: string; card: AdminStatusCard; tone: string }) {
  return (
    <article className="metric-card admin-status-metric">
      <div className={`metric-indicator ${tone} ${card.state === "degraded" ? "warning" : ""}`} />
      <p>{label}</p>
      <strong>{card.value}</strong>
      <span>{card.detail}</span>
    </article>
  );
}

/** Compact owner status summary for the overview; full setup lives in Admin. */
export function AdminStatusPanel({ onOpenAdmin }: { onOpenAdmin?: () => void } = {}) {
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

  return (
    <section aria-labelledby="admin-status-heading" className="section-block admin-status-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Owner controls</p>
          <h2 id="admin-status-heading">Admin status</h2>
        </div>
        <div className="notes-actions">
          {onOpenAdmin && (
            <button className="primary-button" onClick={onOpenAdmin} type="button">
              {status?.nvidia_nim.configured ? "Open Admin" : "Connect NVIDIA NIM"}
            </button>
          )}
          <button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">
            {loading ? "Checking…" : "Refresh"}
          </button>
        </div>
      </div>
      <p className="admin-status-copy">
        Quick health view for owners. Connect or update NVIDIA NIM from the Admin workspace — no SSH required.
      </p>
      {error && (
        <div className="inline-state error-state" role="alert">
          <strong>Status unavailable.</strong>
          <span>{error}</span>
        </div>
      )}
      {loading && !status ? (
        <div className="metric-grid" role="status" aria-label="Loading admin status">
          {["System", "AI provider", "Storage"].map((label) => (
            <div className="metric-card skeleton-card" key={label}>
              <span className="skeleton-line short" />
              <span className="skeleton-line" />
              <span className="skeleton-line tiny" />
            </div>
          ))}
        </div>
      ) : status ? (
        <>
          <div className="metric-grid">
            <StatusMetric card={status.system} label="System status" tone="green" />
            <StatusMetric card={status.ai_provider} label="AI provider" tone="purple" />
            <StatusMetric card={status.storage} label="Storage" tone="blue" />
            <StatusMetric card={status.embedding_provider} label="Embeddings" tone="orange" />
          </div>
          <div className="admin-status-footnote">
            <span>Version {status.version}</span>
            <span>Migration {status.migration_head}</span>
            <span>
              NIM {status.nvidia_nim.configured ? `· ${status.nvidia_nim.model ?? "configured"}` : "· not connected"}
            </span>
            <span>Checked {new Date(status.checked_at).toLocaleTimeString()}</span>
          </div>
        </>
      ) : null}
    </section>
  );
}
