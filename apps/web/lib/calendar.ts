import { authenticatedFetch } from "./auth";

export type CalendarCategory = {
  id: string;
  name: string;
  color: string | null;
};

export type CalendarReminder = {
  id: string;
  scheduled_for: string;
  offset_minutes: number | null;
  status: string;
  delivered_at: string | null;
};

export type CalendarEvent = {
  id: string;
  title: string;
  description: string | null;
  location: string | null;
  starts_at: string;
  ends_at: string;
  all_day: boolean;
  category: CalendarCategory | null;
  created_at: string;
  updated_at: string;
  reminders: CalendarReminder[];
};

export type EventInput = {
  title: string;
  description?: string | null;
  location?: string | null;
  starts_at: string;
  ends_at: string;
  all_day?: boolean;
  category?: string | null;
  reminders?: Array<{ scheduled_for?: string; offset_minutes?: number }>;
};

export type ReminderInput = {
  scheduled_for?: string;
  offset_minutes?: number;
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Calendar request failed with ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function idempotencyKey(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

export async function listEvents(from?: string, to?: string, category?: string): Promise<CalendarEvent[]> {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  if (category) params.set("category", category);
  const query = params.toString();
  const response = await authenticatedFetch(`/api/v1/calendar/events${query ? `?${query}` : ""}`, { cache: "no-store" });
  const body = await parse<{ items: CalendarEvent[] }>(response);
  return body.items;
}

export async function createEvent(input: EventInput): Promise<CalendarEvent> {
  return parse<CalendarEvent>(await authenticatedFetch("/api/v1/calendar/events", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function updateEvent(id: string, input: Partial<EventInput>): Promise<CalendarEvent> {
  return parse<CalendarEvent>(await authenticatedFetch(`/api/v1/calendar/events/${encodeURIComponent(id)}`, { method: "PATCH", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function deleteEvent(id: string): Promise<void> {
  await parse<void>(await authenticatedFetch(`/api/v1/calendar/events/${encodeURIComponent(id)}`, { method: "DELETE", headers: { "Idempotency-Key": idempotencyKey() } }));
}

export async function addEventReminder(eventId: string, input: ReminderInput): Promise<CalendarEvent> {
  return parse<CalendarEvent>(await authenticatedFetch(`/api/v1/calendar/events/${encodeURIComponent(eventId)}/reminders`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function updateReminder(reminderId: string, input: ReminderInput): Promise<CalendarEvent> {
  return parse<CalendarEvent>(await authenticatedFetch(`/api/v1/calendar/reminders/${encodeURIComponent(reminderId)}`, { method: "PATCH", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function deleteReminder(reminderId: string): Promise<void> {
  await parse<void>(await authenticatedFetch(`/api/v1/calendar/reminders/${encodeURIComponent(reminderId)}`, { method: "DELETE", headers: { "Idempotency-Key": idempotencyKey() } }));
}

export async function listCategories(): Promise<CalendarCategory[]> {
  const response = await authenticatedFetch("/api/v1/calendar/categories", { cache: "no-store" });
  return parse<CalendarCategory[]>(response);
}

export async function createCategory(name: string, color?: string): Promise<CalendarCategory> {
  return parse<CalendarCategory>(await authenticatedFetch("/api/v1/calendar/categories", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify({ name, color: color || null }) }));
}

export async function deleteCategory(id: string): Promise<void> {
  await parse<void>(await authenticatedFetch(`/api/v1/calendar/categories/${encodeURIComponent(id)}`, { method: "DELETE", headers: { "Idempotency-Key": idempotencyKey() } }));
}
