import { authenticatedFetch } from "./auth";

export type AdminStatusCard = {
  state: "ready" | "degraded" | "disabled";
  value: string;
  detail: string;
};

export type AdminStatus = {
  version: string;
  migration_head: string;
  checked_at: string;
  system: AdminStatusCard;
  ai_provider: AdminStatusCard;
  storage: AdminStatusCard;
  embedding_provider: AdminStatusCard;
};

export async function readAdminStatus(): Promise<AdminStatus> {
  const response = await authenticatedFetch("/api/v1/system/admin/status", { cache: "no-store" });
  if (!response.ok) throw new Error(`Admin status request failed with ${response.status}`);
  return response.json() as Promise<AdminStatus>;
}
