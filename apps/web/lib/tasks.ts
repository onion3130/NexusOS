import { authenticatedFetch } from "./auth";

export type Task = {
  id: string;
  series_id: string | null;
  title: string;
  description: string | null;
  status: "open" | "in_progress" | "completed" | "archived";
  priority: "low" | "normal" | "high" | "urgent";
  due_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  category: { id: string; name: string; color: string | null } | null;
  tags: Array<{ id: string; name: string }>;
  recurrence: Record<string, unknown> | null;
  reminders: Array<{ id: string; scheduled_for: string; offset_minutes: number | null; status: string; delivered_at: string | null }>;
};

export type TaskInput = {
  title: string;
  description?: string;
  due_at?: string | null;
  priority?: Task["priority"];
  category?: string | null;
  tags?: string[];
  recurrence?: Record<string, unknown> | null;
  reminders?: Array<{ scheduled_for?: string; offset_minutes?: number }>;
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Task request failed with ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function listTasks(includeCompleted = false): Promise<Task[]> {
  const response = await authenticatedFetch(`/api/v1/tasks?include_completed=${includeCompleted}`, { cache: "no-store" });
  const body = await parse<{ items: Task[] }>(response);
  return body.items;
}

function idempotencyKey(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

export async function createTask(input: TaskInput): Promise<Task> {
  return parse<Task>(await authenticatedFetch("/api/v1/tasks", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function updateTask(id: string, input: Partial<TaskInput> & { status?: Task["status"] }): Promise<Task> {
  return parse<Task>(await authenticatedFetch(`/api/v1/tasks/${encodeURIComponent(id)}`, { method: "PATCH", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function completeTask(id: string): Promise<Task> {
  return parse<Task>(await authenticatedFetch(`/api/v1/tasks/${encodeURIComponent(id)}/complete`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey() } }));
}

export async function deleteTask(id: string): Promise<void> {
  await parse<void>(await authenticatedFetch(`/api/v1/tasks/${encodeURIComponent(id)}`, { method: "DELETE", headers: { "Idempotency-Key": idempotencyKey() } }));
}

export async function addReminder(taskId: string, input: { scheduled_for?: string; offset_minutes?: number }): Promise<Task> {
  return parse<Task>(await authenticatedFetch(`/api/v1/tasks/${encodeURIComponent(taskId)}/reminders`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function updateReminder(id: string, input: { scheduled_for?: string; offset_minutes?: number }): Promise<Task> {
  return parse<Task>(await authenticatedFetch(`/api/v1/reminders/${encodeURIComponent(id)}`, { method: "PATCH", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function deleteReminder(id: string): Promise<void> {
  await parse<void>(await authenticatedFetch(`/api/v1/reminders/${encodeURIComponent(id)}`, { method: "DELETE", headers: { "Idempotency-Key": idempotencyKey() } }));
}
