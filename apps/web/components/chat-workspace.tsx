"use client";

import { useCallback, useEffect, useState } from "react";
import { readOpenWebUIStatus, type OpenWebUIStatus } from "../lib/openwebui";

export function ChatWorkspace({
  onOpenAdmin,
  onOpenAssistant,
}: {
  onOpenAdmin?: () => void;
  onOpenAssistant?: () => void;
}) {
  const [status, setStatus] = useState<OpenWebUIStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [frameFailed, setFrameFailed] = useState(false);
  const [frameKey, setFrameKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const next = await readOpenWebUIStatus();
      setStatus(next);
      setError(null);
      setFrameFailed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Chat unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const ready = Boolean(status?.enabled && status.url);
  const canEmbed = ready && status?.embed !== false && !frameFailed;

  return (
    <section aria-labelledby="chat-heading" className="chat-workspace section-block">
      <div className="chat-toolbar">
        <div>
          <p className="eyebrow">{ready ? "Open WebUI · local" : "Chat"}</p>
          <h2 id="chat-heading">{status?.label ?? "Chat"}</h2>
          <p className="chat-toolbar-detail">
            {loading
              ? "Checking Open WebUI integration…"
              : status?.detail ?? "Full multi-model chat hosted on this Pi."}
          </p>
        </div>
        <div className="chat-toolbar-actions">
          {ready && status?.url ? (
            <>
              <a className="refresh-button" href={status.url} rel="noreferrer" target="_blank">
                Open in new tab
              </a>
              <button
                className="text-button"
                onClick={() => {
                  setFrameFailed(false);
                  setFrameKey((value) => value + 1);
                }}
                type="button"
              >
                Reload
              </button>
            </>
          ) : null}
          {onOpenAssistant ? (
            <button className="text-button" onClick={onOpenAssistant} type="button">
              Nexus Assistant
            </button>
          ) : null}
          {onOpenAdmin ? (
            <button className="text-button" onClick={onOpenAdmin} type="button">
              Configure
            </button>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="inline-state error-state" role="alert">
          <strong>Chat unavailable.</strong>
          <span>{error}</span>
          <button className="text-button" onClick={() => void load()} type="button">
            Retry
          </button>
        </div>
      ) : null}

      {loading ? (
        <div className="chat-frame-shell chat-frame-placeholder" role="status">
          Loading Open WebUI…
        </div>
      ) : canEmbed && status?.url ? (
        <div className="chat-frame-shell">
          <iframe
            allow="clipboard-read; clipboard-write; microphone; fullscreen"
            className="chat-frame"
            key={frameKey}
            onError={() => setFrameFailed(true)}
            referrerPolicy="no-referrer"
            src={status.url}
            title={status.label || "Open WebUI"}
          />
        </div>
      ) : ready && status?.url && (frameFailed || !status.embed) ? (
        <div className="chat-frame-shell chat-frame-placeholder">
          <div className="chat-setup-card">
            <strong>{frameFailed ? "Embedded view blocked" : "Embed is off"}</strong>
            <p>
              {frameFailed
                ? "Your Open WebUI instance refused to load inside Nexus (common with strict frame headers). Use the full window instead — it is the same app on this Pi."
                : "Embedding is disabled in Admin. You can still open Open WebUI directly."}
            </p>
            <div className="chat-setup-actions">
              <a className="primary-button" href={status.url} rel="noreferrer" target="_blank">
                Launch Open WebUI
              </a>
              {frameFailed ? (
                <button
                  className="text-button"
                  onClick={() => {
                    setFrameFailed(false);
                    setFrameKey((value) => value + 1);
                  }}
                  type="button"
                >
                  Try embed again
                </button>
              ) : null}
            </div>
            <code className="chat-url-code">{status.url}</code>
          </div>
        </div>
      ) : (
        <div className="chat-frame-shell chat-frame-placeholder">
          <div className="chat-setup-card">
            <strong>Connect Open WebUI</strong>
            <p>
              Your Raspberry Pi already runs Open WebUI (typically on port <code>8080</code>). Point Nexus at it for a full multi-model
              chat UI with history, models, and tools — next to the built-in Nexus Assistant for system/tasks/notes.
            </p>
            <ol className="chat-setup-steps">
              <li>Confirm Open WebUI is up (docker container <code>open-webui</code> on this Pi).</li>
              <li>Open Admin → AI and set the Open WebUI URL, e.g. <code>http://192.168.1.46:8080</code>.</li>
              <li>Return here for an embedded studio-style chat, or open it in a new tab.</li>
            </ol>
            <div className="chat-setup-actions">
              {onOpenAdmin ? (
                <button className="primary-button" onClick={onOpenAdmin} type="button">
                  Open Admin setup
                </button>
              ) : null}
              {onOpenAssistant ? (
                <button className="refresh-button" onClick={onOpenAssistant} type="button">
                  Use Nexus Assistant
                </button>
              ) : null}
              <a className="text-button" href="http://192.168.1.46:8080" rel="noreferrer" target="_blank">
                Try http://192.168.1.46:8080
              </a>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
