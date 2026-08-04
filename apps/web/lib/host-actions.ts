import { authenticatedFetch } from "./auth";

export type ActionCatalogItem = {
  key: "maintenance.create_backup" | "maintenance.verify_backup" | "maintenance.integrity_check" | "maintenance.restore_backup" | "maintenance.retention_cleanup" | "maintenance.rotate_encryption_key";
  title: string;
  description: string;
  risk_level: "low" | "medium" | "high";
  requires_confirmation: boolean;
  enabled: boolean;
};

export type ActionProposal = {
  id: string;
  action_key: ActionCatalogItem["key"];
  title: string;
  description: string;
  risk_level: "low" | "medium" | "high";
  status: "proposed" | "confirmed" | "queued" | "processing" | "succeeded" | "failed" | "rejected" | "expired";
  input: Record<string, unknown>;
  expires_at: string;
  created_at: string;
  confirmed_at: string | null;
  completed_at: string | null;
  job_id: string | null;
  error_code: string | null;
};

export type Backup = {
  id: string;
  relative_path: string;
  size_bytes: number;
  sha256: string;
  status: "created" | "verified" | "failed" | "deleted";
  integrity_result: string | null;
  created_at: string;
  verified_at: string | null;
  encryption_status: string | null;
  encrypted_size_bytes: number | null;
  replication_status: string | null;
  replicated_at: string | null;
  replication_error_code: string | null;
  restored_at: string | null;
  pruned_at: string | null;
};

export type RetentionPolicy = {
  count: number;
  days: number;
};

export type RetentionPreview = {
  policy: RetentionPolicy;
  to_prune: Backup[];
  retained: Backup[];
};

export type DeploymentStatus = {
  replication_configured: boolean;
  tls_expected: boolean;
  migration_head: string;
};

export type AuditEvent = {
  id: string;
  action: string;
  target: string | null;
  result: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Maintenance request failed with ${response.status}`);
  }
  return response.status === 204 ? (undefined as T) : response.json() as Promise<T>;
}

function key(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

export async function listActionCatalog(): Promise<ActionCatalogItem[]> {
  return parse<ActionCatalogItem[]>(await authenticatedFetch("/api/v1/system/actions", { cache: "no-store" }));
}

export async function listProposals(): Promise<ActionProposal[]> {
  return parse<ActionProposal[]>(await authenticatedFetch("/api/v1/system/actions/proposals", { cache: "no-store" }));
}

export async function createProposal(action_key: ActionCatalogItem["key"], input: Record<string, unknown> = {}): Promise<ActionProposal> {
  return parse<ActionProposal>(await authenticatedFetch("/api/v1/system/actions/proposals", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key() }, body: JSON.stringify({ action_key, input }) }));
}

export async function confirmProposal(id: string): Promise<ActionProposal> {
  return parse<ActionProposal>(await authenticatedFetch(`/api/v1/system/actions/proposals/${encodeURIComponent(id)}/confirm`, { method: "POST", headers: { "Idempotency-Key": key() } }));
}

export async function rejectProposal(id: string): Promise<ActionProposal> {
  return parse<ActionProposal>(await authenticatedFetch(`/api/v1/system/actions/proposals/${encodeURIComponent(id)}/reject`, { method: "POST", headers: { "Idempotency-Key": key() } }));
}

export async function readProposal(id: string): Promise<ActionProposal> {
  return parse<ActionProposal>(await authenticatedFetch(`/api/v1/system/actions/proposals/${encodeURIComponent(id)}`, { cache: "no-store" }));
}

export async function listBackups(): Promise<Backup[]> {
  return parse<Backup[]>(await authenticatedFetch("/api/v1/system/backups", { cache: "no-store" }));
}

export function restoreProposalFor(backupId: string): { action_key: ActionCatalogItem["key"]; input: { backup_id: string } } {
  return { action_key: "maintenance.restore_backup", input: { backup_id: backupId } };
}

export function retentionCleanupProposalFor(): { action_key: ActionCatalogItem["key"]; input: Record<string, never> } {
  return { action_key: "maintenance.retention_cleanup", input: {} };
}

export function rotationProposalFor(): { action_key: ActionCatalogItem["key"]; input: Record<string, never> } {
  return { action_key: "maintenance.rotate_encryption_key", input: {} };
}

export async function readRetentionPreview(): Promise<RetentionPreview> {
  return parse<RetentionPreview>(await authenticatedFetch("/api/v1/system/backups/retention-preview", { cache: "no-store" }));
}

export async function readDeploymentStatus(): Promise<DeploymentStatus> {
  return parse<DeploymentStatus>(await authenticatedFetch("/api/v1/system/deployment", { cache: "no-store" }));
}

export async function listAuditEvents(): Promise<AuditEvent[]> {
  return (await parse<{ items: AuditEvent[] }>(await authenticatedFetch("/api/v1/system/audit", { cache: "no-store" }))).items;
}
