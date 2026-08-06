"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  approveToolCall,
  createConversation,
  listConversations,
  readAssistantProvider,
  readConversation,
  rejectToolCall,
  sendMessage,
  sendMessageStream,
  type AssistantProviderStatus,
  type Conversation,
  type ConversationSummary,
  type Message,
} from "../lib/assistant";
import { AssistantActionConfirmation } from "./assistant-action-confirmation";
import { AssistantSourceCitations } from "./assistant-source-citations";

const SUGGESTIONS: Array<{ title: string; prompt: string; hint: string }> = [
  { title: "System status", prompt: "What's my Pi CPU, memory, and temperature right now?", hint: "Live telemetry" },
  { title: "My tasks", prompt: "List my open tasks and what I should do next.", hint: "Tasks on NexusOS" },
  { title: "Search notes", prompt: "Search my notes for anything about networking or setup.", hint: "Grounded retrieval" },
  { title: "Who are you?", prompt: "Who are you and what can you access on NexusOS?", hint: "Identity + scope" },
];

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

/** Lightweight markdown-ish rendering for chat messages (no HTML). */
function MessageBody({ content }: { content: string }) {
  const blocks = content.replace(/\r\n/g, "\n").split(/\n{2,}/);
  return (
    <div className="gpt-md">
      {blocks.map((block, index) => {
        const trimmed = block.trim();
        if (!trimmed) return null;
        if (trimmed.startsWith("```")) {
          const lines = trimmed.split("\n");
          const body = lines.slice(1, lines[lines.length - 1]?.startsWith("```") ? -1 : undefined).join("\n");
          return (
            <pre className="gpt-code" key={index}>
              <code>{body}</code>
            </pre>
          );
        }
        if (/^[-*•]\s/m.test(trimmed) || /^\d+\.\s/m.test(trimmed)) {
          const items = trimmed.split("\n").filter(Boolean);
          return (
            <ul className="gpt-list" key={index}>
              {items.map((item, i) => (
                <li key={i}>{inlineFormat(item.replace(/^([-*•]|\d+\.)\s+/, ""))}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={index}>
            {trimmed.split("\n").map((line, i, arr) => (
              <span key={i}>
                {inlineFormat(line)}
                {i < arr.length - 1 ? <br /> : null}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}

function inlineFormat(text: string): ReactNode[] {
  const parts: React.ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("`")) {
      parts.push(
        <code className="gpt-inline-code" key={key++}>
          {token.slice(1, -1)}
        </code>,
      );
    } else {
      parts.push(
        <strong key={key++}>{token.slice(2, -2)}</strong>,
      );
    }
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function ConversationSidebar({
  items,
  selected,
  onSelect,
  onCreate,
  query,
  onQuery,
  open,
  onClose,
  providerLabel,
  onOpenAdmin,
  onOpenHome,
}: {
  items: ConversationSummary[];
  selected: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  query: string;
  onQuery: (value: string) => void;
  open: boolean;
  onClose: () => void;
  providerLabel: string;
  onOpenAdmin?: () => void;
  onOpenHome?: () => void;
}) {
  const filtered = items.filter((item) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (item.title ?? "new chat").toLowerCase().includes(q);
  });

  return (
    <>
      {open ? <button aria-label="Close sidebar" className="gpt-sidebar-scrim" onClick={onClose} type="button" /> : null}
      <aside aria-label="Conversations" className={`gpt-sidebar${open ? " open" : ""}`}>
        <div className="gpt-sidebar-top">
          <button className="gpt-new-chat" onClick={onCreate} type="button">
            <span aria-hidden="true">＋</span> New chat
          </button>
        </div>
        <label className="gpt-sidebar-search">
          <span aria-hidden="true">⌕</span>
          <input onChange={(e) => onQuery(e.target.value)} placeholder="Search chats" type="search" value={query} />
        </label>
        <div className="gpt-sidebar-list">
          <p className="gpt-sidebar-label">Chats</p>
          {filtered.length === 0 ? (
            <p className="gpt-sidebar-empty">{items.length === 0 ? "No chats yet" : "No matches"}</p>
          ) : (
            filtered.map((item) => (
              <button
                className={`gpt-thread${item.id === selected ? " selected" : ""}`}
                key={item.id}
                onClick={() => {
                  onSelect(item.id);
                  onClose();
                }}
                type="button"
              >
                <span className="gpt-thread-icon" aria-hidden="true">
                  💬
                </span>
                <span className="gpt-thread-title">{item.title ?? "New chat"}</span>
              </button>
            ))
          )}
        </div>
        <div className="gpt-sidebar-foot">
          <div className="gpt-sidebar-model" title={providerLabel}>
            <span className="gpt-model-dot" aria-hidden="true" />
            <div>
              <strong>Nexus</strong>
              <span>{providerLabel}</span>
            </div>
          </div>
          {onOpenHome ? (
            <button className="gpt-sidebar-link" onClick={onOpenHome} type="button">
              ← NexusOS home
            </button>
          ) : null}
          {onOpenAdmin ? (
            <button className="gpt-sidebar-link" onClick={onOpenAdmin} type="button">
              AI settings
            </button>
          ) : null}
        </div>
      </aside>
    </>
  );
}

function ChatRow({
  message,
  onOpenNote,
  onOpenSource,
}: {
  message: Message;
  onOpenNote?: (id: string) => void;
  onOpenSource?: (id: string) => void;
}) {
  const isUser = message.role === "user";
  return (
    <article className={`gpt-row ${message.role}`}>
      <div className="gpt-row-inner">
        <div className={`gpt-avatar ${isUser ? "user" : "assistant"}`} aria-hidden="true">
          {isUser ? "Y" : "N"}
        </div>
        <div className="gpt-row-body">
          <div className="gpt-row-meta">
            <strong>{isUser ? "You" : "Nexus"}</strong>
            <time dateTime={message.created_at}>{formatTime(message.created_at)}</time>
          </div>
          {isUser ? <p className="gpt-user-text">{message.content}</p> : <MessageBody content={message.content} />}
          {!isUser ? (
            <AssistantSourceCitations
              onOpenSource={(source) =>
                source.source_type === "note" ? onOpenNote?.(source.source_id) : onOpenSource?.(source.source_id)
              }
              sources={message.sources}
            />
          ) : null}
        </div>
      </div>
    </article>
  );
}

export function AssistantWorkspace({
  onOpenNote,
  onOpenSource,
  onOpenAdmin,
  onOpenHome,
}: {
  onOpenNote?: (id: string) => void;
  onOpenSource?: (id: string) => void;
  onOpenAdmin?: () => void;
  onOpenHome?: () => void;
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
  const [sidebarOpen, setSidebarOpen] = useState(false);
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
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
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
      setSidebarOpen(false);
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
      setPendingAction(null);
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

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const content = draft.trim();
    if (!content || !conversation || sending) return;
    setSending(true);
    setError(null);
    setErrorKind(null);
    setDraft("");
    try {
      const needsTools = /\b(cpu|memory|ram|temp(?:erature)?|thermal|disk|storage|uptime|load|task|tasks|todo|todos|reminder|reminders|note|notes|search my|look up my|find my|in my notes|backup|backups|restore|file|files|folder|folders|project|projects|git|docker|container|containers|plugin|plugins|system|overview|telemetry|status of|on (?:my )?(?:pi|nexus|nexusos)|calendar|event|events|finance|budget|spending|transaction|media|photo|photos|notification|notifications|what'?s my|how much|how hot|list my|show my|check my|my open)\b/i.test(content);
      let result: import("../lib/assistant").AssistantResult;
      if (needsTools) {
        result = await sendMessage(conversation.id, content, { enabled: groundingEnabled, mode: groundingMode, limit: 6 });
        setConversation((current) => current ? { ...current, messages: [...current.messages, result.user_message, result.assistant_message] } : current);
      } else {
        let streamedAssistant = "";
        result = await sendMessageStream(
          conversation.id,
          content,
          { enabled: groundingEnabled, mode: groundingMode, limit: 6 },
          (userMessage) => {
            setConversation((current) => current ? { ...current, messages: [...current.messages, userMessage] } : current);
          },
          (delta) => {
            streamedAssistant += delta;
            setConversation((current) => {
              if (!current) return current;
              const messages = [...current.messages];
              const last = messages[messages.length - 1];
              if (last?.role === "assistant" && last.id === "streaming") {
                messages[messages.length - 1] = { ...last, content: streamedAssistant };
              } else {
                messages.push({ id: "streaming", role: "assistant", content: streamedAssistant, sequence: messages.length, created_at: new Date().toISOString(), sources: [] });
              }
              return { ...current, messages };
            });
          },
        );
      }
      const proposal = result.tool_calls.find((call) => call.requires_confirmation && call.status === "proposed");
      setPendingAction(proposal ? { id: proposal.id, tool: proposal.tool_key, arguments: proposal.arguments } : null);
      setConversation((current) =>
        current
          ? {
              ...current,
              message_count: current.message_count + 2,
              updated_at: result.assistant_message.created_at,
              messages: needsTools ? current.messages : [...current.messages.filter((message) => message.id !== "streaming"), result.assistant_message],
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
      if (content.trim().toLowerCase().startsWith("/model")) {
        try {
          setProvider(await readAssistantProvider());
        } catch {
          /* keep prior provider badge */
        }
      }
    } catch (reason) {
      setDraft(content);
      try {
        const reconciled = await readConversation(conversation.id);
        setConversation(reconciled);
      } catch {
        setConversation((current) => current ? { ...current, messages: current.messages.filter((message) => message.id !== "streaming") } : current);
      }
      setErrorKind("send");
      setError(reason instanceof Error ? reason.message : "Assistant unavailable");
    } finally {
      setSending(false);
    }
  }

  function useSuggestion(prompt: string) {
    setDraft(prompt);
    textareaRef.current?.focus();
  }

  const providerReady = provider?.state === "configured";
  const providerLabel =
    provider?.state === "configured"
      ? `${provider.label}${provider.model ? ` · ${provider.model}` : ""}`
      : provider?.label ?? "Checking provider…";
  const empty = !loading && conversation && conversation.messages.length === 0;

  return (
    <section aria-label="Nexus Assistant" className="gpt-chat">
      <ConversationSidebar
        items={conversations}
        onClose={() => setSidebarOpen(false)}
        onCreate={() => void newConversation()}
        onOpenAdmin={onOpenAdmin}
        onOpenHome={onOpenHome}
        onQuery={setSidebarQuery}
        onSelect={(id) => void selectConversation(id)}
        open={sidebarOpen}
        providerLabel={providerLabel}
        query={sidebarQuery}
        selected={conversation?.id ?? null}
      />

      <div className="gpt-main">
        <header className="gpt-topbar">
          <button
            aria-label="Open chats"
            className="gpt-icon-btn gpt-menu-btn"
            onClick={() => setSidebarOpen(true)}
            type="button"
          >
            ☰
          </button>
          <div className="gpt-model-chip" title={providerLabel}>
            <span className={`gpt-status-dot${providerReady ? " on" : ""}`} />
            <div>
              <strong>Nexus</strong>
              <span>{provider?.model ?? providerLabel}</span>
            </div>
          </div>
          <div className="gpt-topbar-actions">
            <button className="gpt-icon-btn" onClick={() => void newConversation()} title="New chat" type="button">
              ＋
            </button>
            {onOpenAdmin ? (
              <button className="gpt-text-btn" onClick={onOpenAdmin} type="button">
                Settings
              </button>
            ) : null}
          </div>
        </header>

        <div aria-live="polite" className="gpt-scroll">
          {loading ? (
            <div className="gpt-empty" role="status">
              <span className="gpt-spinner" aria-hidden="true" />
              <p>Loading chats…</p>
            </div>
          ) : !conversation ? (
            <div className="gpt-empty">
              <div className="gpt-logo" aria-hidden="true">
                ✦
              </div>
              <h2>Nexus</h2>
              <p>Start a chat to talk to your local assistant.</p>
              <button className="gpt-primary" onClick={() => void newConversation()} type="button">
                New chat
              </button>
            </div>
          ) : empty ? (
            <div className="gpt-empty gpt-welcome">
              <div className="gpt-logo" aria-hidden="true">
                ✦
              </div>
              <h2>{provider?.state === "disabled" ? "Connect a model to start" : "What can I help with?"}</h2>
              <p className="gpt-welcome-copy">
                {provider?.state === "disabled"
                  ? "Open Admin, add your NVIDIA API key, pick a model, and save. Keys stay on this Pi."
                  : "ChatGPT-style chat on your Pi — with access to NexusOS notes, tasks, system telemetry, files, and more when you ask."}
              </p>
              {provider?.state === "disabled" && onOpenAdmin ? (
                <button className="gpt-primary" onClick={onOpenAdmin} type="button">
                  Open Admin
                </button>
              ) : (
                <div className="gpt-suggestion-grid">
                  {SUGGESTIONS.map((item) => (
                    <button className="gpt-suggestion" key={item.title} onClick={() => useSuggestion(item.prompt)} type="button">
                      <strong>{item.title}</strong>
                      <span>{item.hint}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="gpt-thread-view">
              {conversation.messages.map((message) => (
                <ChatRow key={message.id} message={message} onOpenNote={onOpenNote} onOpenSource={onOpenSource} />
              ))}
              {sending && !conversation.messages.some((message) => message.id === "streaming") ? (
                <article className="gpt-row assistant">
                  <div className="gpt-row-inner">
                    <div className="gpt-avatar assistant" aria-hidden="true">
                      N
                    </div>
                    <div className="gpt-row-body">
                      <div className="gpt-row-meta">
                        <strong>Nexus</strong>
                      </div>
                      <span className="gpt-typing" aria-label="Thinking">
                        <i />
                        <i />
                        <i />
                      </span>
                    </div>
                  </div>
                </article>
              ) : null}
              <div ref={messageEndRef} />
            </div>
          )}
        </div>

        {pendingAction ? (
          <div className="gpt-confirm-wrap">
            <AssistantActionConfirmation
              arguments={pendingAction.arguments}
              onApprove={() => void approvePending()}
              onReject={() => void rejectPending()}
              tool={pendingAction.tool}
            />
          </div>
        ) : null}

        {error ? (
          <div className="gpt-error" role="alert">
            <div>
              <strong>Something went wrong</strong>
              <span>{error}</span>
            </div>
            {errorKind === "send" ? (
              <button className="gpt-text-btn" onClick={() => { setError(null); setErrorKind(null); }} type="button">
                Dismiss
              </button>
            ) : (
              <button className="gpt-text-btn" onClick={() => void loadConversations()} type="button">
                Retry
              </button>
            )}
          </div>
        ) : null}

        <div className="gpt-composer-wrap">
          <form className="gpt-composer" onSubmit={(e) => void submit(e)}>
            <div className="gpt-composer-tools">
              <label className={`gpt-pill-toggle${groundingEnabled ? " on" : ""}`}>
                <input checked={groundingEnabled} onChange={(e) => setGroundingEnabled(e.target.checked)} type="checkbox" />
                NexusOS context
              </label>
              {groundingEnabled ? (
                <label className="gpt-mode">
                  <span className="sr-only">Retrieval mode</span>
                  <select
                    aria-label="Grounding retrieval mode"
                    onChange={(e) => setGroundingMode(e.target.value as typeof groundingMode)}
                    value={groundingMode}
                  >
                    <option value="hybrid">Hybrid</option>
                    <option value="lexical">Lexical</option>
                    <option value="semantic">Semantic</option>
                  </select>
                </label>
              ) : null}
              <span className="gpt-composer-hint">Notes · tasks · system · files</span>
            </div>
            <div className="gpt-composer-box">
              <textarea
                aria-label="Message Nexus"
                maxLength={4000}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void submit();
                  }
                }}
                placeholder={providerReady ? "Message Nexus… Ask anything, or about your Pi" : "Connect a model in Admin to chat"}
                ref={textareaRef}
                rows={1}
                value={draft}
              />
              <button
                aria-label="Send message"
                className="gpt-send"
                disabled={!draft.trim() || sending || !providerReady || !conversation}
                type="submit"
              >
                {sending ? "…" : "↑"}
              </button>
            </div>
            <p className="gpt-disclaimer">
              Nexus can use your NexusOS data when context is on. Sensitive actions need your confirmation.{" "}
              <kbd>/model</kbd> switches models.
            </p>
          </form>
        </div>
      </div>
    </section>
  );
}
