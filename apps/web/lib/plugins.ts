import { authenticatedFetch } from "./auth";

export type PluginCapability = {
  method: string;
  description: string;
  risk: "read" | "write" | "dangerous";
};

export type Plugin = {
  id: string;
  name: string;
  version: string;
  description: string;
  entrypoint: string;
  capabilities: PluginCapability[];
  status: "enabled" | "disabled" | "uninstalled";
  last_error_code: string | null;
  updated_at: string;
  run_count: number;
};

export type PluginRun = {
  id: string;
  plugin_id: string;
  method: string;
  status: "success" | "failure";
  error_code: string | null;
  duration_ms: number | null;
  created_at: string;
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Plugin request failed with ${response.status}`);
  }
  return response.status === 204 ? (undefined as T) : response.json() as Promise<T>;
}

export async function listPlugins(): Promise<Plugin[]> {
  return parse<Plugin[]>(await authenticatedFetch("/api/v1/plugins", { cache: "no-store" }));
}

export async function listPluginRuns(name: string): Promise<PluginRun[]> {
  return parse<PluginRun[]>(await authenticatedFetch(`/api/v1/plugins/${encodeURIComponent(name)}/runs`, { cache: "no-store" }));
}

export function pluginLifecycleProposalFor(action: "plugins.rescan" | "plugins.enable" | "plugins.disable" | "plugins.uninstall", name?: string): { action_key: string; input: Record<string, unknown> } {
  return { action_key: action, input: name ? { name } : {} };
}
