import { authenticatedFetch } from "./auth";

export type ChannelDelivery = {
  channel: string;
  status: string;
  delivered_at: string | null;
  error_code: string | null;
};

export type Notification = {
  id: string;
  type: string;
  title: string;
  body: string;
  task_id: string | null;
  created_at: string;
  read_at: string | null;
  channels: ChannelDelivery[];
};

export type NotificationSettings = {
  email_enabled: boolean;
  email_configured: boolean;
  email_smtp_host: string | null;
  email_smtp_user: string | null;
  email_from: string | null;
  email_to: string | null;
  email_credentials_set: boolean;
  push_enabled: boolean;
  push_configured: boolean;
  push_url: string | null;
  push_topic: string | null;
  push_token_set: boolean;
};

export type TestSendResult = {
  channel: string;
  ok: boolean;
  error_code: string | null;
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Notification request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

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

export async function readNotificationSettings(): Promise<NotificationSettings> {
  return parse<NotificationSettings>(await authenticatedFetch("/api/v1/notifications/settings", { cache: "no-store" }));
}

export async function testNotificationSettings(): Promise<TestSendResult[]> {
  return parse<TestSendResult[]>(await authenticatedFetch("/api/v1/notifications/settings/test", { method: "POST", headers: { "Idempotency-Key": `test-${Date.now()}` } }));
}

export async function resendNotification(id: string): Promise<Notification> {
  return parse<Notification>(await authenticatedFetch(`/api/v1/notifications/${encodeURIComponent(id)}/resend`, { method: "POST", headers: { "Idempotency-Key": `resend-${Date.now()}` } }));
}
