import { authenticatedFetch } from "./auth";

export type Availability = {
  available: boolean;
  reason: string | null;
};

export type SystemOverview = {
  status: "ok" | "degraded";
  checked_at: string;
  cpu: {
    usage_percent: number | null;
    load_1m: number | null;
    cpu_count: number | null;
    source: Availability;
  };
  memory: {
    total_bytes: number | null;
    available_bytes: number | null;
    used_percent: number | null;
    source: Availability;
  };
  storage: {
    path_label: string;
    total_bytes: number | null;
    used_bytes: number | null;
    free_bytes: number | null;
    used_percent: number | null;
    source: Availability;
  };
  temperature: {
    celsius: number | null;
    source_name: string | null;
    source: Availability;
  };
  uptime: {
    seconds: number | null;
    source: Availability;
  };
  network: {
    interfaces: Array<{
      name: string;
      state: string | null;
      receive_bytes: number;
      transmit_bytes: number;
    }>;
    source: Availability;
  };
  service_status: {
    services_available: boolean;
    containers_available: boolean;
    reason: string | null;
    source: Availability;
  };
};

export async function readSystemOverview(): Promise<SystemOverview> {
  const response = await authenticatedFetch("/api/v1/system/overview", {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`System overview request failed with ${response.status}`);
  }
  return response.json() as Promise<SystemOverview>;
}
