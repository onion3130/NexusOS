"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { configureNvidiaNim, disableNvidiaNim, readAdminStatus, type AdminStatus, type AdminStatusCard } from "../lib/admin";

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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("meta/llama-3.1-8b-instruct");
  const [embeddings, setEmbeddings] = useState(false);
  const [embeddingModel, setEmbeddingModel] = useState("nvidia/nv-embedqa-e5-v5");
  const [showSetup, setShowSetup] = useState(false);

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

  async function saveNim(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const next = await configureNvidiaNim({ api_key: apiKey, model, embeddings_enabled: embeddings, embedding_model: embeddings ? embeddingModel : undefined });
      setStatus(next);
      setApiKey("");
      setShowSetup(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "NVIDIA NIM setup failed");
    } finally {
      setSaving(false);
    }
  }

  async function disableNim() {
    setSaving(true);
    setError(null);
    try {
      setStatus(await disableNvidiaNim());
      setApiKey("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "NVIDIA NIM disable failed");
    } finally {
      setSaving(false);
    }
  }

  return <section aria-labelledby="admin-status-heading" className="section-block admin-status-panel">
    <div className="section-heading">
      <div><p className="eyebrow">Owner controls</p><h2 id="admin-status-heading">Admin status</h2></div>
      <button className="refresh-button" disabled={loading || saving} onClick={() => void refresh()} type="button">{loading ? "Checking…" : "Refresh"}</button>
    </div>
    <p className="admin-status-copy">Read-only operational status. NIM credentials are encrypted on this server and are never returned to the browser.</p>
    {error && <div className="inline-state error-state" role="alert"><strong>Provider setup problem.</strong><span>{error}</span></div>}
    {loading && !status ? <div className="metric-grid" role="status" aria-label="Loading admin status">{["System", "AI provider", "Storage"].map((label) => <div className="metric-card skeleton-card" key={label}><span className="skeleton-line short" /><span className="skeleton-line" /><span className="skeleton-line tiny" /></div>)}</div> : status ? <>
      <div className="metric-grid">
        <StatusMetric card={status.system} label="System status" tone="green" />
        <StatusMetric card={status.ai_provider} label="AI provider" tone="purple" />
        <StatusMetric card={status.storage} label="Storage" tone="blue" />
        <StatusMetric card={status.embedding_provider} label="Embeddings" tone="orange" />
      </div>
      <div className="admin-status-footnote"><span>Version {status.version}</span><span>Migration {status.migration_head}</span><span>Checked {new Date(status.checked_at).toLocaleTimeString()}</span></div>
      <div className="nim-setup-card">
        <div><p className="eyebrow">Secure provider setup</p><h3>{status.nvidia_nim.configured ? "NVIDIA NIM connected" : "Connect NVIDIA NIM"}</h3><p>{status.nvidia_nim.configured ? `Model: ${status.nvidia_nim.model ?? "configured"} · ${status.nvidia_nim.source === "browser" ? "Configured from this admin panel" : "Configured by server environment"}` : "Add your NVIDIA API Catalog key and model once. The key is encrypted on the Pi and never shown again."}</p>{status.nvidia_nim.restart_required && <p className="form-help">Restart the API and worker to activate the saved provider configuration.</p>}</div>
        <div className="nim-setup-actions">
          <button className="primary-button" disabled={saving} onClick={() => setShowSetup((open) => !open)} type="button">{showSetup ? "Cancel" : status.nvidia_nim.configured ? "Update NIM" : "Connect NIM"}</button>
          {status.nvidia_nim.source === "browser" && <button className="text-button danger-text" disabled={saving} onClick={() => void disableNim()} type="button">Disable</button>}
        </div>
      </div>
      {showSetup && <form className="nim-setup-form" onSubmit={(event) => void saveNim(event)}>
        <label>NVIDIA API key<input autoComplete="new-password" minLength={20} onChange={(event) => setApiKey(event.target.value)} placeholder="nvapi-…" required type="password" value={apiKey} /></label>
        <label>Chat model<input maxLength={160} onChange={(event) => setModel(event.target.value)} required value={model} /></label>
        <label className="checkbox-row"><input checked={embeddings} onChange={(event) => setEmbeddings(event.target.checked)} type="checkbox" /> Enable semantic embeddings</label>
        {embeddings && <label>Embedding model<input maxLength={160} onChange={(event) => setEmbeddingModel(event.target.value)} required value={embeddingModel} /></label>}
        <p className="form-help">The key is sent only to the authenticated Nexus API over this same-origin connection. It is not stored in SQLite, logs, or browser storage. Restarting the API and worker is recommended after changing provider settings.</p>
        <button className="primary-button" disabled={saving || !apiKey.trim()} type="submit">{saving ? "Encrypting…" : "Save encrypted configuration"}</button>
      </form>}
    </> : null}
  </section>;
}
