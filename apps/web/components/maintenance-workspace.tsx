"use client";

import { useCallback, useEffect, useState } from "react";
import { confirmProposal, createProposal, listActionCatalog, listAuditEvents, listBackups, listProposals, readDeploymentStatus, rejectProposal, restoreProposalFor, type ActionCatalogItem, type ActionProposal, type AuditEvent, type Backup, type DeploymentStatus } from "../lib/host-actions";

function formatDate(value: string): string { return new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }); }
function formatBytes(value: number): string { return `${(value / 1024 / 1024).toFixed(2)} MB`; }

function ProposalCard({ proposal, onChange, onError }: { proposal: ActionProposal; onChange: (proposal: ActionProposal) => void; onError: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function decide(action: () => Promise<ActionProposal>) {
    setBusy(true);
    try { onChange(await action()); } catch (reason) { onError(reason instanceof Error ? reason.message : "Action update failed"); } finally { setBusy(false); }
  }
  const pending = proposal.status === "proposed";
  const isRestore = proposal.action_key === "maintenance.restore_backup";
  return <article className={`maintenance-proposal risk-${proposal.risk_level}`}><div className="maintenance-proposal-top"><div><span className="source-badge">{proposal.risk_level} risk</span><h3>{proposal.title}</h3></div><span className={`proposal-status status-${proposal.status}`}>{proposal.status}</span></div><p>{proposal.description}</p><small>Created {formatDate(proposal.created_at)} · Expires {formatDate(proposal.expires_at)}</small>{pending && <div className="maintenance-confirm-actions"><strong>Nothing runs until you confirm.</strong>{isRestore && <span className="restore-warning">This replaces the live database with the selected verified backup. A safety backup of the current database is created first, and NexusOS must be restarted after the restore completes.</span>}<button className="primary-button" disabled={busy} onClick={() => void decide(() => confirmProposal(proposal.id))} type="button">{busy ? "Confirming…" : "Confirm action"}</button><button className="text-button" disabled={busy} onClick={() => void decide(() => rejectProposal(proposal.id))} type="button">Reject</button></div>}{proposal.status === "queued" || proposal.status === "processing" ? <div className="inline-state" role="status"><span>Confirmed and queued for the private worker. Refresh to see the result.</span></div> : null}{proposal.status === "succeeded" && <div className="maintenance-success" role="status">{isRestore ? "Restored successfully. Restart NexusOS to complete the restore." : "Completed and audited successfully."}</div>}{proposal.status === "failed" && <div className="error-state" role="alert">Action failed with a safe error code: {proposal.error_code ?? "host_action_failed"}.</div>}</article>;
}

export function MaintenanceWorkspace() {
  const [catalog, setCatalog] = useState<ActionCatalogItem[]>([]);
  const [proposals, setProposals] = useState<ActionProposal[]>([]);
  const [backups, setBackups] = useState<Backup[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [deployment, setDeployment] = useState<DeploymentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { const [available, current, saved, events, status] = await Promise.all([listActionCatalog(), listProposals(), listBackups(), listAuditEvents(), readDeploymentStatus()]); setCatalog(available); setProposals(current); setBackups(saved); setAudit(events); setDeployment(status); setError(null); } catch (reason) { setError(reason instanceof Error ? reason.message : "Maintenance unavailable"); } finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  async function request(item: ActionCatalogItem) {
    setBusyAction(item.key);
    try { const created = await createProposal(item.key); setProposals((items) => [created, ...items]); setError(null); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create proposal"); } finally { setBusyAction(null); }
  }

  async function requestRestore(backupId: string) {
    setBusyAction("maintenance.restore_backup");
    try { const spec = restoreProposalFor(backupId); const created = await createProposal(spec.action_key, spec.input); setProposals((items) => [created, ...items]); setError(null); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create restore proposal"); } finally { setBusyAction(null); }
  }

  function updateProposal(updated: ActionProposal) { setProposals((items) => items.map((item) => item.id === updated.id ? updated : item)); void refresh(); }

  return <section aria-labelledby="maintenance-heading" className="maintenance-workspace section-block"><div className="section-heading"><div><p className="eyebrow">Controlled host operations</p><h2 id="maintenance-heading">Maintenance</h2></div><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div><div className="inline-state warning-state"><strong>Confirmation required for every action.</strong><span>NexusOS never accepts arbitrary shell text, filesystem paths, Docker commands, reboot, shutdown, or package operations.</span></div>{deployment && <div className="deployment-status-grid" aria-label="Deployment status"><article><strong>{deployment.tls_expected ? "HTTPS expected" : "Local HTTP"}</strong><span>Proxy deployment mode</span></article><article><strong>{deployment.replication_configured ? "Replication configured" : "Local backup only"}</strong><span>Encrypted off-host backup</span></article><article><strong>{deployment.migration_head}</strong><span>Database migration head</span></article></div>}{error && <div className="inline-state error-state" role="alert"><strong>Maintenance unavailable.</strong><span>{error}</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div>}<div className="maintenance-action-grid">{catalog.map((item) => <article className="maintenance-action-card" key={item.key}><span className="command-icon">⌁</span><h3>{item.title}</h3><p>{item.description}</p><span className="maintenance-risk">{item.risk_level} risk · explicit confirmation</span><button className="primary-button" disabled={busyAction === item.key} onClick={() => void request(item)} type="button">{busyAction === item.key ? "Preparing…" : "Review action"}</button></article>)}</div><div className="maintenance-columns"><div><div className="section-heading"><div><p className="eyebrow">Approval history</p><h2>Action proposals</h2></div></div>{loading ? <div className="task-list-placeholder">Loading proposals…</div> : proposals.length === 0 ? <div className="empty-state task-empty"><strong>No proposals yet</strong><span>Review an action above to begin.</span></div> : <div className="maintenance-proposals">{proposals.map((item) => <ProposalCard key={item.id} onChange={updateProposal} onError={setError} proposal={item} />)}</div>}</div><div><div className="section-heading"><div><p className="eyebrow">Verified artifacts</p><h2>Backups</h2></div></div><div className="backup-list">{backups.length === 0 ? <div className="empty-state task-empty"><strong>No backups yet</strong><span>Verified backups stay on the configured data volume.</span></div> : backups.map((backup) => <article className="backup-card" key={backup.id}><strong>{backup.status === "verified" ? "✓" : "!"} {backup.status}</strong><span>{formatBytes(backup.size_bytes)} · {formatDate(backup.created_at)}</span><small>{backup.relative_path}</small><span>{backup.encryption_status === "encrypted" ? "Encrypted" : "Not encrypted"} · {backup.replication_status === "replicated" ? "Replicated" : backup.replication_status ?? "Not configured"}</span><code>{backup.sha256.slice(0, 16)}…</code>{backup.restored_at && <small className="restored-note">Restored {formatDate(backup.restored_at)}</small>}{backup.status === "verified" && <button className="text-button restore-button" disabled={busyAction === "maintenance.restore_backup"} onClick={() => void requestRestore(backup.id)} type="button">{busyAction === "maintenance.restore_backup" ? "Preparing…" : "Restore"}</button>}</article>)}</div><div className="section-heading audit-heading"><div><p className="eyebrow">Account history</p><h2>Audit log</h2></div></div><div className="audit-list">{audit.slice(0, 8).map((event) => <article className="audit-row" key={event.id}><strong>{event.action}</strong><span>{event.result} · {formatDate(event.created_at)}</span></article>)}</div></div></div></section>;
}
