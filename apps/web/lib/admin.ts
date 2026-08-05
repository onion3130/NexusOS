import { authenticatedFetch } from "./auth";

export type AdminStatusCard = {
  state: "ready" | "degraded" | "disabled";
  value: string;
  detail: string;
};

export type NimStatus = {
  configured: boolean;
  source: "browser" | "environment" | "none";
  model: string | null;
  embeddings_enabled: boolean;
  restart_required: boolean;
};

export type AdminStatus = {
  version: string;
  migration_head: string;
  checked_at: string;
  system: AdminStatusCard;
  ai_provider: AdminStatusCard;
  storage: AdminStatusCard;
  embedding_provider: AdminStatusCard;
  nvidia_nim: NimStatus;
};

export type NimChatPreset = {
  id: string;
  label: string;
  description: string;
  recommended?: boolean;
};

export type NimEmbeddingPreset = {
  id: string;
  label: string;
  description: string;
  recommended?: boolean;
};

export type NimOptions = {
  chat_endpoint: string;
  embedding_endpoint: string;
  chat_models: NimChatPreset[];
  embedding_models: NimEmbeddingPreset[];
  help_text: string;
};

export type NimTestResult = {
  ok: boolean;
  detail: string;
  model: string | null;
  embeddings_tested: boolean;
};

async function parseError(response: Response, fallback: string): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: string } | null;
  return body?.detail ?? fallback;
}

export async function readAdminStatus(): Promise<AdminStatus> {
  const response = await authenticatedFetch("/api/v1/system/admin/status", { cache: "no-store" });
  if (!response.ok) throw new Error(`Admin status request failed with ${response.status}`);
  return response.json() as Promise<AdminStatus>;
}

export async function readNimOptions(): Promise<NimOptions> {
  const response = await authenticatedFetch("/api/v1/system/admin/nvidia-nim/options", { cache: "no-store" });
  if (!response.ok) throw new Error(`NVIDIA NIM options request failed with ${response.status}`);
  return response.json() as Promise<NimOptions>;
}

export async function configureNvidiaNim(payload: {
  api_key?: string;
  model: string;
  embeddings_enabled: boolean;
  embedding_model?: string;
}): Promise<AdminStatus> {
  const response = await authenticatedFetch("/api/v1/system/admin/nvidia-nim", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await parseError(response, `NVIDIA NIM setup failed with ${response.status}`));
  return response.json() as Promise<AdminStatus>;
}

export async function testNvidiaNim(payload: { api_key?: string; model?: string } = {}): Promise<NimTestResult> {
  const response = await authenticatedFetch("/api/v1/system/admin/nvidia-nim/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await parseError(response, `NVIDIA NIM test failed with ${response.status}`));
  return response.json() as Promise<NimTestResult>;
}

export async function disableNvidiaNim(): Promise<AdminStatus> {
  const response = await authenticatedFetch("/api/v1/system/admin/nvidia-nim", { method: "DELETE" });
  if (!response.ok) throw new Error(`NVIDIA NIM disable failed with ${response.status}`);
  return response.json() as Promise<AdminStatus>;
}

export type SoftwareUpdateStatus = {
  state: "idle" | "queued" | "running" | "succeeded" | "failed" | "agent_missing";
  action: "check" | "apply" | null;
  request_id: string | null;
  message: string;
  agent_available: boolean;
  current_version: string;
  current_commit: string | null;
  target_commit: string | null;
  requested_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  log_tail: string | null;
  can_request: boolean;
};

export async function readSoftwareUpdateStatus(): Promise<SoftwareUpdateStatus> {
  const response = await authenticatedFetch("/api/v1/system/admin/update", { cache: "no-store" });
  if (!response.ok) throw new Error(`Software update status failed with ${response.status}`);
  return response.json() as Promise<SoftwareUpdateStatus>;
}

export async function requestSoftwareUpdate(action: "check" | "apply", confirm = false): Promise<SoftwareUpdateStatus> {
  const response = await authenticatedFetch("/api/v1/system/admin/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, confirm }),
  });
  if (!response.ok) throw new Error(await parseError(response, `Software update request failed with ${response.status}`));
  return response.json() as Promise<SoftwareUpdateStatus>;
}
