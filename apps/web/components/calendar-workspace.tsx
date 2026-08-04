"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addEventReminder,
  createCategory,
  createEvent,
  deleteCategory,
  deleteEvent,
  deleteReminder,
  listCategories,
  listEvents,
  updateEvent,
  type CalendarCategory,
  type CalendarEvent,
} from "../lib/calendar";

function eventLabel(value: string, allDay: boolean): string {
  const date = new Date(value);
  if (allDay) return date.toLocaleDateString([], { dateStyle: "medium" });
  return date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function categoryColor(category: CalendarCategory | null): string {
  return category?.color ?? "var(--accent)";
}

function EventRow({ event, onChanged, onRemoved, onError }: { event: CalendarEvent; onChanged: (event: CalendarEvent) => void; onRemoved: (id: string) => void; onError: (message: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(event.title);
  const [editStart, setEditStart] = useState(event.starts_at.slice(0, 16));
  const [editEnd, setEditEnd] = useState(event.ends_at.slice(0, 16));
  const [reminderMinutes, setReminderMinutes] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    try { await action(); } catch (reason) { onError(reason instanceof Error ? reason.message : "Calendar update failed"); } finally { setBusy(false); }
  }
  function saveEdit() {
    void run(async () => {
      onChanged(await updateEvent(event.id, { title: editTitle.trim(), starts_at: new Date(editStart).toISOString(), ends_at: new Date(editEnd).toISOString() }));
      setEditing(false);
    });
  }
  function remove() {
    if (!window.confirm(`Delete event “${event.title}”?`)) return;
    void run(async () => { await deleteEvent(event.id); onRemoved(event.id); });
  }
  function addReminder() {
    if (!reminderMinutes) return;
    void run(async () => { onChanged(await addEventReminder(event.id, { offset_minutes: Number(reminderMinutes) })); setReminderMinutes(""); });
  }
  function cancelReminder(id: string) {
    void run(async () => {
      await deleteReminder(id);
      onChanged({ ...event, reminders: event.reminders.filter((reminder) => reminder.id !== id) });
    });
  }

  return <article className="event-row">
    <span aria-hidden="true" className="event-time-line" style={{ background: categoryColor(event.category) }}>
      <time>{new Date(event.starts_at).toLocaleDateString([], { day: "2-digit", month: "short" })}</time>
      <span>{new Date(event.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
    </span>
    <div className="event-row-copy">
      {editing ? <div className="task-edit-fields"><input aria-label="Edit event title" maxLength={160} onChange={(event) => setEditTitle(event.target.value)} value={editTitle} /><input aria-label="Edit start time" onChange={(event) => setEditStart(event.target.value)} type="datetime-local" value={editStart} /><input aria-label="Edit end time" onChange={(event) => setEditEnd(event.target.value)} type="datetime-local" value={editEnd} /><button className="primary-button" disabled={!editTitle.trim() || busy} onClick={saveEdit} type="button">Save</button><button className="text-button" onClick={() => setEditing(false)} type="button">Cancel</button></div> : <>
        <div className="event-row-heading">
          <strong>{event.title}</strong>
          {event.category && <span className="event-category" style={{ borderColor: categoryColor(event.category), color: categoryColor(event.category) }}>{event.category.name}</span>}
        </div>
        <p>{eventLabel(event.starts_at, event.all_day)} – {eventLabel(event.ends_at, event.all_day)}{event.location ? ` · ${event.location}` : ""}</p>
        {event.reminders.filter((reminder) => reminder.status === "pending").length > 0 && <div className="event-reminder-list">{event.reminders.filter((reminder) => reminder.status === "pending").map((reminder) => <span key={reminder.id}>♢ reminder {reminder.offset_minutes !== null ? `${reminder.offset_minutes}m before` : new Date(reminder.scheduled_for).toLocaleString([], { dateStyle: "short", timeStyle: "short" })} <button className="text-button" disabled={busy} onClick={() => cancelReminder(reminder.id)} type="button">Remove</button></span>)}</div>}
        <div className="event-row-actions"><button className="text-button" disabled={busy} onClick={() => setEditing(true)} type="button">Edit</button><span className="reminder-inline"><input aria-label={`Reminder minutes before ${event.title}`} inputMode="numeric" min="0" onChange={(event) => setReminderMinutes(event.target.value)} placeholder="Minutes before" type="number" value={reminderMinutes} /><button className="text-button" disabled={!reminderMinutes || busy} onClick={addReminder} type="button">Add reminder</button></span></div>
      </>}
    </div>
    <button aria-label={`Delete ${event.title}`} className="task-delete" disabled={busy} onClick={remove} type="button">⌫</button>
  </article>;
}

export function CalendarWorkspace() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [categories, setCategories] = useState<CalendarCategory[]>([]);
  const [title, setTitle] = useState("");
  const [startAt, setStartAt] = useState("");
  const [endAt, setEndAt] = useState("");
  const [allDay, setAllDay] = useState(false);
  const [location, setLocation] = useState("");
  const [category, setCategory] = useState("");
  const [reminderMinutes, setReminderMinutes] = useState("");
  const [categoryDraft, setCategoryDraft] = useState("");
  const [categoryColorDraft, setCategoryColorDraft] = useState("#7b6cff");
  const [range, setRange] = useState<"month" | "week">("month");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const now = new Date();
      const from = range === "week" ? new Date(now.getTime() - 7 * 86400000) : new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const to = range === "week" ? new Date(now.getTime() + 14 * 86400000) : new Date(now.getFullYear(), now.getMonth() + 2, 0, 23, 59, 59);
      const [items, cats] = await Promise.all([listEvents(from.toISOString(), to.toISOString()), listCategories()]);
      setEvents(items);
      setCategories(cats);
      setError(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Calendar unavailable"); } finally { setLoading(false); }
  }, [range]);
  useEffect(() => { void refresh(); }, [refresh]);

  const upcoming = useMemo(() => {
    const now = new Date().toISOString();
    return events.filter((event) => event.ends_at >= now).sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  }, [events]);

  async function add(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim() || !startAt || saving) return;
    setSaving(true); setError(null);
    try {
      const created = await createEvent({ title: title.trim(), starts_at: new Date(startAt).toISOString(), ends_at: new Date(endAt || startAt).toISOString(), all_day: allDay, location: location.trim() || null, category: category.trim() || null, reminders: reminderMinutes ? [{ offset_minutes: Number(reminderMinutes) }] : [] });
      setEvents((items) => [...items, created]);
      setTitle(""); setStartAt(""); setEndAt(""); setLocation(""); setCategory(""); setReminderMinutes(""); setAllDay(false);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create event"); } finally { setSaving(false); }
  }

  function addCategory() {
    if (!categoryDraft.trim()) return;
    void (async () => {
      try {
        const created = await createCategory(categoryDraft.trim(), categoryColorDraft);
        setCategories((items) => [...items, created]);
        setCategoryDraft(""); setCategoryColorDraft("#7b6cff");
      } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create category"); }
    })();
  }
  function removeCategory(id: string) {
    if (!window.confirm("Delete this category? Events keep their schedule.")) return;
    void (async () => {
      try { await deleteCategory(id); setCategories((items) => items.filter((item) => item.id !== id)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to delete category"); }
    })();
  }

  return <section aria-labelledby="calendar-heading" className="calendar-workspace section-block">
    <div className="section-heading"><div><p className="eyebrow">Time &amp; reminders</p><h2 id="calendar-heading">Calendar</h2></div><div className="event-toolbar"><div className="task-filters"><button className={range === "month" ? "filter-active" : ""} onClick={() => setRange("month")} type="button">Month</button><button className={range === "week" ? "filter-active" : ""} onClick={() => setRange("week")} type="button">Week</button></div><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div></div>

    <form className="task-create-form" onSubmit={add}><label htmlFor="event-title">New event</label><div className="task-create-main"><input id="event-title" maxLength={160} onChange={(event) => setTitle(event.target.value)} placeholder="What is happening?" value={title} /><button className="primary-button" disabled={!title.trim() || !startAt || saving} type="submit">{saving ? "Adding…" : "Add event"}</button></div><div className="task-create-options"><input aria-label="Starts at" onChange={(event) => setStartAt(event.target.value)} required type="datetime-local" value={startAt} /><input aria-label="Ends at" onChange={(event) => setEndAt(event.target.value)} type="datetime-local" value={endAt} /><input aria-label="Location" maxLength={255} onChange={(event) => setLocation(event.target.value)} placeholder="Location" value={location} /><input aria-label="Category" list="calendar-categories" maxLength={64} onChange={(event) => setCategory(event.target.value)} placeholder="Category" value={category} /><datalist id="calendar-categories">{categories.map((item) => <option key={item.id} value={item.name} />)}</datalist><input aria-label="Reminder minutes before" inputMode="numeric" min="0" onChange={(event) => setReminderMinutes(event.target.value)} placeholder="Reminder minutes before" type="number" value={reminderMinutes} /><label className="checkbox-label"><input checked={allDay} onChange={(event) => setAllDay(event.target.checked)} type="checkbox" /> All day</label></div></form>

    <div className="event-category-manager"><strong>Categories</strong><div className="event-category-fields"><input aria-label="Category name" maxLength={64} onChange={(event) => setCategoryDraft(event.target.value)} placeholder="New category" value={categoryDraft} /><input aria-label="Category color" onChange={(event) => setCategoryColorDraft(event.target.value)} type="color" value={categoryColorDraft} /><button className="text-button" disabled={!categoryDraft.trim()} onClick={addCategory} type="button">Add category</button></div>{categories.map((item) => <span className="event-category event-category-managed" key={item.id} style={{ borderColor: item.color ?? "var(--line-strong)", color: item.color ?? "var(--muted-strong)" }}>{item.name}<button aria-label={`Delete category ${item.name}`} className="category-delete" onClick={() => removeCategory(item.id)} type="button">×</button></span>)}</div>

    {error && <div className="inline-state error-state" role="alert"><strong>Calendar unavailable.</strong><span>{error}</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div>}
    {loading ? <div className="task-list-placeholder" role="status">Loading your events…</div> : upcoming.length === 0 ? <div className="empty-state task-empty"><span className="empty-icon">▦</span><strong>No upcoming events</strong><span>Add an event above to keep your schedule visible.</span></div> : <div className="event-list">{upcoming.map((event) => <EventRow event={event} key={event.id} onChanged={(updated) => setEvents((items) => items.map((item) => item.id === updated.id ? updated : item))} onError={setError} onRemoved={(id) => setEvents((items) => items.filter((item) => item.id !== id))} />)}</div>}
  </section>;
}
