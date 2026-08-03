"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { addReminder, completeTask, createTask, deleteReminder, deleteTask, listTasks, updateTask, type Task } from "../lib/tasks";

function dueLabel(value: string | null): string {
  if (!value) return "No due date";
  return new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function TaskRow({ task, includeCompleted, onChange, onError }: { task: Task; includeCompleted: boolean; onChange: (task: Task | null, removedId?: string) => void; onError: (message: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(task.title);
  const [editDue, setEditDue] = useState(task.due_at ? task.due_at.slice(0, 16) : "");
  const [reminderMinutes, setReminderMinutes] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    try { await action(); } catch (reason) { onError(reason instanceof Error ? reason.message : "Task update failed"); } finally { setBusy(false); }
  }
  function complete() { void run(async () => onChange(await completeTask(task.id))); }
  function saveEdit() { void run(async () => { onChange(await updateTask(task.id, { title: editTitle.trim(), due_at: editDue ? new Date(editDue).toISOString() : null })); setEditing(false); }); }
  function remove() {
    if (!window.confirm(`Delete “${task.title}”?`)) return;
    void run(async () => { await deleteTask(task.id); onChange(null, task.id); });
  }
  function addTaskReminder() {
    if (!reminderMinutes || !task.due_at) return;
    void run(async () => { onChange(await addReminder(task.id, { offset_minutes: Number(reminderMinutes) })); setReminderMinutes(""); });
  }
  function cancelReminder(id: string) { void run(async () => { await deleteReminder(id); onChange({ ...task, reminders: task.reminders.map((item) => item.id === id ? { ...item, status: "cancelled" } : item) }); }); }

  return <article className={`task-row priority-${task.priority}${task.status === "completed" ? " task-completed" : ""}`}>
    <button aria-label={task.status === "completed" ? `Completed: ${task.title}` : `Complete: ${task.title}`} className="task-check" disabled={busy || task.status === "completed"} onClick={complete} type="button">{task.status === "completed" ? "✓" : "○"}</button>
    <div className="task-row-copy">
      {editing ? <div className="task-edit-fields"><input aria-label="Edit task title" maxLength={160} onChange={(event) => setEditTitle(event.target.value)} value={editTitle} /><input aria-label="Edit task due date" onChange={(event) => setEditDue(event.target.value)} type="datetime-local" value={editDue} /><button className="primary-button" disabled={!editTitle.trim() || busy} onClick={saveEdit} type="button">Save</button><button className="text-button" onClick={() => setEditing(false)} type="button">Cancel</button></div> : <>
        <strong>{task.title}</strong>{task.description && <p>{task.description}</p>}<div className="task-meta"><span>{dueLabel(task.due_at)}</span><span>{task.priority}</span>{task.category && <span>{task.category.name}</span>}{task.tags.map((tag) => <span key={tag.id}>#{tag.name}</span>)}{task.reminders.length > 0 && <span>♢ {task.reminders.length} reminder{task.reminders.length === 1 ? "" : "s"}</span>}</div>
        <div className="task-reminder-list">{task.reminders.filter((reminder) => reminder.status === "pending").map((reminder) => <button className="text-button" disabled={busy} key={reminder.id} onClick={() => cancelReminder(reminder.id)} type="button">Cancel reminder</button>)}{task.due_at && task.status !== "completed" && <span className="reminder-inline"><input aria-label={`Reminder minutes before ${task.title}`} inputMode="numeric" min="0" onChange={(event) => setReminderMinutes(event.target.value)} placeholder="Minutes before" type="number" value={reminderMinutes} /><button className="text-button" disabled={!reminderMinutes || busy} onClick={addTaskReminder} type="button">Add reminder</button></span>}</div>
        <button className="text-button task-edit-button" disabled={busy} onClick={() => setEditing(true)} type="button">Edit</button>
      </>}
    </div>
    <button aria-label={`Delete ${task.title}`} className="task-delete" disabled={busy} onClick={remove} type="button">⌫</button>
  </article>;
}

export function TaskWorkspace() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [includeCompleted, setIncludeCompleted] = useState(false);
  const [priority, setPriority] = useState("all");
  const [draft, setDraft] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [taskPriority, setTaskPriority] = useState<Task["priority"]>("normal");
  const [category, setCategory] = useState("");
  const [tags, setTags] = useState("");
  const [recurring, setRecurring] = useState(false);
  const [recurrenceFrequency, setRecurrenceFrequency] = useState<"daily" | "weekly" | "monthly">("daily");
  const [recurrenceWeekday, setRecurrenceWeekday] = useState("MO");
  const [reminderMinutes, setReminderMinutes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { setTasks(await listTasks(includeCompleted)); setError(null); } catch (reason) { setError(reason instanceof Error ? reason.message : "Tasks unavailable"); } finally { setLoading(false); }
  }, [includeCompleted]);
  useEffect(() => { void refresh(); }, [refresh]);
  const visibleTasks = useMemo(() => priority === "all" ? tasks : tasks.filter((task) => task.priority === priority), [priority, tasks]);

  async function add(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.trim() || saving) return;
    setSaving(true); setError(null);
    try {
      const task = await createTask({ title: draft.trim(), due_at: dueAt ? new Date(dueAt).toISOString() : null, priority: taskPriority, category: category.trim() || null, tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean), recurrence: recurring ? { version: 1, frequency: recurrenceFrequency, interval: 1, ...(recurrenceFrequency === "weekly" ? { weekdays: [recurrenceWeekday] } : {}), ...(recurrenceFrequency === "monthly" ? { day_of_month: dueAt ? new Date(dueAt).getDate() : 1 } : {}), timezone: Intl.DateTimeFormat().resolvedOptions().timeZone } : null, reminders: reminderMinutes ? [{ offset_minutes: Number(reminderMinutes) }] : [] });
      setTasks((items) => [task, ...items]); setDraft(""); setDueAt(""); setCategory(""); setTags(""); setRecurring(false); setReminderMinutes(""); setRecurrenceFrequency("daily");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create task"); } finally { setSaving(false); }
  }
  function replaceTask(updated: Task | null, removedId?: string) { setTasks((items) => { if (!updated) return items.filter((item) => item.id !== removedId); if (!includeCompleted && updated.status === "completed") return items.filter((item) => item.id !== updated.id); return items.map((item) => item.id === updated.id ? updated : item); }); }

  return <section aria-labelledby="tasks-heading" className="task-workspace section-block">
    <div className="section-heading"><div><p className="eyebrow">Personal productivity</p><h2 id="tasks-heading">Tasks</h2></div><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div>
    <form className="task-create-form" onSubmit={add}><label htmlFor="task-title">New task</label><div className="task-create-main"><input id="task-title" maxLength={160} onChange={(event) => setDraft(event.target.value)} placeholder="What needs doing?" value={draft} /><button className="primary-button" disabled={!draft.trim() || saving} type="submit">{saving ? "Adding…" : "Add task"}</button></div><div className="task-create-options"><input aria-label="Due date" onChange={(event) => setDueAt(event.target.value)} type="datetime-local" value={dueAt} /><select aria-label="Priority" onChange={(event) => setTaskPriority(event.target.value as Task["priority"])} value={taskPriority}><option value="low">Low priority</option><option value="normal">Normal priority</option><option value="high">High priority</option><option value="urgent">Urgent priority</option></select><input aria-label="Category" maxLength={64} onChange={(event) => setCategory(event.target.value)} placeholder="Category" value={category} /><input aria-label="Tags" maxLength={300} onChange={(event) => setTags(event.target.value)} placeholder="Tags, comma separated" value={tags} /><input aria-label="Reminder minutes before due" inputMode="numeric" min="0" onChange={(event) => setReminderMinutes(event.target.value)} placeholder="Reminder minutes before due" type="number" value={reminderMinutes} /><label className="checkbox-label"><input checked={recurring} onChange={(event) => setRecurring(event.target.checked)} type="checkbox" /> Recurring</label>{recurring && <select aria-label="Recurrence frequency" onChange={(event) => setRecurrenceFrequency(event.target.value as typeof recurrenceFrequency)} value={recurrenceFrequency}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select>}{recurring && recurrenceFrequency === "weekly" && <select aria-label="Weekly recurrence day" onChange={(event) => setRecurrenceWeekday(event.target.value)} value={recurrenceWeekday}>{[["MO", "Monday"], ["TU", "Tuesday"], ["WE", "Wednesday"], ["TH", "Thursday"], ["FR", "Friday"], ["SA", "Saturday"], ["SU", "Sunday"]].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>}</div></form>
    <div className="task-toolbar"><div className="task-filters"><button className={priority === "all" ? "filter-active" : ""} onClick={() => setPriority("all")} type="button">All</button>{["urgent", "high", "normal", "low"].map((value) => <button className={priority === value ? "filter-active" : ""} key={value} onClick={() => setPriority(value)} type="button">{value}</button>)}</div><label className="checkbox-label"><input checked={includeCompleted} onChange={(event) => setIncludeCompleted(event.target.checked)} type="checkbox" /> Show completed</label></div>
    {error && <div className="inline-state error-state" role="alert"><strong>Tasks unavailable.</strong><span>{error}</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div>}
    {loading ? <div className="task-list-placeholder" role="status">Loading your tasks…</div> : visibleTasks.length === 0 ? <div className="empty-state task-empty"><span className="empty-icon">□</span><strong>No tasks here yet</strong><span>Add a task above to make progress visible.</span></div> : <div className="task-list">{visibleTasks.map((task) => <TaskRow includeCompleted={includeCompleted} key={task.id} onChange={replaceTask} onError={setError} task={task} />)}</div>}
  </section>;
}
