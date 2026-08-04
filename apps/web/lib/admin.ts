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

export async function readAdminStatus(): Promise<AdminStatus> {
  const response = await authenticatedFetch("/api/v1/system/admin/status", { cache: "no-store" });
  if (!response.ok) throw new Error(`Admin status request failed with ${response.status}`);
  return response.json() as Promise<AdminStatus>;
}

export async function configureNvidiaNim(payload: {
  api_key: string;
  model: string;
  embeddings_enabled: boolean;
  embedding_model?: string;
}): Promise<AdminStatus> {
  const response = await authenticatedFetch("/api/v1/system/admin/nvidia-nim", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? `NVIDIA NIM setup failed with ${response.status}`);
  }
  return response.json() as Promise<AdminStatus>;
}

export async function disableNvidiaNim(): Promise<AdminStatus> {
  const response = await authenticatedFetch("/api/v1/system/admin/nvidia-nim", { method: "DELETE" });
  if (!response.ok) throw new Error(`NVIDIA NIM disable failed with ${response.status}`);
  return response.json() as Promise<AdminStatus>;
}
