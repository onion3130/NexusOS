"use client";

import { useCallback, useEffect, useState } from "react";
import { readSystemOverview, type HealthLevel, type SystemOverview } from "../lib/system";

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

function toneFor(level: HealthLevel): string {
  if (level === "critical") return "danger";
  if (level === "warning") return "warning";
  if (level === "unavailable") return "muted";
  return "green";
}

function Metric({
  label,
  value,
  detail,
  level,
  levelLabel,
  progress,
}: {
  label: string;
  value: string;
  detail: string;
  level: HealthLevel;
  levelLabel: string;
  progress?: number | null;
}) {
  const width = progress === null || progress === undefined ? null : Math.max(0, Math.min(100, progress));
  return (
    <article className={`telemetry-card health-${level}`}>
      <div className={`metric-indicator ${toneFor(level)}`} />
      <div className="telemetry-card-top">
        <p>{label}</p>
        <span className={`health-chip health-chip-${level}`}>{levelLabel}</span>
      </div>
      <strong>{value}</strong>
      <span>{detail}</span>
      {width !== null && (
        <div aria-hidden="true" className="telemetry-meter">
          <span className={`telemetry-meter-fill health-fill-${level}`} style={{ width: `${width}%` }} />
        </div>
      )}
    </article>
  );
}

function TelemetrySkeleton() {
  return (
    <div aria-label="Loading system telemetry" className="telemetry-grid" role="status">
      {["CPU", "Memory", "Storage", "Temperature", "Uptime", "Network"].map((label) => (
        <div className="telemetry-card skeleton-card" key={label}>
          <span className="skeleton-line short" />
          <span className="skeleton-line" />
          <span className="skeleton-line tiny" />
        </div>
      ))}
    </div>
  );
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
    const interval = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const overall = overview?.health.level ?? "unavailable";

  return (
    <section aria-labelledby="system-overview-heading" className="section-block system-overview">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Raspberry Pi 5</p>
          <h2 id="system-overview-heading">System overview</h2>
        </div>
        <div className="system-heading-actions">
          {overview && <span className={`health-chip health-chip-${overall} health-chip-lg`}>{overview.health.label}</span>}
          <button className="refresh-button" disabled={refreshing} onClick={() => void refresh()} type="button">
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {error && !overview ? (
        <div className="inline-state error-state" role="alert">
          <strong>System telemetry unavailable.</strong>
          <span>Check the authenticated API connection and try again.</span>
          <button className="text-button" onClick={() => void refresh()} type="button">
            Retry
          </button>
        </div>
      ) : overview ? (
        <>
          {error && (
            <div className="inline-state warning-state" role="status">
              <strong>Showing the last successful reading.</strong>
              <span>Refresh failed; the next check will retry automatically.</span>
            </div>
          )}

          {overall !== "healthy" && (
            <div className={`inline-state ${overall === "critical" ? "error-state" : "warning-state"}`} role="status">
              <strong>{overview.health.label}.</strong>
              <span>{overview.health.reasons.join(" · ")}</span>
            </div>
          )}

          <div className="telemetry-grid">
            <Metric
              detail={`${overview.cpu.cpu_count ?? "—"} logical cores · load ${overview.cpu.load_1m ?? "—"}`}
              label="CPU usage"
              level={overview.cpu.health.level}
              levelLabel={overview.cpu.health.label}
              progress={overview.cpu.usage_percent}
              value={overview.cpu.usage_percent === null ? "Unavailable" : `${overview.cpu.usage_percent}%`}
            />
            <Metric
              detail={`${formatBytes(overview.memory.available_bytes)} available`}
              label="Memory"
              level={overview.memory.health.level}
              levelLabel={overview.memory.health.label}
              progress={overview.memory.used_percent}
              value={overview.memory.used_percent === null ? "Unavailable" : `${overview.memory.used_percent}% used`}
            />
            <Metric
              detail={`${formatBytes(overview.storage.free_bytes)} free`}
              label="Storage"
              level={overview.storage.health.level}
              levelLabel={overview.storage.health.label}
              progress={overview.storage.used_percent}
              value={overview.storage.used_percent === null ? "Unavailable" : `${overview.storage.used_percent}% used`}
            />
            <Metric
              detail={overview.temperature.source_name ?? "Thermal zone"}
              label="Temperature"
              level={overview.temperature.health.level}
              levelLabel={overview.temperature.health.label}
              progress={
                overview.temperature.celsius === null
                  ? null
                  : Math.min(100, Math.round((overview.temperature.celsius / 90) * 100))
              }
              value={overview.temperature.celsius === null ? "Unavailable" : `${overview.temperature.celsius.toFixed(1)}°C`}
            />
            <Metric
              detail="Since system boot"
              label="Uptime"
              level={overview.uptime.health.level}
              levelLabel={overview.uptime.health.label}
              value={formatUptime(overview.uptime.seconds)}
            />
            <Metric
              detail={`${overview.network.interfaces.length} interface(s) readable`}
              label="Network"
              level={overview.network.health.level}
              levelLabel={overview.network.health.label}
              value={overview.network.source.available ? "Online" : "Unavailable"}
            />
          </div>

          <div className="system-footnote">
            <span className={`system-health-dot ${overall === "healthy" ? "ok" : overall === "critical" ? "danger" : "warning"}`} />
            {overview.health.label}
            <span>·</span>
            {overview.health.reasons[0]}
            <span>·</span>
            Last checked {new Date(overview.checked_at).toLocaleTimeString()}
            <span>·</span>
            Auto-refresh 15s
          </div>

          <div className={`service-boundary service-boundary-${overview.service_status.health.level}`}>
            <div className="service-boundary-heading">
              <span aria-hidden="true">⌁</span>
              <div>
                <strong>
                  {overview.service_status.source.available
                    ? overview.service_status.containers_available
                      ? "Containers detected"
                      : "Stack services detected"
                    : "Service status limited"}
                </strong>
                <span>
                  {overview.service_status.source.available
                    ? overview.service_status.containers_available
                      ? "Read-only Docker metadata from the configured socket boundary."
                      : "Private Compose network auto-detect (no Docker socket required)."
                    : overview.service_status.reason === "docker_socket_unavailable"
                      ? "Docker socket could not be read. Stack DNS detection also failed."
                      : "Service visibility is limited without Docker socket or Compose network names."}
                </span>
              </div>
              <span className={`health-chip health-chip-${overview.service_status.health.level}`}>
                {overview.service_status.health.label}
              </span>
            </div>
            {overview.service_status.units.length > 0 ? (
              <div className="service-unit-grid">
                {overview.service_status.units.map((unit) => (
                  <article className={`service-unit health-${unit.health}`} key={`${unit.kind}-${unit.name}`}>
                    <div>
                      <strong>{unit.name}</strong>
                      <span>{unit.detail ?? unit.kind}</span>
                    </div>
                    <em className={`health-chip health-chip-${unit.health}`}>{unit.state}</em>
                  </article>
                ))}
              </div>
            ) : (
              <p className="service-boundary-empty">No service units reported yet.</p>
            )}
          </div>
        </>
      ) : (
        <TelemetrySkeleton />
      )}
    </section>
  );
}
