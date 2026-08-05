"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  configureNvidiaNim,
  disableNvidiaNim,
  listNvidiaModels,
  readAdminStatus,
  readNimOptions,
  readSoftwareUpdateStatus,
  requestSoftwareUpdate,
  testNvidiaNim,
  type AdminStatus,
  type NimChatPreset,
  type NimEmbeddingPreset,
  type NimModelCatalog,
  type NimOptions,
  type NimTestResult,
  type SoftwareUpdateStatus,
} from "../lib/admin";
import type { User } from "../lib/auth";
import { listAuditEvents, listBackups, readDeploymentStatus, type AuditEvent, type Backup, type DeploymentStatus } from "../lib/host-actions";
import { readSystemOverview, type HealthLevel, type SystemOverview } from "../lib/system";

type AdminPage = "dashboard" | "ai" | "updates" | "system" | "services" | "operations" | "host";

type AdminNavigateTarget =
  | "assistant"
  | "maintenance"
  | "notifications"
  | "sources"
  | "plugins"
  | "files"
  | "docker"
  | "overview";

type AdminWorkspaceProps = {
  user: User;
  onOpenAssistant?: () => void;
  onNavigate?: (target: AdminNavigateTarget) => void;
  onLogout?: () => void;
};

const NAV: Array<{ id: AdminPage; label: string; icon: string; hint: string }> = [
  { id: "dashboard", label: "Dashboard", icon: "◈", hint: "Summary & tables" },
  { id: "ai", label: "AI / NIM", icon: "✦", hint: "Provider setup" },
  { id: "updates", label: "Updates", icon: "↻", hint: "GitHub pull & rebuild" },
  { id: "system", label: "System", icon: "◎", hint: "Live telemetry" },
  { id: "services", label: "Services", icon: "⌁", hint: "Stack units" },
  { id: "operations", label: "Operations", icon: "⚙", hint: "Quick actions" },
  { id: "host", label: "Host only", icon: "⌂", hint: "SSH-bound tasks" },
];

function tone(level: HealthLevel | string | undefined): string {
  if (level === "critical" || level === "danger") return "critical";
  if (level === "warning" || level === "degraded" || level === "attention") return "warning";
  if (level === "unavailable" || level === "disabled") return "muted";
  return "healthy";
}

function SummaryCard({
  label,
  value,
  detail,
  level = "healthy",
}: {
  label: string;
  value: string;
  detail: string;
  level?: string;
}) {
  return (
    <article className={`admin-summary-metric admin-summary-${tone(level)}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

function DataTable({
  columns,
  rows,
  empty,
}: {
  columns: string[];
  rows: Array<Array<ReactNode>>;
  empty: string;
}) {
  if (rows.length === 0) {
    return <div className="admin-table-empty">{empty}</div>;
  }
  return (
    <div className="admin-table-wrap">
      <table className="admin-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Panel({ title, eyebrow, actions, children }: { title: string; eyebrow?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="admin-panel-card">
      <div className="admin-panel-card-head">
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h3>{title}</h3>
        </div>
        {actions && <div className="admin-panel-card-actions">{actions}</div>}
      </div>
      <div className="admin-panel-card-body">{children}</div>
    </section>
  );
}

export function AdminWorkspace({ user, onOpenAssistant, onNavigate, onLogout }: AdminWorkspaceProps) {
  const [page, setPage] = useState<AdminPage>("dashboard");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [options, setOptions] = useState<NimOptions | null>(null);
  const [updateStatus, setUpdateStatus] = useState<SoftwareUpdateStatus | null>(null);
  const [system, setSystem] = useState<SystemOverview | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [backups, setBackups] = useState<Backup[]>([]);
  const [deployment, setDeployment] = useState<DeploymentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [updateBusy, setUpdateBusy] = useState(false);
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
  const [liveCatalog, setLiveCatalog] = useState<NimModelCatalog | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelFilter, setModelFilter] = useState("");
  const [modelsError, setModelsError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [nextStatus, nextOptions, nextUpdate, nextSystem, nextAudit, nextBackups, nextDeployment] = await Promise.all([
        readAdminStatus(),
        readNimOptions(),
        readSoftwareUpdateStatus(),
        readSystemOverview().catch(() => null),
        listAuditEvents().catch(() => [] as AuditEvent[]),
        listBackups().catch(() => [] as Backup[]),
        readDeploymentStatus().catch(() => null),
      ]);
      setStatus(nextStatus);
      setOptions(nextOptions);
      setUpdateStatus(nextUpdate);
      setSystem(nextSystem);
      setAudit(nextAudit);
      setBackups(nextBackups);
      setDeployment(nextDeployment);
      if (nextStatus.nvidia_nim.model) {
        setModel(nextStatus.nvidia_nim.model);
      }
      setEmbeddings(nextStatus.nvidia_nim.embeddings_enabled);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Admin console unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!updateStatus || !["queued", "running"].includes(updateStatus.state)) return;
    const timer = window.setInterval(() => {
      void readSoftwareUpdateStatus()
        .then(setUpdateStatus)
        .catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [updateStatus?.state]);

  useEffect(() => {
    if (page !== "system" && page !== "dashboard") return;
    const timer = window.setInterval(() => {
      void readSystemOverview()
        .then(setSystem)
        .catch(() => undefined);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [page]);

  const navItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return NAV;
    return NAV.filter((item) => `${item.label} ${item.hint}`.toLowerCase().includes(q));
  }, [query]);

  const configured = Boolean(status?.nvidia_nim.configured);
  const source = status?.nvidia_nim.source ?? "none";
  const canSave = Boolean(model.trim()) && (Boolean(apiKey.trim()) || (configured && source === "browser"));
  const chatModels: NimChatPreset[] = liveCatalog?.chat_models ?? options?.chat_models ?? [];
  const embeddingModels: NimEmbeddingPreset[] = liveCatalog?.embedding_models ?? options?.embedding_models ?? [];
  const filteredChatModels = useMemo(() => {
    const q = modelFilter.trim().toLowerCase();
    if (!q) return chatModels;
    return chatModels.filter((item) => `${item.id} ${item.label} ${item.description}`.toLowerCase().includes(q));
  }, [chatModels, modelFilter]);
  const filteredEmbeddingModels = useMemo(() => {
    const q = modelFilter.trim().toLowerCase();
    if (!q) return embeddingModels;
    return embeddingModels.filter((item) => `${item.id} ${item.label} ${item.description}`.toLowerCase().includes(q));
  }, [embeddingModels, modelFilter]);

  async function saveNim(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    setTestResult(null);
    try {
      const payload: { api_key?: string; model: string; embeddings_enabled: boolean; embedding_model?: string } = {
        model: model.trim(),
        embeddings_enabled: embeddings,
        embedding_model: embeddings ? embeddingModel.trim() : undefined,
      };
      if (apiKey.trim()) payload.api_key = apiKey.trim();
      const next = await configureNvidiaNim(payload);
      setStatus(next);
      setApiKey("");
      setNotice("NVIDIA NIM saved and active.");
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
    if (!window.confirm("Disable browser-managed NVIDIA NIM?")) return;
    setSaving(true);
    setError(null);
    try {
      setStatus(await disableNvidiaNim());
      setLiveCatalog(null);
      setNotice("NVIDIA NIM disabled.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Disable failed");
    } finally {
      setSaving(false);
    }
  }

  async function loadLiveModels(forceKey?: string) {
    const key = (forceKey ?? apiKey).trim();
    setLoadingModels(true);
    setModelsError(null);
    try {
      // Key is optional for the public catalog; include it when present so key-scoped lists work.
      const catalog = await listNvidiaModels(key || undefined);
      setLiveCatalog(catalog);
      const chatIds = catalog.chat_models.map((item) => item.id);
      const embedIds = catalog.embedding_models.map((item) => item.id);
      if (!chatIds.includes(model) && catalog.chat_models[0]) {
        const recommended = catalog.chat_models.find((item) => item.recommended) ?? catalog.chat_models[0];
        setModel(recommended.id);
        setCustomModel(false);
      }
      if (embeddings && !embedIds.includes(embeddingModel) && catalog.embedding_models[0]) {
        const recommended = catalog.embedding_models.find((item) => item.recommended) ?? catalog.embedding_models[0];
        setEmbeddingModel(recommended.id);
        setCustomEmbedding(false);
      }
      setNotice(catalog.detail);
    } catch (reason) {
      setModelsError(reason instanceof Error ? reason.message : "Failed to load NVIDIA models");
    } finally {
      setLoadingModels(false);
    }
  }

  useEffect(() => {
    if (page !== "ai") return;
    if (liveCatalog?.source === "live") return;
    void loadLiveModels();
    // Auto-load public/live catalog when opening AI setup.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  useEffect(() => {
    if (page !== "ai") return;
    const key = apiKey.trim();
    if (key.length < 20) return;
    const timer = window.setTimeout(() => {
      void loadLiveModels(key);
    }, 600);
    return () => window.clearTimeout(timer);
    // Reload after the user finishes typing a key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey, page]);

  async function runUpdate(action: "check" | "apply") {
    if (action === "apply") {
      const ok = window.confirm("Update NexusOS from GitHub now? Containers will rebuild and may briefly disconnect.");
      if (!ok) return;
    }
    setUpdateBusy(true);
    setError(null);
    try {
      setUpdateStatus(await requestSoftwareUpdate(action, action === "apply"));
      setNotice(action === "check" ? "Update check queued." : "Update queued on host agent.");
      setPage("updates");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Update request failed");
    } finally {
      setUpdateBusy(false);
    }
  }

  const systemRows = system
    ? [
        ["CPU", system.cpu.usage_percent === null ? "—" : `${system.cpu.usage_percent}%`, `${system.cpu.cpu_count ?? "—"} cores · load ${system.cpu.load_1m ?? "—"}`, system.cpu.health.label],
        ["Memory", system.memory.used_percent === null ? "—" : `${system.memory.used_percent}%`, "Used of system RAM", system.memory.health.label],
        ["Storage", system.storage.used_percent === null ? "—" : `${system.storage.used_percent}%`, "Data volume", system.storage.health.label],
        ["Temperature", system.temperature.celsius === null ? "—" : `${system.temperature.celsius.toFixed(1)}°C`, system.temperature.source_name ?? "thermal", system.temperature.health.label],
        ["Network", system.network.source.available ? "Online" : "Offline", `${system.network.interfaces.length} interface(s)`, system.network.health.label],
        ["Uptime", system.uptime.seconds === null ? "—" : `${Math.floor(system.uptime.seconds / 86400)}d ${Math.floor((system.uptime.seconds % 86400) / 3600)}h`, "Since boot", system.uptime.health.label],
      ]
    : [];

  const serviceRows = (system?.service_status.units ?? []).map((unit) => [
    unit.name,
    unit.kind,
    unit.state,
    unit.detail ?? "—",
    <span className={`admin-badge admin-badge-${tone(unit.health)}`} key={`${unit.name}-h`}>
      {unit.health}
    </span>,
  ]);

  const auditRows = audit.slice(0, 12).map((event) => [
    new Date(event.created_at).toLocaleString(),
    event.action,
    event.result,
    event.target ?? "—",
  ]);

  const backupRows = backups.slice(0, 8).map((backup) => [
    backup.status,
    `${(backup.size_bytes / 1024 / 1024).toFixed(2)} MB`,
    new Date(backup.created_at).toLocaleString(),
    backup.relative_path,
  ]);

  return (
    <div className="admin-console">
      <aside className="admin-console-sidebar" aria-label="Admin navigation">
        <div className="admin-console-brand">
          <div className="admin-console-mark">A</div>
          <div>
            <strong>Nexus Admin</strong>
            <span>Control center</span>
          </div>
        </div>
        <nav className="admin-console-nav">
          {navItems.map((item) => (
            <button
              aria-current={page === item.id ? "page" : undefined}
              className={`admin-console-nav-item${page === item.id ? " active" : ""}`}
              key={item.id}
              onClick={() => setPage(item.id)}
              type="button"
            >
              <span aria-hidden="true">{item.icon}</span>
              <span>
                <strong>{item.label}</strong>
                <em>{item.hint}</em>
              </span>
            </button>
          ))}
        </nav>
        <div className="admin-console-sidebar-footer">
          <button className="admin-console-exit" onClick={() => onNavigate?.("overview")} type="button">
            ← Back to workspace
          </button>
        </div>
      </aside>

      <div className="admin-console-main">
        <header className="admin-console-header">
          <div className="admin-console-search">
            <span aria-hidden="true">⌕</span>
            <input
              aria-label="Search admin sections"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search admin sections, filters, actions…"
              value={query}
            />
          </div>
          <div className="admin-console-header-actions">
            <button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">
              {loading ? "Refreshing…" : "Refresh data"}
            </button>
            <button className="primary-button" onClick={() => setPage("updates")} type="button">
              Updates
            </button>
            <div className="admin-console-profile">
              <strong>{user.username}</strong>
              <span>{user.roles.join(", ") || "owner"}</span>
            </div>
            {onLogout && (
              <button aria-label="Sign out" className="refresh-button" onClick={onLogout} type="button">
                Sign out
              </button>
            )}
          </div>
        </header>

        <div className="admin-console-body">
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
              <strong>Done.</strong>
              <span>{notice}</span>
            </div>
          )}

          {page === "dashboard" && (
            <div className="admin-console-stack">
              <div className="admin-console-title-row">
                <div>
                  <p className="eyebrow">Operations dashboard</p>
                  <h2>Admin overview</h2>
                </div>
                <span className="admin-console-updated">{loading ? "Loading…" : `Updated ${status ? new Date(status.checked_at).toLocaleTimeString() : "—"}`}</span>
              </div>

              <div className="admin-summary-grid-4">
                <SummaryCard
                  detail={status?.system.detail ?? "Loading"}
                  label="System"
                  level={status?.system.state === "ready" ? "healthy" : "warning"}
                  value={status?.system.value ?? "—"}
                />
                <SummaryCard
                  detail={status?.ai_provider.detail ?? "Loading"}
                  label="AI provider"
                  level={status?.ai_provider.state === "ready" ? "healthy" : status?.ai_provider.state === "disabled" ? "muted" : "warning"}
                  value={status?.ai_provider.value ?? "—"}
                />
                <SummaryCard
                  detail={system?.health.reasons[0] ?? "Telemetry"}
                  label="Live health"
                  level={system?.health.level ?? "muted"}
                  value={system?.health.label ?? "—"}
                />
                <SummaryCard
                  detail={updateStatus?.message ?? "Host agent"}
                  label="Updates"
                  level={updateStatus?.state === "failed" ? "critical" : updateStatus?.agent_available ? "healthy" : "warning"}
                  value={updateStatus?.state ?? "—"}
                />
              </div>

              <div className="admin-quick-grid">
                {[
                  { label: "Connect NIM", detail: "AI setup", action: () => setPage("ai") },
                  { label: "Check updates", detail: "GitHub main", action: () => void runUpdate("check") },
                  { label: "Update now", detail: "Pull & rebuild", action: () => void runUpdate("apply") },
                  { label: "Open Assistant", detail: "Chat workspace", action: () => onOpenAssistant?.() },
                  { label: "Maintenance", detail: "Backups & restore", action: () => onNavigate?.("maintenance") },
                  { label: "Sources", detail: "Knowledge base", action: () => onNavigate?.("sources") },
                  { label: "Notifications", detail: "Channels", action: () => onNavigate?.("notifications") },
                  { label: "Plugins", detail: "Extensions", action: () => onNavigate?.("plugins") },
                ].map((item) => (
                  <button className="admin-quick-action" key={item.label} onClick={item.action} type="button">
                    <strong>{item.label}</strong>
                    <span>{item.detail}</span>
                  </button>
                ))}
              </div>

              <div className="admin-console-split">
                <Panel title="System metrics" eyebrow="Live table" actions={<button className="text-button" onClick={() => setPage("system")} type="button">Open system</button>}>
                  <DataTable columns={["Metric", "Value", "Detail", "Health"]} empty="Telemetry unavailable." rows={systemRows} />
                </Panel>
                <Panel title="Stack services" eyebrow="Auto-detected" actions={<button className="text-button" onClick={() => setPage("services")} type="button">Open services</button>}>
                  <DataTable columns={["Name", "Kind", "State", "Detail", "Health"]} empty="No services detected yet." rows={serviceRows} />
                </Panel>
              </div>

              <div className="admin-console-split">
                <Panel title="Recent audit events" eyebrow="Account history">
                  <DataTable columns={["When", "Action", "Result", "Target"]} empty="No audit events yet." rows={auditRows} />
                </Panel>
                <Panel title="Backups" eyebrow="Verified artifacts" actions={<button className="text-button" onClick={() => onNavigate?.("maintenance")} type="button">Maintenance</button>}>
                  <DataTable columns={["Status", "Size", "Created", "Path"]} empty="No backups yet." rows={backupRows} />
                </Panel>
              </div>

              <Panel title="Deployment snapshot" eyebrow="Configuration">
                <DataTable
                  columns={["Property", "Value"]}
                  empty="Deployment status unavailable."
                  rows={[
                    ["App version", status?.version ?? "—"],
                    ["Migration head", status?.migration_head ?? deployment?.migration_head ?? "—"],
                    ["TLS expected", deployment ? (deployment.tls_expected ? "Yes" : "No") : "—"],
                    ["Replication", deployment ? (deployment.replication_configured ? "Configured" : "Local only") : "—"],
                    ["NIM source", status?.nvidia_nim.source ?? "—"],
                    ["NIM model", status?.nvidia_nim.model ?? "Not connected"],
                    ["Update agent", updateStatus?.agent_available ? "Online" : "Not seen"],
                    ["Current commit", updateStatus?.current_commit ?? "—"],
                  ]}
                />
              </Panel>
            </div>
          )}

          {page === "ai" && (
            <div className="admin-console-stack">
              <div className="admin-console-title-row">
                <div>
                  <p className="eyebrow">OpenAI-compatible NVIDIA API</p>
                  <h2>AI / NVIDIA NIM</h2>
                </div>
                <span className={`admin-badge admin-badge-${configured ? "healthy" : "muted"}`}>{configured ? "Connected" : "Not connected"}</span>
              </div>
              <Panel title={configured ? "NVIDIA NIM connected" : "Connect NVIDIA NIM"} eyebrow="Live model catalog">
                <p className="admin-panel-help">
                  Models load automatically from the OpenAI-compatible catalog at{" "}
                  <code>{liveCatalog?.base_url ?? options?.base_url ?? "https://integrate.api.nvidia.com/v1"}</code>
                  <code>/models</code>. Paste your API key to use a model — you do not need to browse build.nvidia.com for model ids.
                </p>
                <ol className="admin-setup-steps">
                  <li>
                    <strong>1 · Models load automatically</strong>
                    <span>Live chat and embedding models are fetched from NVIDIA when you open this page.</span>
                  </li>
                  <li>
                    <strong>2 · Paste API key & pick a model</strong>
                    <span>Key is encrypted on this device. Choose any model from the live list (or search).</span>
                  </li>
                  <li>
                    <strong>3 · Test, then save</strong>
                    <span>Test a completion, then save to enable the Assistant.</span>
                  </li>
                </ol>
                <form className="admin-nim-form" onSubmit={(event) => void saveNim(event)}>
                  <label>
                    NVIDIA API key
                    <input
                      autoComplete="new-password"
                      onChange={(event) => setApiKey(event.target.value)}
                      placeholder={configured && source === "browser" ? "Leave blank to keep saved key" : "nvapi-…"}
                      required={!configured || source !== "browser"}
                      type="password"
                      value={apiKey}
                    />
                  </label>
                  <div className="admin-nim-actions">
                    <button
                      className="refresh-button"
                      disabled={loadingModels}
                      onClick={() => void loadLiveModels()}
                      type="button"
                    >
                      {loadingModels ? "Loading models…" : liveCatalog?.source === "live" ? "Refresh models from NVIDIA" : "Load models from NVIDIA"}
                    </button>
                    <span className="form-help">
                      {loadingModels
                        ? "Contacting integrate.api.nvidia.com…"
                        : liveCatalog
                          ? `${liveCatalog.source === "live" ? "Live" : "Fallback"} · ${liveCatalog.chat_models.length} chat · ${liveCatalog.embedding_models.length} embedding`
                          : "Waiting to load model catalog…"}
                    </span>
                  </div>
                  {modelsError && (
                    <div className="inline-state error-state" role="alert">
                      <strong>Model list failed.</strong>
                      <span>{modelsError}</span>
                      <button className="text-button" disabled={loadingModels} onClick={() => void loadLiveModels()} type="button">
                        Retry
                      </button>
                    </div>
                  )}
                  <label>
                    Filter models
                    <input onChange={(event) => setModelFilter(event.target.value)} placeholder="Search llama, gemma, embed…" value={modelFilter} />
                  </label>
                  <div className="admin-model-block">
                    <div className="admin-model-heading">
                      <strong>Chat model ({filteredChatModels.length})</strong>
                      <button className="text-button" onClick={() => setCustomModel((value) => !value)} type="button">
                        {customModel ? "Pick from list" : "Custom model id"}
                      </button>
                    </div>
                    {customModel ? (
                      <label>
                        Model id
                        <input maxLength={160} onChange={(event) => setModel(event.target.value)} required value={model} />
                      </label>
                    ) : (
                      <div className="admin-preset-grid admin-preset-grid-scroll">
                        {filteredChatModels.length === 0 ? (
                          <p className="form-help">No chat models loaded yet. Paste a key and click Load models from NVIDIA.</p>
                        ) : (
                          filteredChatModels.map((preset) => (
                            <button
                              className={`admin-preset-card${model === preset.id ? " selected" : ""}`}
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
                          ))
                        )}
                      </div>
                    )}
                  </div>
                  <label className="checkbox-row">
                    <input checked={embeddings} onChange={(event) => setEmbeddings(event.target.checked)} type="checkbox" />
                    Enable semantic embeddings
                  </label>
                  {embeddings && (
                    <div className="admin-model-block">
                      <div className="admin-model-heading">
                        <strong>Embedding model ({filteredEmbeddingModels.length})</strong>
                        <button className="text-button" onClick={() => setCustomEmbedding((value) => !value)} type="button">
                          {customEmbedding ? "Pick from list" : "Custom model id"}
                        </button>
                      </div>
                      {customEmbedding ? (
                        <label>
                          Embedding model id
                          <input maxLength={160} onChange={(event) => setEmbeddingModel(event.target.value)} required value={embeddingModel} />
                        </label>
                      ) : (
                        <div className="admin-preset-grid admin-preset-grid-scroll">
                          {filteredEmbeddingModels.length === 0 ? (
                            <p className="form-help">No embedding models loaded yet.</p>
                          ) : (
                            filteredEmbeddingModels.map((preset) => (
                              <button
                                className={`admin-preset-card${embeddingModel === preset.id ? " selected" : ""}`}
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
                            ))
                          )}
                        </div>
                      )}
                    </div>
                  )}
                  <button className="text-button" onClick={() => setShowAdvanced((value) => !value)} type="button">
                    {showAdvanced ? "Hide endpoint details" : "Show endpoint details"}
                  </button>
                  {showAdvanced && (
                    <DataTable
                      columns={["Field", "Value"]}
                      empty="—"
                      rows={[
                        ["Base URL", liveCatalog?.base_url ?? options?.base_url ?? "https://integrate.api.nvidia.com/v1"],
                        ["Models", liveCatalog?.models_url ?? "https://integrate.api.nvidia.com/v1/models"],
                        ["Chat completions", liveCatalog?.chat_endpoint ?? options?.chat_endpoint ?? "https://integrate.api.nvidia.com/v1/chat/completions"],
                        ["Embeddings", liveCatalog?.embedding_endpoint ?? options?.embedding_endpoint ?? "https://integrate.api.nvidia.com/v1/embeddings"],
                        ["OpenAI compatible", (liveCatalog?.openai_compatible ?? options?.openai_compatible ?? true) ? "Yes" : "No"],
                        ["Catalog source", liveCatalog?.source ?? "fallback presets"],
                      ]}
                    />
                  )}
                  {testResult && (
                    <div className={`inline-state ${testResult.ok ? "success-state" : "error-state"}`}>
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
                      <button className="text-button danger-text" disabled={saving} onClick={() => void disableNim()} type="button">
                        Disable NIM
                      </button>
                    )}
                    {configured && onOpenAssistant && (
                      <button className="text-button" onClick={onOpenAssistant} type="button">
                        Open Assistant
                      </button>
                    )}
                  </div>
                </form>
              </Panel>
            </div>
          )}

          {page === "updates" && (
            <div className="admin-console-stack">
              <div className="admin-console-title-row">
                <div>
                  <p className="eyebrow">Software lifecycle</p>
                  <h2>Updates</h2>
                </div>
                <span className={`admin-badge admin-badge-${updateStatus?.agent_available ? "healthy" : "warning"}`}>
                  {updateStatus?.agent_available ? "Agent online" : "Agent offline"}
                </span>
              </div>
              <div className="admin-summary-grid-4">
                <SummaryCard detail="Installed app" label="Version" value={updateStatus?.current_version ?? status?.version ?? "—"} />
                <SummaryCard detail="Local checkout" label="Current commit" value={updateStatus?.current_commit ?? "—"} />
                <SummaryCard detail="Remote target" label="Target commit" value={updateStatus?.target_commit ?? "—"} />
                <SummaryCard detail={updateStatus?.message ?? "—"} label="State" level={updateStatus?.state === "failed" ? "critical" : "healthy"} value={updateStatus?.state ?? "—"} />
              </div>
              <Panel
                actions={
                  <div className="admin-nim-actions">
                    <button className="refresh-button" disabled={updateBusy || updateStatus?.can_request === false} onClick={() => void runUpdate("check")} type="button">
                      Check for updates
                    </button>
                    <button className="primary-button" disabled={updateBusy || updateStatus?.can_request === false} onClick={() => void runUpdate("apply")} type="button">
                      Update now
                    </button>
                  </div>
                }
                eyebrow="Fixed host steps"
                title="GitHub pull, rebuild, migrate, restart"
              >
                <DataTable
                  columns={["Field", "Value"]}
                  empty="No update status yet."
                  rows={[
                    ["Request id", updateStatus?.request_id ?? "—"],
                    ["Action", updateStatus?.action ?? "—"],
                    ["Agent", updateStatus?.agent_available ? "Online" : "Not seen recently"],
                    ["Message", updateStatus?.message ?? "—"],
                    ["Requested", updateStatus?.requested_at ? new Date(updateStatus.requested_at).toLocaleString() : "—"],
                    ["Started", updateStatus?.started_at ? new Date(updateStatus.started_at).toLocaleString() : "—"],
                    ["Finished", updateStatus?.finished_at ? new Date(updateStatus.finished_at).toLocaleString() : "—"],
                  ]}
                />
                {updateStatus?.log_tail && <pre className="admin-update-log">{updateStatus.log_tail}</pre>}
              </Panel>
            </div>
          )}

          {page === "system" && (
            <div className="admin-console-stack">
              <div className="admin-console-title-row">
                <div>
                  <p className="eyebrow">Live telemetry</p>
                  <h2>System</h2>
                </div>
                <span className={`admin-badge admin-badge-${tone(system?.health.level)}`}>{system?.health.label ?? "Loading"}</span>
              </div>
              <div className="admin-summary-grid-4">
                <SummaryCard detail={`${system?.cpu.cpu_count ?? "—"} cores`} label="CPU" level={system?.cpu.health.level} value={system?.cpu.usage_percent == null ? "—" : `${system.cpu.usage_percent}%`} />
                <SummaryCard detail="Used" label="Memory" level={system?.memory.health.level} value={system?.memory.used_percent == null ? "—" : `${system.memory.used_percent}%`} />
                <SummaryCard detail="Data volume" label="Storage" level={system?.storage.health.level} value={system?.storage.used_percent == null ? "—" : `${system.storage.used_percent}%`} />
                <SummaryCard detail={system?.temperature.source_name ?? "thermal"} label="Temperature" level={system?.temperature.health.level} value={system?.temperature.celsius == null ? "—" : `${system.temperature.celsius.toFixed(1)}°C`} />
              </div>
              <Panel title="Metric table" eyebrow="Auto-classified">
                <DataTable columns={["Metric", "Value", "Detail", "Health"]} empty="Telemetry unavailable." rows={systemRows} />
              </Panel>
            </div>
          )}

          {page === "services" && (
            <div className="admin-console-stack">
              <div className="admin-console-title-row">
                <div>
                  <p className="eyebrow">Stack visibility</p>
                  <h2>Services</h2>
                </div>
                <span className={`admin-badge admin-badge-${tone(system?.service_status.health.level)}`}>{system?.service_status.health.label ?? "—"}</span>
              </div>
              <Panel title="Detected units" eyebrow={system?.service_status.containers_available ? "Docker socket" : "Compose network"}>
                <DataTable columns={["Name", "Kind", "State", "Detail", "Health"]} empty="No service units reported." rows={serviceRows} />
              </Panel>
            </div>
          )}

          {page === "operations" && (
            <div className="admin-console-stack">
              <div className="admin-console-title-row">
                <div>
                  <p className="eyebrow">Function-oriented shortcuts</p>
                  <h2>Operations</h2>
                </div>
              </div>
              <div className="admin-quick-grid">
                {[
                  { label: "Maintenance", detail: "Backups, restore, retention", target: "maintenance" as const },
                  { label: "Notifications", detail: "Channel status & test send", target: "notifications" as const },
                  { label: "Sources", detail: "Upload, import, sync", target: "sources" as const },
                  { label: "Plugins", detail: "Rescan & lifecycle", target: "plugins" as const },
                  { label: "Files", detail: "Approved-root metadata", target: "files" as const },
                  { label: "Docker view", detail: "Container inspection", target: "docker" as const },
                  { label: "Assistant", detail: "Chat with configured model", target: "assistant" as const },
                ].map((item) => (
                  <button className="admin-quick-action" key={item.label} onClick={() => (item.target === "assistant" ? onOpenAssistant?.() : onNavigate?.(item.target))} type="button">
                    <strong>{item.label}</strong>
                    <span>{item.detail}</span>
                  </button>
                ))}
              </div>
              <Panel title="Audit trail" eyebrow="Latest events">
                <DataTable columns={["When", "Action", "Result", "Target"]} empty="No audit events." rows={auditRows} />
              </Panel>
            </div>
          )}

          {page === "host" && (
            <div className="admin-console-stack">
              <div className="admin-console-title-row">
                <div>
                  <p className="eyebrow">Intentionally host-side</p>
                  <h2>Host only</h2>
                </div>
              </div>
              <Panel title="Still requires the Pi terminal" eyebrow="Safety boundary">
                <DataTable
                  columns={["Category", "Examples"]}
                  empty="—"
                  rows={[
                    ["One-time install", "Docker install, first clone, owner bootstrap"],
                    ["Secrets", "JWT_SECRET, SMTP/ntfy credentials, backup encryption keys"],
                    ["Paths", "WORKSPACE_ROOTS, MEDIA_ROOTS, PLUGINS_DIR"],
                    ["Never in browser", "Arbitrary shell, reboot, package installs, unconstrained Docker control"],
                  ]}
                />
                <p className="form-help">
                  Software updates and AI setup are web-native after the host agent is installed. Remaining items stay on the host so a stolen browser session cannot reconfigure the machine.
                </p>
              </Panel>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
