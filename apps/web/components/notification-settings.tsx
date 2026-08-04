"use client";

import { useCallback, useEffect, useState } from "react";
import { readNotificationSettings, testNotificationSettings, type NotificationSettings, type TestSendResult } from "../lib/notifications";

function ChannelCard({ title, icon, enabled, configured, fields, footnote }: { title: string; icon: string; enabled: boolean; configured: boolean; fields: Array<[string, string | null]>; footnote: string }) {
  return (
    <article className="channel-card">
      <div className="channel-card-heading">
        <span className="status-card-icon" aria-hidden="true">{icon}</span>
        <div>
          <p className="eyebrow">{enabled ? "Enabled" : "Disabled"}</p>
          <h3>{title}</h3>
        </div>
        <span className={`channel-pill ${enabled ? (configured ? "pill-green" : "pill-amber") : "pill-muted"}`}>{enabled ? (configured ? "Configured" : "Incomplete") : "Off"}</span>
      </div>
      <dl className="channel-fields">
        {fields.map(([label, value]) => (
          <div key={label}><dt>{label}</dt><dd>{value || "—"}</dd></div>
        ))}
      </dl>
      <p className="channel-footnote">{footnote}</p>
    </article>
  );
}

export function NotificationSettingsWorkspace() {
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [results, setResults] = useState<TestSendResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setSettings(await readNotificationSettings());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Notification settings unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function sendTest() {
    setSending(true);
    setResults(null);
    setError(null);
    try {
      setResults(await testNotificationSettings());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Test send unavailable");
    } finally {
      setSending(false);
    }
  }

  const noChannels = settings !== null && !settings.email_enabled && !settings.push_enabled;

  return <section aria-labelledby="notifications-settings-heading" className="notification-settings section-block">
    <div className="section-heading"><div><p className="eyebrow">Outbound delivery</p><h2 id="notifications-settings-heading">Notifications</h2></div><button className="refresh-button" disabled={loading || sending} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div>
    {error && <div className="inline-state error-state" role="alert"><strong>Notification settings unavailable.</strong><span>{error}</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div>}
    {loading ? <div className="skeleton-card"><div className="skeleton-line" /><div className="skeleton-line short" /></div> : settings === null ? null : <>
      <div className="inline-state warning-state"><strong>Configured on the server.</strong><span>Channels are enabled through environment variables; secrets stay server-side and are never returned here.</span></div>
      {noChannels && <div className="inline-state"><strong>No channels enabled.</strong><span>Set NOTIFICATION_EMAIL_ENABLED and/or NOTIFICATION_PUSH_ENABLED in the server environment to receive reminders outside the dashboard.</span></div>}
      <div className="channel-grid">
        <ChannelCard configured={settings.email_configured} enabled={settings.email_enabled} fields={[["SMTP host", settings.email_smtp_host], ["User", settings.email_smtp_user], ["From", settings.email_from], ["To", settings.email_to], ["Credentials", settings.email_credentials_set ? "Set (hidden)" : "Not set"]]} footnote="Email reminders use the configured SMTP relay with a bounded timeout and truncated payloads." icon="✉" title="Email" />
        <ChannelCard configured={settings.push_configured} enabled={settings.push_enabled} fields={[["Endpoint", settings.push_url], ["Topic", settings.push_topic], ["Token", settings.push_token_set ? "Set (hidden)" : "Not set"]]} footnote="Push reminders use a ntfy-compatible HTTPS endpoint; tokens are sent as bearer credentials." icon="⇪" title="Push" />
      </div>
      <div className="test-row">
        <button className="primary-button" disabled={sending || noChannels} onClick={() => void sendTest()} type="button">{sending ? "Sending…" : "Send test notification"}</button>
        {results && <div className="test-results">{results.map((item) => <span className={`test-result ${item.ok ? "test-ok" : "test-fail"}`} key={item.channel}>{item.ok ? `✓ ${item.channel} delivered` : `✗ ${item.channel}: ${item.error_code ?? "failed"}`}</span>)}</div>}
      </div>
    </>}
  </section>;
}
