"use client";

import { useCallback, useEffect, useState } from "react";
import { createProposal, confirmProposal, type ActionCatalogItem } from "../lib/host-actions";
import { listPlugins, type Plugin } from "../lib/plugins";

export function PluginsWorkspace() {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { setPlugins(await listPlugins()); setError(null); } catch (reason) { setError(reason instanceof Error ? reason.message : "Plugin registry unavailable"); } finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  async function lifecycle(action: "plugins.rescan" | "plugins.enable" | "plugins.disable" | "plugins.uninstall", name?: string) {
    const label = `${action}:${name ?? "all"}`;
    setBusy(label); setError(null); setMessage(null);
    try {
      const proposal = await createProposal(action as ActionCatalogItem["key"], name ? { name } : {});
      const confirmed = window.confirm(`Confirm ${action.replace("plugins.", "")} for ${name ?? "the approved plugin directory"}? This action is audited.`);
      if (!confirmed) { setMessage("Action left unconfirmed."); return; }
      await confirmProposal(proposal.id);
      setMessage(`${action.replace("plugins.", "")} queued. The worker will apply it shortly.`);
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Plugin action failed"); } finally { setBusy(null); }
  }

  return <section aria-labelledby="plugins-heading" className="plugins-workspace section-block">
    <div className="section-heading"><div><p className="eyebrow">Operator-approved boundary</p><h2 id="plugins-heading">Plugins</h2></div><div className="plugins-toolbar"><button className="refresh-button" disabled={busy !== null} onClick={() => void lifecycle("plugins.rescan")} type="button">{busy === "plugins.rescan:all" ? "Queuing…" : "Rescan directory"}</button><button className="refresh-button" disabled={loading || busy !== null} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div></div>
    <p className="workspace-help">Only manifests under <code>PLUGINS_DIR</code> are discovered. Plugin code runs outside the API process with bounded time, memory, output, and file descriptors.</p>
    {message && <div className="inline-state" role="status"><strong>Plugin boundary.</strong><span>{message}</span></div>}
    {error && <div className="inline-state error-state" role="alert"><strong>Plugin unavailable.</strong><span>{error}</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div>}
    {loading ? <div className="task-list-placeholder" role="status">Loading approved plugins…</div> : plugins.length === 0 ? <div className="empty-state task-empty"><span className="empty-icon">◇</span><strong>No plugins registered</strong><span>Configure PLUGINS_DIR and rescan when you are ready to add an operator-approved plugin.</span></div> : <div className="plugin-list">{plugins.map((plugin) => { const readCapabilities = plugin.capabilities.filter((capability) => capability.risk === "read"); return <article className="plugin-card" key={plugin.id}><div className="plugin-card-heading"><div><span className={`plugin-status plugin-status-${plugin.status}`}>{plugin.status}</span><h3>{plugin.name}</h3><p>{plugin.description || "No description provided."} · v{plugin.version}</p></div><span className="plugin-run-count">{plugin.run_count} runs</span></div><div className="plugin-capabilities">{plugin.capabilities.map((capability) => <span className={`capability-pill capability-${capability.risk}`} key={capability.method}>{capability.method} · {capability.risk}</span>)}</div>{plugin.last_error_code && <p className="plugin-error">Last error: {plugin.last_error_code}</p>}{plugin.status === "enabled" && readCapabilities.length > 0 && <div className="plugin-invoke"><span className="workspace-help">Capabilities, including read-labeled methods, run only through the assistant confirmation workflow.</span><span className="capability-pill capability-read">{readCapabilities.length} read capability{readCapabilities.length === 1 ? "" : "ies"} available</span></div>}{<div className="plugin-actions"><button className="text-button" disabled={busy !== null} onClick={() => void lifecycle(plugin.status === "enabled" ? "plugins.disable" : "plugins.enable", plugin.name)} type="button">{plugin.status === "enabled" ? "Disable" : "Enable"}</button><button className="text-button danger-text" disabled={busy !== null} onClick={() => void lifecycle("plugins.uninstall", plugin.name)} type="button">Uninstall</button></div>}</article>; })}</div>}

  </section>;
}
