"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  approveToolCall,
  createConversation,
  listConversations,
  readAssistantProvider,
  readConversation,
  rejectToolCall,
  sendMessage,
  type AssistantProviderStatus,
  type Conversation,
  type ConversationSummary,
} from "../lib/assistant";
import { AssistantActionConfirmation } from "./assistant-action-confirmation";
import { AssistantSourceCitations } from "./assistant-source-citations";

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

function ConversationSidebar({
  items,
  selected,
  onSelect,
  onCreate,
  query,
  onQuery,
}: {
  items: ConversationSummary[];
  selected: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  query: string;
  onQuery: (value: string) => void;
}) {
  const filtered = items.filter((item) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (item.title ?? "new conversation").toLowerCase().includes(q);
  });

  return (
    <aside aria-label="Conversations" className="nx-chat-sidebar">
      <div className="nx-chat-sidebar-head">
        <div>
          <p className="eyebrow">Nexus</p>
          <strong>Chats</strong>
        </div>
        <button aria-label="New conversation" className="nx-chat-new" onClick={onCreate} type="button">
          +
        </button>
      </div>
      <label className="nx-chat-search">
        <span aria-hidden="true">⌕</span>
        <input
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Search chats…"
          type="search"
          value={query}
        />
      </label>
      <div className="nx-chat-sidebar-list">
        {filtered.length === 0 ? (
          <p className="nx-chat-sidebar-empty">{items.length === 0 ? "No chats yet. Start one." : "No matches."}</p>
        ) : (
          filtered.map((item) => (
            <button
              className={`nx-chat-thread${item.id === selected ? " selected" : ""}`}
              key={item.id}
              onClick={() => onSelect(item.id)}
              type="button"
            >
              <span className="nx-chat-thread-avatar" aria-hidden="true">
                ✦
              </span>
              <span className="nx-chat-thread-copy">
                <strong>{item.title ?? "New conversation"}</strong>
                <span>
                  {item.message_count} message{item.message_count === 1 ? "" : "s"}
                </span>
              </span>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}

export function AssistantWorkspace({
  onOpenNote,
  onOpenSource,
  onOpenAdmin,
}: {
  onOpenNote?: (id: string) => void;
  onOpenSource?: (id: string) => void;
  onOpenAdmin?: () => void;
}) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorKind, setErrorKind] = useState<"load" | "send" | null>(null);
  const [pendingAction, setPendingAction] = useState<{ id: string; tool: string; arguments: Record<string, unknown> } | null>(null);
  const [groundingEnabled, setGroundingEnabled] = useState(true);
  const [groundingMode, setGroundingMode] = useState<"lexical" | "semantic" | "hybrid">("hybrid");
  const [provider, setProvider] = useState<AssistantProviderStatus | null>(null);
  const [sidebarQuery, setSidebarQuery] = useState("");
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const loadConversations = useCallback(async () => {
    setLoading(true);
    try {
      const items = await listConversations();
      setConversations(items);
      try {
        setProvider(await readAssistantProvider());
      } catch {
        setProvider(null);
      }
      if (items[0]) setConversation(await readConversation(items[0].id));
      setError(null);
      setErrorKind(null);
    } catch (reason) {
      setErrorKind("load");
      setError(reason instanceof Error ? reason.message : "Assistant unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [conversation?.messages.length, sending]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [draft]);

  async function selectConversation(id: string) {
    setError(null);
    try {
      setConversation(await readConversation(id));
    } catch (reason) {
      setErrorKind("load");
      setError(reason instanceof Error ? reason.message : "Conversation unavailable");
    }
  }

  async function newConversation() {
    setError(null);
    try {
      const created = await createConversation();
      setConversations((items) => [created, ...items]);
      setConversation({ ...created, messages: [] });
      setErrorKind(null);
      textareaRef.current?.focus();
    } catch (reason) {
      setErrorKind("load");
      setError(reason instanceof Error ? reason.message : "Unable to create conversation");
    }
  }

  async function approvePending() {
    if (!pendingAction) return;
    try {
      await approveToolCall(pendingAction.id);
      setPendingAction(null);
    } catch (reason) {
      setErrorKind("load");
      setError(reason instanceof Error ? reason.message : "Approval unavailable");
    }
  }

  async function rejectPending() {
    if (!pendingAction) return;
    try {
      await rejectToolCall(pendingAction.id);
      setPendingAction(null);
    } catch (reason) {
      setErrorKind("load");
      setError(reason instanceof Error ? reason.message : "Rejection unavailable");
    }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || !conversation || sending) return;
    setSending(true);
    setError(null);
    setErrorKind(null);
    setDraft("");
    try {
      const result = await sendMessage(conversation.id, content, { enabled: groundingEnabled, mode: groundingMode, limit: 6 });
      const proposal = result.tool_calls.find((call) => call.requires_confirmation && call.status === "proposed");
      setPendingAction(proposal ? { id: proposal.id, tool: proposal.tool_key, arguments: proposal.arguments } : null);
      setConversation((current) =>
        current
          ? {
              ...current,
              message_count: current.message_count + 2,
              updated_at: result.assistant_message.created_at,
              messages: [...current.messages, result.user_message, result.assistant_message],
            }
          : current,
      );
      setConversations((items) =>
        items.map((item) =>
          item.id === conversation.id
            ? { ...item, message_count: item.message_count + 2, updated_at: result.assistant_message.created_at, title: item.title ?? content.slice(0, 48) }
            : item,
        ),
      );
    } catch (reason) {
      setDraft(content);
      setErrorKind("send");
      setError(reason instanceof Error ? reason.message : "Assistant unavailable");
    } finally {
      setSending(false);
    }
  }

  const providerReady = provider?.state === "configured";
  const providerLabel =
    provider?.state === "configured"
      ? `${provider.label}${provider.model ? ` · ${provider.model}` : ""}`
      : provider?.label ?? "Checking provider…";

  return (
    <section aria-labelledby="assistant-heading" className="nx-chat section-block">
      <div className="nx-chat-top">
        <div>
          <p className="eyebrow">{provider?.provider === "nvidia_nim" ? "NVIDIA NIM" : "Private by default"}</p>
          <h2 id="assistant-heading">Assistant</h2>
        </div>
        <div className="nx-chat-top-meta">
          <span className={`nx-chat-pill${provider?.state === "disabled" ? " muted" : " live"}`}>{providerLabel}</span>
          {onOpenAdmin ? (
            <button className="text-button" onClick={onOpenAdmin} type="button">
              AI settings
            </button>
          ) : null}
        </div>
      </div>

      <div className="nx-chat-shell">
        <ConversationSidebar
          items={conversations}
          onCreate={() => void newConversation()}
          onQuery={setSidebarQuery}
          onSelect={(id) => void selectConversation(id)}
          query={sidebarQuery}
          selected={conversation?.id ?? null}
        />

        <div className="nx-chat-main">
          {loading ? (
            <div className="nx-chat-empty" role="status">
              <span className="nx-chat-spinner" aria-hidden="true" />
              <strong>Loading conversations…</strong>
            </div>
          ) : conversation ? (
            <>
              <div className="nx-chat-main-head">
                <div>
                  <strong>{conversation.title ?? "New conversation"}</strong>
                  <span>{conversation.message_count} messages · local · server-side model</span>
                </div>
                <button className="text-button" onClick={() => void newConversation()} type="button">
                  New chat
                </button>
              </div>

              <div aria-live="polite" className="nx-chat-messages">
                {conversation.messages.length === 0 ? (
                  <div className="nx-chat-empty">
                    <div className="nx-chat-empty-orb" aria-hidden="true">
                      ✦
                    </div>
                    <strong>{provider?.state === "disabled" ? "Connect a model to start" : "How can Nexus help?"}</strong>
                    <span>
                      {provider?.state === "disabled"
                        ? "Open Admin, paste your NVIDIA API key, choose a model, and save. No SSH required."
                        : "Ask about your system, tasks, notes, or anything you’re building. Tools run on this Pi with confirmation when needed."}
                    </span>
                    {provider?.state === "disabled" && onOpenAdmin ? (
                      <button className="primary-button" onClick={onOpenAdmin} type="button">
                        Open Admin
                      </button>
                    ) : (
                      <div className="nx-chat-suggestions">
                        {["Who are you?", "What is 99 × 99?", "Summarize my open tasks"].map((prompt) => (
                          <button
                            className="nx-chat-chip"
                            key={prompt}
                            onClick={() => {
                              setDraft(prompt);
                              textareaRef.current?.focus();
                            }}
                            type="button"
                          >
                            {prompt}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  conversation.messages.map((message) => (
                    <article className={`nx-chat-bubble ${message.role}`} key={message.id}>
                      <div className="nx-chat-bubble-meta">
                        <span className="nx-chat-avatar" aria-hidden="true">
                          {message.role === "user" ? "You" : "N"}
                        </span>
                        <span className="nx-chat-name">{message.role === "user" ? "You" : "Nexus"}</span>
                        <time dateTime={message.created_at}>{formatTime(message.created_at)}</time>
                      </div>
                      <div className="nx-chat-bubble-body">
                        <p>{message.content}</p>
                        {message.role === "assistant" ? (
                          <AssistantSourceCitations
                            onOpenSource={(source) =>
                              source.source_type === "note" ? onOpenNote?.(source.source_id) : onOpenSource?.(source.source_id)
                            }
                            sources={message.sources}
                          />
                        ) : null}
                      </div>
                    </article>
                  ))
                )}
                {sending ? (
                  <article className="nx-chat-bubble assistant typing">
                    <div className="nx-chat-bubble-meta">
                      <span className="nx-chat-avatar" aria-hidden="true">
                        N
                      </span>
                      <span className="nx-chat-name">Nexus</span>
                    </div>
                    <div className="nx-chat-bubble-body">
                      <span className="nx-chat-typing" aria-label="Thinking">
                        <i />
                        <i />
                        <i />
                      </span>
                    </div>
                  </article>
                ) : null}
                <div ref={messageEndRef} />
              </div>

              {pendingAction ? (
                <AssistantActionConfirmation
                  arguments={pendingAction.arguments}
                  onApprove={() => void approvePending()}
                  onReject={() => void rejectPending()}
                  tool={pendingAction.tool}
                />
              ) : null}

              {error ? (
                <div className="inline-state error-state nx-chat-error" role="alert">
                  <strong>Assistant unavailable.</strong>
                  <span>{error === "ai_provider_disabled" ? "Connect NVIDIA NIM in Admin to send messages." : error}</span>
                  {error === "ai_provider_disabled" && onOpenAdmin ? (
                    <button className="text-button" onClick={onOpenAdmin} type="button">
                      Open Admin
                    </button>
                  ) : errorKind === "send" ? (
                    <button
                      className="text-button"
                      onClick={() => {
                        setError(null);
                        setErrorKind(null);
                      }}
                      type="button"
                    >
                      Dismiss
                    </button>
                  ) : (
                    <button className="text-button" onClick={() => void loadConversations()} type="button">
                      Retry
                    </button>
                  )}
                </div>
              ) : null}

              <form className="nx-chat-composer" onSubmit={submit}>
                <div className="nx-chat-composer-tools">
                  <label className="nx-chat-toggle">
                    <input checked={groundingEnabled} onChange={(event) => setGroundingEnabled(event.target.checked)} type="checkbox" />
                    Use my notes
                  </label>
                  {groundingEnabled ? (
                    <label className="nx-chat-mode">
                      Mode
                      <select
                        aria-label="Grounding retrieval mode"
                        onChange={(event) => setGroundingMode(event.target.value as typeof groundingMode)}
                        value={groundingMode}
                      >
                        <option value="hybrid">Hybrid</option>
                        <option value="lexical">Lexical</option>
                        <option value="semantic">Semantic</option>
                      </select>
                    </label>
                  ) : null}
                </div>
                <div className="nx-chat-composer-box">
                  <textarea
                    aria-label="Message assistant"
                    maxLength={4000}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        event.currentTarget.form?.requestSubmit();
                      }
                    }}
                    placeholder="Message Nexus… Enter to send, Shift+Enter for a new line"
                    ref={textareaRef}
                    rows={1}
                    value={draft}
                  />
                  <button className="nx-chat-send" disabled={!draft.trim() || sending || !providerReady} type="submit">
                    {sending ? "…" : "Send"}
                  </button>
                </div>
                <div className="nx-chat-composer-foot">
                  <span>
                    {draft.length}/4000 · Provider stays server-side
                    {!providerReady ? " · model not connected" : ""}
                  </span>
                </div>
              </form>
            </>
          ) : (
            <div className="nx-chat-empty">
              <strong>No conversation selected</strong>
              <button className="primary-button" onClick={() => void newConversation()} type="button">
                Start chatting
              </button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
