"use client";

import { useCallback, useEffect, useState } from "react";
import { readSystemOverview, type SystemOverview } from "../lib/system";

function formatBytes(value: number | null): string {
  if (value === null) return "Unavailable";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(amount >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatUptime(seconds: number | null): string {
  if (seconds === null) return "Unavailable";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return days > 0 ? `${days}d ${hours}h` : `${hours}h ${minutes}m`;
}

function Metric({ label, value, detail, tone = "green" }: { label: string; value: string; detail: string; tone?: string }) {
  return (
    <article className="telemetry-card">
      <div className={`metric-indicator ${tone}`} />
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

function TelemetrySkeleton() {
  return <div aria-label="Loading system telemetry" className="telemetry-grid" role="status">{["CPU", "Memory", "Storage", "Temperature", "Uptime", "Network"].map((label) => <div className="telemetry-card skeleton-card" key={label}><span className="skeleton-line short" /><span className="skeleton-line" /><span className="skeleton-line tiny" /></div>)}</div>;
}

export function SystemOverview() {
  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [error, setError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      setOverview(await readSystemOverview());
      setError(false);
    } catch {
      setError(true);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  return (
    <section aria-labelledby="system-overview-heading" className="section-block">
      <div className="section-heading">
        <div><p className="eyebrow">Raspberry Pi 5</p><h2 id="system-overview-heading">System overview</h2></div>
        <button className="refresh-button" disabled={refreshing} onClick={() => void refresh()} type="button">{refreshing ? "Refreshing…" : "Refresh"}</button>
      </div>
      {error && !overview ? (
        <div className="inline-state error-state" role="alert"><strong>System telemetry unavailable.</strong><span>Check the authenticated API connection and try again.</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div>
      ) : overview ? (
        <>
          {error && <div className="inline-state warning-state" role="status"><strong>Showing the last successful reading.</strong><span>Refresh failed; the next check will retry automatically.</span></div>}
          <div className="telemetry-grid">
            <Metric detail={`${overview.cpu.cpu_count ?? "—"} logical cores · load ${overview.cpu.load_1m ?? "—"}`} label="CPU usage" tone="green" value={overview.cpu.usage_percent === null ? "Unavailable" : `${overview.cpu.usage_percent}%`} />
            <Metric detail={`${formatBytes(overview.memory.available_bytes)} available`} label="Memory" tone="purple" value={overview.memory.used_percent === null ? "Unavailable" : `${overview.memory.used_percent}% used`} />
            <Metric detail={`${formatBytes(overview.storage.free_bytes)} free`} label="Storage" tone="blue" value={overview.storage.used_percent === null ? "Unavailable" : `${overview.storage.used_percent}% used`} />
            <Metric detail={overview.temperature.source_name ?? "Thermal zone"} label="Temperature" tone="orange" value={overview.temperature.celsius === null ? "Unavailable" : `${overview.temperature.celsius.toFixed(1)}°C`} />
            <Metric detail="Since system boot" label="Uptime" tone="green" value={formatUptime(overview.uptime.seconds)} />
            <Metric detail={`${overview.network.interfaces.length} interface(s) readable`} label="Network" tone="blue" value={overview.network.source.available ? "Online" : "Unavailable"} />
          </div>
          <div className="system-footnote"><span className={`system-health-dot ${overview.status}`} />{overview.status === "ok" ? "All telemetry sources readable" : "Some telemetry sources unavailable"}<span>·</span>Last checked {new Date(overview.checked_at).toLocaleTimeString()}</div>
        </>
      ) : <TelemetrySkeleton />}
      <div className="service-boundary"><span aria-hidden="true">⌁</span><div><strong>Service and container status is not exposed yet</strong><span>No Docker socket or host-control boundary is added in this read-only milestone.</span></div></div>
    </section>
  );
}
