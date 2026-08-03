"use client";

export function ViewLoading({ label }: { label: string }) {
  return <div className="workspace-view-state" role="status"><span className="loading-orb" aria-hidden="true" /><strong>Loading {label}…</strong></div>;
}

export function ViewError({ label, message, onRetry }: { label: string; message: string; onRetry: () => void }) {
  return <div className="inline-state error-state" role="alert"><strong>{label} unavailable.</strong><span>{message}</span><button className="text-button" onClick={onRetry} type="button">Retry</button></div>;
}

export function ViewEmpty({ title, description }: { title: string; description: string }) {
  return <div className="empty-state workspace-empty"><span className="empty-icon" aria-hidden="true">⌁</span><strong>{title}</strong><span>{description}</span></div>;
}

export function formatViewDate(value: string | null): string {
  return value ? new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "Unavailable";
}

export function formatViewBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;
}
