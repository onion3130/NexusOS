import { authenticatedFetch } from "./auth";

export type OpenWebUIStatus = {
  enabled: boolean;
  configured: boolean;
  url: string | null;
  label: string;
  embed: boolean;
  source: "browser" | "environment" | "none";
  detail: string;
};

async function parseError(response: Response, fallback: string): Promise<string> {
  const body = (await response.json().catch(() => null)) as { detail?: string | Array<{ msg?: string }> } | null;
  if (!body?.detail) return fallback;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    const first = body.detail[0];
    if (first && typeof first.msg === "string") return first.msg;
  }
  return fallback;
}

export async function readOpenWebUIStatus(): Promise<OpenWebUIStatus> {
  const response = await authenticatedFetch("/api/v1/system/openwebui", { cache: "no-store" });
  if (!response.ok) throw new Error(`Open WebUI status failed with ${response.status}`);
  return response.json() as Promise<OpenWebUIStatus>;
}

export async function configureOpenWebUI(payload: {
  enabled: boolean;
  url?: string;
  label?: string;
  embed?: boolean;
}): Promise<OpenWebUIStatus> {
  const response = await authenticatedFetch("/api/v1/system/admin/openwebui", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await parseError(response, `Open WebUI setup failed with ${response.status}`));
  return response.json() as Promise<OpenWebUIStatus>;
}

export async function disableOpenWebUI(): Promise<OpenWebUIStatus> {
  const response = await authenticatedFetch("/api/v1/system/admin/openwebui", { method: "DELETE" });
  if (!response.ok) throw new Error(`Open WebUI disable failed with ${response.status}`);
  return response.json() as Promise<OpenWebUIStatus>;
}
