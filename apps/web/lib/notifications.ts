import { authenticatedFetch } from "./auth";

export type Notification = {
  id: string;
  type: string;
  title: string;
  body: string;
  task_id: string | null;
  created_at: string;
  read_at: string | null;
};

export async function listNotifications(): Promise<{ items: Notification[]; unread_count: number }> {
  const response = await authenticatedFetch("/api/v1/notifications", { cache: "no-store" });
  if (!response.ok) throw new Error(`Notification request failed with ${response.status}`);
  return response.json() as Promise<{ items: Notification[]; unread_count: number }>;
}

export async function markNotificationRead(id: string): Promise<void> {
  const response = await authenticatedFetch(`/api/v1/notifications/${encodeURIComponent(id)}/read`, { method: "POST", headers: { "Idempotency-Key": id } });
  if (!response.ok && response.status !== 204) throw new Error(`Notification update failed with ${response.status}`);
}

export async function markAllNotificationsRead(): Promise<void> {
  const response = await authenticatedFetch("/api/v1/notifications/read-all", { method: "POST", headers: { "Idempotency-Key": `all-${Date.now()}` } });
  if (!response.ok) throw new Error(`Notification update failed with ${response.status}`);
}
