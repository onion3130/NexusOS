"use client";

import { useCallback, useEffect, useId, useState, type FormEvent, type ReactNode } from "react";
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

type AdminSection = "overview" | "ai" | "operations" | "host";

type AdminNavigateTarget =
  | "assistant"
  | "maintenance"
  | "notifications"
  | "sources"
  | "plugins"
  | "files"
  | "docker";

type AdminWorkspaceProps = {
  onOpenAssistant?: () => void;
  onNavigate?: (target: AdminNavigateTarget) => void;
};

function StatusMetric({ label, card, tone, delay = 0 }: { label: string; card: AdminStatusCard; tone: string; delay?: number }) {
  return (
    <article className="metric-card admin-status-metric admin-fade-in" style={{ animationDelay: `${delay}ms` }}>
      <div className={`metric-indicator ${tone} ${card.state === "degraded" ? "warning" : ""}`} />
      <p>{label}</p>
      <strong>{card.value}</strong>
      <span>{card.detail}</span>
    </article>
  );
}

function SectionCard({
  id,
  eyebrow,
  title,
  description,
  badge,
  badgeState = "ready",
  children,
  open,
  onToggle,
}: {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
  badge?: string;
  badgeState?: "ready" | "disabled" | "attention";
  children: ReactNode;
  open: boolean;
  onToggle: () => void;
}) {
  const bodyId = `${id}-body`;
  return (
    <section className={`admin-section-card admin-fade-in${open ? " is-open" : ""}`} aria-labelledby={`${id}-title`}>
      <button
        aria-controls={bodyId}
        aria-expanded={open}
        className="admin-section-toggle"
        onClick={onToggle}
        type="button"
      >
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h3 id={`${id}-title`}>{title}</h3>
          <p>{description}</p>
        </div>
        <div className="admin-section-toggle-meta">
          {badge && (
            <span className="admin-nim-status-pill" data-state={badgeState}>
              {badge}
            </span>
          )}
          <span aria-hidden="true" className="admin-chevron">
            {open ? "▾" : "▸"}
          </span>
        </div>
      </button>
      <div className="admin-section-body" id={bodyId} hidden={!open}>
        {children}
      </div>
    </section>
  );
}

function OperationTile({
  icon,
  title,
  detail,
  status,
  onClick,
}: {
  icon: string;
  title: string;
  detail: string;
  status: string;
  onClick: () => void;
}) {
  return (
    <button className="admin-op-tile" onClick={onClick} type="button">
      <span aria-hidden="true" className="admin-op-icon">
        {icon}
      </span>
      <strong>{title}</strong>
      <span>{detail}</span>
      <em>{status}</em>
    </button>
  );
}

export function AdminWorkspace({ onOpenAssistant, onNavigate }: AdminWorkspaceProps = {}) {
  const baseId = useId();
  const [section, setSection] = useState<AdminSection>("overview");
  const [nimOpen, setNimOpen] = useState(true);
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
  const [showAdvanced, setShowAdvanced] = useState(false);

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
          ? "NVIDIA NIM is saved and active. Open the Assistant to chat — no SSH or restart required."
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

  function go(target: AdminNavigateTarget) {
    onNavigate?.(target);
  }

  const configured = Boolean(status?.nvidia_nim.configured);
  const source = status?.nvidia_nim.source ?? "none";
  const canSave = Boolean(model.trim()) && (Boolean(apiKey.trim()) || (configured && source === "browser"));
  const sections: Array<{ id: AdminSection; label: string; hint: string }> = [
    { id: "overview", label: "Overview", hint: "Health at a glance" },
    { id: "ai", label: "AI setup", hint: "NVIDIA NIM" },
    { id: "operations", label: "Operations", hint: "Web control center" },
    { id: "host", label: "Host only", hint: "What still needs SSH" },
  ];

  return (
    <section aria-labelledby="admin-heading" className="workspace-view section-block admin-workspace">
      <div className="section-heading admin-top">
        <div>
          <p className="eyebrow">Owner control center</p>
          <h2 id="admin-heading">Admin</h2>
        </div>
        <button className="refresh-button" disabled={loading || saving || testing} onClick={() => void refresh()} type="button">
          {loading ? "Checking…" : "Refresh"}
        </button>
      </div>

      <p className="workspace-help admin-lead">
        Day-to-day setup lives here and in linked workspaces — no terminal for normal AI, backups, notifications testing, sources, or plugins.
        Install, upgrades, and host secrets stay on the Pi for safety.
      </p>

      <nav aria-label="Admin sections" className="admin-section-nav">
        {sections.map((item) => (
          <button
            aria-current={section === item.id ? "page" : undefined}
            className={`admin-section-nav-item${section === item.id ? " active" : ""}`}
            key={item.id}
            onClick={() => setSection(item.id)}
            type="button"
          >
            <strong>{item.label}</strong>
            <span>{item.hint}</span>
          </button>
        ))}
      </nav>

      {error && (
        <div className="inline-state error-state admin-fade-in" role="alert">
          <strong>Admin problem.</strong>
          <span>{error}</span>
          <button className="text-button" onClick={() => void refresh()} type="button">
            Retry
          </button>
        </div>
      )}
      {notice && (
        <div className="inline-state success-state admin-fade-in" role="status">
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
          {["System", "AI provider", "Storage", "Embeddings"].map((label) => (
            <div className="metric-card skeleton-card" key={label}>
              <span className="skeleton-line short" />
              <span className="skeleton-line" />
              <span className="skeleton-line tiny" />
            </div>
          ))}
        </div>
      ) : status ? (
        <div className="admin-panel-stage" key={section}>
          {section === "overview" && (
            <div className="admin-stack">
              <div className="metric-grid">
                <StatusMetric card={status.system} delay={0} label="System status" tone="green" />
                <StatusMetric card={status.ai_provider} delay={40} label="AI provider" tone="purple" />
                <StatusMetric card={status.storage} delay={80} label="Storage" tone="blue" />
                <StatusMetric card={status.embedding_provider} delay={120} label="Embeddings" tone="orange" />
              </div>
              <div className="admin-status-footnote admin-fade-in">
                <span>Version {status.version}</span>
                <span>Migration {status.migration_head}</span>
                <span>NIM {configured ? `· ${status.nvidia_nim.model ?? "configured"}` : "· not connected"}</span>
                <span>Checked {new Date(status.checked_at).toLocaleTimeString()}</span>
              </div>

              <div className="admin-summary-grid">
                <article className="admin-summary-card admin-fade-in">
                  <p className="eyebrow">Do this in the browser</p>
                  <h3>No terminal needed</h3>
                  <ul>
                    <li>Connect / test / update / disable NVIDIA NIM</li>
                    <li>Backups, restore, retention (Maintenance)</li>
                    <li>Notification test-send status</li>
                    <li>Sources upload, import, sync</li>
                    <li>Plugin rescan and lifecycle</li>
                    <li>Tasks, notes, calendar, finance, media</li>
                  </ul>
                  <div className="admin-nim-actions">
                    <button className="primary-button" onClick={() => setSection("ai")} type="button">
                      Set up AI
                    </button>
                    <button className="refresh-button" onClick={() => setSection("operations")} type="button">
                      Browse operations
                    </button>
                  </div>
                </article>
                <article className="admin-summary-card admin-fade-in" style={{ animationDelay: "60ms" }}>
                  <p className="eyebrow">Still on the Pi host</p>
                  <h3>First install & advanced</h3>
                  <ul>
                    <li>Docker install, image rebuild, compose upgrades</li>
                    <li>JWT secret and base <code>.env</code> creation</li>
                    <li>Email/push channel secrets (env for now)</li>
                    <li>Workspace/media roots, backup encryption keys</li>
                    <li>Owner bootstrap and DB migration apply</li>
                  </ul>
                  <button className="text-button" onClick={() => setSection("host")} type="button">
                    See full host-only list
                  </button>
                </article>
              </div>
            </div>
          )}

          {section === "ai" && (
            <div className="admin-stack">
              <SectionCard
                badge={configured ? "Active" : "Not connected"}
                badgeState={configured ? "ready" : "disabled"}
                description={
                  configured
                    ? `Model: ${status.nvidia_nim.model ?? "configured"} · ${
                        source === "browser"
                          ? "Configured from this Admin panel"
                          : source === "environment"
                            ? "Configured by server environment"
                            : "Not configured"
                      }`
                    : options?.help_text ?? "Add your NVIDIA API Catalog key and choose a model. No terminal required."
                }
                eyebrow="Step-by-step AI setup"
                id={`${baseId}-nim`}
                onToggle={() => setNimOpen((value) => !value)}
                open={nimOpen}
                title={configured ? "NVIDIA NIM connected" : "Connect NVIDIA NIM"}
              >
                {status.nvidia_nim.restart_required && (
                  <p className="form-help admin-fade-in">Worker is applying the latest saved configuration automatically.</p>
                )}

                <ol className="admin-setup-steps">
                  <li>
                    <strong>1 · Get an NVIDIA API key</strong>
                    <span>
                      Open{" "}
                      <a href="https://build.nvidia.com/" rel="noreferrer" target="_blank">
                        build.nvidia.com
                      </a>
                      , sign in, and create an API Catalog key.
                    </span>
                  </li>
                  <li>
                    <strong>2 · Choose a model</strong>
                    <span>Pick a recommended preset, or enter a hosted model id from NVIDIA.</span>
                  </li>
                  <li>
                    <strong>3 · Test, then save</strong>
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

                  <div className={`admin-collapse${embeddings ? " is-open" : ""}`}>
                    {embeddings && (
                      <div className="admin-model-block admin-fade-in">
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
                  </div>

                  <button className="text-button admin-advanced-toggle" onClick={() => setShowAdvanced((value) => !value)} type="button">
                    {showAdvanced ? "Hide technical details" : "Show technical details"}
                  </button>
                  <div className={`admin-collapse${showAdvanced ? " is-open" : ""}`}>
                    {showAdvanced && (
                      <p className="form-help admin-fade-in">
                        Hosted endpoint: <code>{options?.chat_endpoint ?? "https://integrate.api.nvidia.com/v1/chat/completions"}</code>.
                        Keys are encrypted under the private data volume, never written to SQLite, and never returned to the browser. Private and
                        loopback provider targets stay blocked. The worker reloads this configuration automatically.
                      </p>
                    )}
                  </div>

                  {testResult && (
                    <div className={`inline-state admin-fade-in ${testResult.ok ? "success-state" : "error-state"}`} role="status">
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
              </SectionCard>
            </div>
          )}

          {section === "operations" && (
            <div className="admin-stack">
              <p className="workspace-help admin-fade-in">
                These controls already live in the web UI. Admin is the map — open the workspace you need without leaving the browser.
              </p>
              <div className="admin-op-grid">
                <OperationTile
                  detail="Backups, integrity checks, restore, retention"
                  icon="⚙"
                  onClick={() => go("maintenance")}
                  status="Web · confirmation required"
                  title="Maintenance"
                />
                <OperationTile
                  detail="Email/push status and test delivery"
                  icon="♢"
                  onClick={() => go("notifications")}
                  status="Web · secrets still in env"
                  title="Notifications"
                />
                <OperationTile
                  detail="Upload, import, sync approved files"
                  icon="◇"
                  onClick={() => go("sources")}
                  status="Web · full control"
                  title="Sources"
                />
                <OperationTile
                  detail="Rescan and manage trusted plugins"
                  icon="◇"
                  onClick={() => go("plugins")}
                  status="Web · operator plugins"
                  title="Plugins"
                />
                <OperationTile
                  detail="Approved-root file metadata"
                  icon="▤"
                  onClick={() => go("files")}
                  status="Web · read-only"
                  title="Files"
                />
                <OperationTile
                  detail="Container listing when socket is enabled"
                  icon="▣"
                  onClick={() => go("docker")}
                  status="Web · optional host setup"
                  title="Docker view"
                />
                <OperationTile
                  detail="Chat with your configured model"
                  icon="✦"
                  onClick={() => go("assistant")}
                  status={configured ? "Ready" : "Needs AI setup"}
                  title="Assistant"
                />
              </div>
            </div>
          )}

          {section === "host" && (
            <div className="admin-stack">
              <article className="admin-host-card admin-fade-in">
                <p className="eyebrow">Intentionally host-side</p>
                <h3>What still needs SSH or the Pi terminal</h3>
                <p>
                  NexusOS keeps high-risk host control out of the browser. These are one-time or advanced operator tasks, not daily use.
                </p>
                <div className="admin-host-grid">
                  <div>
                    <strong>Install & updates</strong>
                    <ul>
                      <li>Clone/pull the repo and rebuild Docker images</li>
                      <li>Apply database migrations (<code>alembic upgrade</code>)</li>
                      <li>Bootstrap the first owner account</li>
                      <li>Hardened proxy / systemd unit setup</li>
                    </ul>
                  </div>
                  <div>
                    <strong>Secrets & paths</strong>
                    <ul>
                      <li>Create <code>.env</code> and set <code>JWT_SECRET</code></li>
                      <li>Email/push SMTP & ntfy credentials</li>
                      <li>Backup encryption / replication keys</li>
                      <li>
                        <code>WORKSPACE_ROOTS</code>, <code>MEDIA_ROOTS</code>, <code>PLUGINS_DIR</code>
                      </li>
                    </ul>
                  </div>
                  <div>
                    <strong>Never from the browser</strong>
                    <ul>
                      <li>Arbitrary shell, reboot, package installs</li>
                      <li>Docker daemon control / compose rebuild</li>
                      <li>Editing host filesystem paths from clients</li>
                      <li>Exposing private provider endpoints</li>
                    </ul>
                  </div>
                </div>
                <p className="form-help">
                  Daily AI setup, assistant use, productivity apps, source sync, and confirmed maintenance actions are already web-native.
                  Host-only items stay terminal on purpose so a stolen session cannot reconfigure the machine.
                </p>
              </article>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
