"use client";

import { useCallback, useEffect, useState } from "react";
import { listNotifications, markAllNotificationsRead, markNotificationRead, type Notification } from "../lib/notifications";

export function NotificationCenter() {
  const [items, setItems] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(false);

  const refresh = useCallback(async () => { try { const result = await listNotifications(); setItems(result.items); setUnread(result.unread_count); setError(false); } catch { setError(true); } }, []);
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 30_000); return () => window.clearInterval(timer); }, [refresh]);

  async function read(id: string) { await markNotificationRead(id); setItems((current) => current.map((item) => item.id === id ? { ...item, read_at: new Date().toISOString() } : item)); setUnread((count) => Math.max(0, count - 1)); }
  async function readAll() { await markAllNotificationsRead(); setItems((current) => current.map((item) => ({ ...item, read_at: item.read_at ?? new Date().toISOString() }))); setUnread(0); }

  return <div className="notification-wrap"><button aria-expanded={open} aria-label={`${unread} unread notifications`} className="icon-button notification-button" onClick={() => setOpen((value) => !value)} type="button">♢{unread > 0 && <span className="notification-badge">{unread > 9 ? "9+" : unread}</span>}</button>{open && <section aria-label="Notifications" className="notification-panel"><div className="notification-heading"><strong>Notifications</strong>{unread > 0 && <button className="text-button" onClick={() => void readAll()} type="button">Mark all read</button>}</div>{error ? <p className="conversation-empty">Notifications are temporarily unavailable.</p> : items.length === 0 ? <p className="conversation-empty">You are all caught up.</p> : items.map((item) => <button className={`notification-item${item.read_at ? " notification-read" : ""}`} key={item.id} onClick={() => void read(item.id)} type="button"><strong>{item.title}</strong><span>{item.body}</span><small>{new Date(item.created_at).toLocaleString()}</small></button>)}</section>}</div>;
}
