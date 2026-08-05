"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  configureNvidiaNim,
  disableNvidiaNim,
  readAdminStatus,
  readNimOptions,
  testNvidiaNim,
  type AdminStatus,
  type AdminStatusCard,
  type NimOptions,
  type NimTestResult,
} from "../lib/admin";

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

export function AdminWorkspace({ onOpenAssistant }: { onOpenAssistant?: () => void } = {}) {
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [options, setOptions] = useState<NimOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<NimTestResult | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("meta/llama-3.1-8b-instruct");
  const [customModel, setCustomModel] = useState(false);
  const [embeddings, setEmbeddings] = useState(false);
  const [embeddingModel, setEmbeddingModel] = useState("nvidia/nv-embedqa-e5-v5");
  const [customEmbedding, setCustomEmbedding] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [nextStatus, nextOptions] = await Promise.all([readAdminStatus(), readNimOptions()]);
      setStatus(nextStatus);
      setOptions(nextOptions);
      if (nextStatus.nvidia_nim.model) {
        const known = nextOptions.chat_models.some((item) => item.id === nextStatus.nvidia_nim.model);
        setModel(nextStatus.nvidia_nim.model);
        setCustomModel(!known);
      }
      setEmbeddings(nextStatus.nvidia_nim.embeddings_enabled);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Admin panel unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function saveNim(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    setTestResult(null);
    try {
      const payload: {
        api_key?: string;
        model: string;
        embeddings_enabled: boolean;
        embedding_model?: string;
      } = {
        model: model.trim(),
        embeddings_enabled: embeddings,
        embedding_model: embeddings ? embeddingModel.trim() : undefined,
      };
      if (apiKey.trim()) payload.api_key = apiKey.trim();
      const next = await configureNvidiaNim(payload);
      setStatus(next);
      setApiKey("");
      setNotice(
        next.nvidia_nim.configured
          ? "NVIDIA NIM is saved and active. Open the Assistant to chat — no SSH or container restart required."
          : "NVIDIA NIM settings saved.",
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "NVIDIA NIM setup failed");
    } finally {
      setSaving(false);
    }
  }

  async function runTest() {
    setTesting(true);
    setError(null);
    setTestResult(null);
    try {
      const payload: { api_key?: string; model?: string } = { model: model.trim() || undefined };
      if (apiKey.trim()) payload.api_key = apiKey.trim();
      setTestResult(await testNvidiaNim(payload));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "NVIDIA NIM test failed");
    } finally {
      setTesting(false);
    }
  }

  async function disableNim() {
    if (!window.confirm("Disable browser-managed NVIDIA NIM? The Assistant will stop using this provider until you reconnect it.")) {
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    setTestResult(null);
    try {
      setStatus(await disableNvidiaNim());
      setApiKey("");
      setNotice("NVIDIA NIM disabled. Environment-based configuration is unchanged if present.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "NVIDIA NIM disable failed");
    } finally {
      setSaving(false);
    }
  }

  const configured = Boolean(status?.nvidia_nim.configured);
  const source = status?.nvidia_nim.source ?? "none";
  const canSave = Boolean(model.trim()) && (Boolean(apiKey.trim()) || (configured && source === "browser"));

  return (
    <section aria-labelledby="admin-heading" className="workspace-view section-block admin-workspace">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Owner controls</p>
          <h2 id="admin-heading">Admin</h2>
        </div>
        <button className="refresh-button" disabled={loading || saving || testing} onClick={() => void refresh()} type="button">
          {loading ? "Checking…" : "Refresh"}
        </button>
      </div>
      <p className="workspace-help">
        Use this panel to connect NVIDIA NIM and review system health. You do not need SSH or terminal commands for normal AI setup.
        API keys are encrypted on the Pi, never stored in the browser, and never returned by the API.
      </p>

      {error && (
        <div className="inline-state error-state" role="alert">
          <strong>Admin problem.</strong>
          <span>{error}</span>
          <button className="text-button" onClick={() => void refresh()} type="button">
            Retry
          </button>
        </div>
      )}
      {notice && (
        <div className="inline-state success-state" role="status">
          <strong>Saved.</strong>
          <span>{notice}</span>
          {onOpenAssistant && (
            <button className="text-button" onClick={onOpenAssistant} type="button">
              Open Assistant
            </button>
          )}
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
            <span>Checked {new Date(status.checked_at).toLocaleTimeString()}</span>
          </div>

          <div className="admin-nim-panel">
            <div className="admin-nim-header">
              <div>
                <p className="eyebrow">Step-by-step AI setup</p>
                <h3>{configured ? "NVIDIA NIM connected" : "Connect NVIDIA NIM"}</h3>
                <p>
                  {configured
                    ? `Model: ${status.nvidia_nim.model ?? "configured"} · ${
                        source === "browser"
                          ? "Configured from this Admin panel"
                          : source === "environment"
                            ? "Configured by server environment"
                            : "Not configured"
                      }`
                    : options?.help_text ?? "Add your NVIDIA API Catalog key and choose a model. No terminal required."}
                </p>
                {status.nvidia_nim.restart_required && (
                  <p className="form-help">Worker is picking up the latest saved configuration automatically.</p>
                )}
              </div>
              <div className="admin-nim-status-pill" data-state={configured ? "ready" : "disabled"}>
                {configured ? "Active" : "Not connected"}
              </div>
            </div>

            <ol className="admin-setup-steps">
              <li>
                <strong>Get a free or paid NVIDIA API key</strong>
                <span>
                  Open{" "}
                  <a href="https://build.nvidia.com/" rel="noreferrer" target="_blank">
                    build.nvidia.com
                  </a>
                  , sign in, and create an API Catalog key.
                </span>
              </li>
              <li>
                <strong>Paste the key and choose a model</strong>
                <span>Use a recommended preset below, or enter a hosted model id from NVIDIA.</span>
              </li>
              <li>
                <strong>Test, then save</strong>
                <span>Test checks the connection. Save encrypts the key on this device and enables the Assistant immediately.</span>
              </li>
            </ol>

            <form className="admin-nim-form" onSubmit={(event) => void saveNim(event)}>
              <label>
                NVIDIA API key
                <input
                  autoComplete="new-password"
                  minLength={configured && source === "browser" ? 0 : 20}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={configured && source === "browser" ? "Leave blank to keep the saved key" : "nvapi-…"}
                  required={!configured || source !== "browser"}
                  type="password"
                  value={apiKey}
                />
              </label>

              <div className="admin-model-block">
                <div className="admin-model-heading">
                  <strong>Chat model</strong>
                  <button className="text-button" onClick={() => setCustomModel((value) => !value)} type="button">
                    {customModel ? "Use presets" : "Custom model id"}
                  </button>
                </div>
                {customModel ? (
                  <label>
                    Model id
                    <input maxLength={160} onChange={(event) => setModel(event.target.value)} required value={model} />
                  </label>
                ) : (
                  <div className="admin-preset-grid" role="listbox" aria-label="Chat model presets">
                    {(options?.chat_models ?? []).map((preset) => {
                      const selected = model === preset.id;
                      return (
                        <button
                          aria-selected={selected}
                          className={`admin-preset-card${selected ? " selected" : ""}`}
                          key={preset.id}
                          onClick={() => setModel(preset.id)}
                          type="button"
                        >
                          <strong>
                            {preset.label}
                            {preset.recommended ? <span className="admin-recommended">Recommended</span> : null}
                          </strong>
                          <span>{preset.description}</span>
                          <code>{preset.id}</code>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <label className="checkbox-row">
                <input checked={embeddings} onChange={(event) => setEmbeddings(event.target.checked)} type="checkbox" />
                Enable semantic embeddings for note search
              </label>

              {embeddings && (
                <div className="admin-model-block">
                  <div className="admin-model-heading">
                    <strong>Embedding model</strong>
                    <button className="text-button" onClick={() => setCustomEmbedding((value) => !value)} type="button">
                      {customEmbedding ? "Use presets" : "Custom model id"}
                    </button>
                  </div>
                  {customEmbedding ? (
                    <label>
                      Embedding model id
                      <input maxLength={160} onChange={(event) => setEmbeddingModel(event.target.value)} required value={embeddingModel} />
                    </label>
                  ) : (
                    <div className="admin-preset-grid" role="listbox" aria-label="Embedding model presets">
                      {(options?.embedding_models ?? []).map((preset) => {
                        const selected = embeddingModel === preset.id;
                        return (
                          <button
                            aria-selected={selected}
                            className={`admin-preset-card${selected ? " selected" : ""}`}
                            key={preset.id}
                            onClick={() => setEmbeddingModel(preset.id)}
                            type="button"
                          >
                            <strong>
                              {preset.label}
                              {preset.recommended ? <span className="admin-recommended">Recommended</span> : null}
                            </strong>
                            <span>{preset.description}</span>
                            <code>{preset.id}</code>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              <p className="form-help">
                Hosted endpoint: <code>{options?.chat_endpoint ?? "https://integrate.api.nvidia.com/v1/chat/completions"}</code>. Private and
                loopback provider targets stay blocked by design. The worker reloads this configuration automatically.
              </p>

              {testResult && (
                <div className={`inline-state ${testResult.ok ? "success-state" : "error-state"}`} role="status">
                  <strong>{testResult.ok ? "Connection OK" : "Connection failed"}</strong>
                  <span>{testResult.detail}</span>
                </div>
              )}

              <div className="admin-nim-actions">
                <button className="primary-button" disabled={saving || !canSave} type="submit">
                  {saving ? "Saving…" : configured ? "Save NIM settings" : "Connect NVIDIA NIM"}
                </button>
                <button className="refresh-button" disabled={testing || saving} onClick={() => void runTest()} type="button">
                  {testing ? "Testing…" : "Test connection"}
                </button>
                {source === "browser" && (
                  <button className="text-button danger-text" disabled={saving || testing} onClick={() => void disableNim()} type="button">
                    Disable NIM
                  </button>
                )}
                {onOpenAssistant && configured && (
                  <button className="text-button" onClick={onOpenAssistant} type="button">
                    Open Assistant
                  </button>
                )}
              </div>
            </form>
          </div>
        </>
      ) : null}
    </section>
  );
}
