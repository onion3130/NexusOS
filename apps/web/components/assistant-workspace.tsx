"use client";

import { useCallback, useEffect, useState } from "react";
import { readOpenWebUIStatus, type OpenWebUIStatus } from "../lib/openwebui";

/**
 * Assistant is Open WebUI, embedded in Nexus and linked to the shared filesystem.
 * The older tool-gateway chat is no longer the primary surface.
 */
export function AssistantWorkspace({
  onOpenAdmin,
}: {
  onOpenNote?: (id: string) => void;
  onOpenSource?: (id: string) => void;
  onOpenAdmin?: () => void;
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
      setError(reason instanceof Error ? reason.message : "Assistant unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const ready = Boolean(status?.enabled && status.url);
  const canEmbed = ready && status?.embed !== false && !frameFailed;
  const sharedHost = status?.filesystem?.host_path;
  const sharedContainer = status?.filesystem?.container_path;

  return (
    <section aria-labelledby="assistant-heading" className="chat-workspace section-block">
      <div className="chat-toolbar">
        <div>
          <p className="eyebrow">{ready ? "Open WebUI · Nexus filesystem" : "Assistant"}</p>
          <h2 id="assistant-heading">{status?.label ?? "Assistant"}</h2>
          <p className="chat-toolbar-detail">
            {loading
              ? "Connecting to Open WebUI…"
              : ready
                ? "Full multi-model chat on this Pi. Shared Nexus files are available inside Open WebUI for Knowledge / attachments."
                : status?.detail ?? "Connect Open WebUI so Assistant becomes your local chat studio."}
          </p>
          {ready && sharedHost ? (
            <p className="chat-fs-hint">
              Shared folder: <code>{sharedHost}</code>
              {sharedContainer ? (
                <>
                  {" "}
                  → Open WebUI <code>{sharedContainer}</code>
                </>
              ) : null}
            </p>
          ) : null}
        </div>
        <div className="chat-toolbar-actions">
          {ready && status?.url ? (
            <>
              <a className="refresh-button" href={status.url} rel="noreferrer" target="_blank">
                Open full window
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
          {onOpenAdmin ? (
            <button className="text-button" onClick={onOpenAdmin} type="button">
              Configure
            </button>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="inline-state error-state" role="alert">
          <strong>Assistant unavailable.</strong>
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
            title={status.label || "Nexus Assistant"}
          />
        </div>
      ) : ready && status?.url && (frameFailed || !status.embed) ? (
        <div className="chat-frame-shell chat-frame-placeholder">
          <div className="chat-setup-card">
            <strong>{frameFailed ? "Embedded view blocked" : "Embed is off"}</strong>
            <p>
              {frameFailed
                ? "Open WebUI refused to load inside this page (frame headers). Use the full window — same app, same models, same shared files."
                : "Embedding is disabled in Admin. Launch Open WebUI in a full window instead."}
            </p>
            <div className="chat-setup-actions">
              <a className="primary-button" href={status.url} rel="noreferrer" target="_blank">
                Launch Assistant
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
            <strong>Assistant = Open WebUI</strong>
            <p>
              Nexus uses your Pi-hosted Open WebUI as the assistant (multi-model chat, history, Knowledge). Point it at the local
              instance and link the shared filesystem so chat can use files from Nexus.
            </p>
            <ol className="chat-setup-steps">
              <li>
                Confirm Open WebUI is running (usually <code>http://192.168.1.46:8080</code>).
              </li>
              <li>
                Admin → AI: save Open WebUI URL (or set <code>OPENWEBUI_URL</code>).
              </li>
              <li>
                Drop files into the shared folder on the Pi (<code>…/nexus-data/shared</code>) — mounted into Open WebUI as{" "}
                <code>/data/nexus</code>.
              </li>
            </ol>
            <div className="chat-setup-actions">
              {onOpenAdmin ? (
                <button className="primary-button" onClick={onOpenAdmin} type="button">
                  Open Admin setup
                </button>
              ) : null}
              <a className="refresh-button" href="http://192.168.1.46:8080" rel="noreferrer" target="_blank">
                Try Open WebUI
              </a>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
