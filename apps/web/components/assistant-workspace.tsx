"use client";

import { useCallback, useEffect, useState } from "react";
import { createConversation, listConversations, readConversation, sendMessage, type Conversation, type ConversationSummary } from "../lib/assistant";

function ConversationList({ items, selected, onSelect, onCreate }: { items: ConversationSummary[]; selected: string | null; onSelect: (id: string) => void; onCreate: () => void }) {
  return (
    <aside aria-label="Conversations" className="conversation-list">
      <div className="conversation-list-heading"><div><p className="eyebrow">Assistant</p><strong>Conversations</strong></div><button aria-label="New conversation" className="icon-button" onClick={onCreate} type="button">+</button></div>
      {items.length === 0 ? <p className="conversation-empty">Start a private conversation.</p> : items.map((item) => <button className={`conversation-item${item.id === selected ? " selected" : ""}`} key={item.id} onClick={() => onSelect(item.id)} type="button"><strong>{item.title ?? "New conversation"}</strong><span>{item.message_count} message{item.message_count === 1 ? "" : "s"}</span></button>)}
    </aside>
  );
}

export function AssistantWorkspace() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadConversations = useCallback(async () => {
    setLoading(true);
    try {
      const items = await listConversations();
      setConversations(items);
      if (items[0]) setConversation(await readConversation(items[0].id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Assistant unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadConversations(); }, [loadConversations]);

  async function selectConversation(id: string) {
    setError(null);
    try { setConversation(await readConversation(id)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Conversation unavailable"); }
  }

  async function newConversation() {
    setError(null);
    try {
      const created = await createConversation();
      setConversations((items) => [created, ...items]);
      setConversation({ ...created, messages: [] });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create conversation"); }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || !conversation || sending) return;
    setSending(true);
    setError(null);
    setDraft("");
    try {
      const result = await sendMessage(conversation.id, content);
      setConversation((current) => current ? { ...current, message_count: current.message_count + 2, updated_at: result.assistant_message.created_at, messages: [...current.messages, result.user_message, result.assistant_message] } : current);
      setConversations((items) => items.map((item) => item.id === conversation.id ? { ...item, message_count: item.message_count + 2, updated_at: result.assistant_message.created_at } : item));
    } catch (reason) {
      setDraft(content);
      setError(reason instanceof Error ? reason.message : "Assistant unavailable");
    } finally { setSending(false); }
  }

  return <section aria-labelledby="assistant-heading" className="assistant-workspace section-block">
    <div className="section-heading"><div><p className="eyebrow">Private by default</p><h2 id="assistant-heading">Assistant</h2></div><span className="updated">Bounded gateway</span></div>
    <div className="assistant-layout">
      <ConversationList items={conversations} selected={conversation?.id ?? null} onSelect={(id) => void selectConversation(id)} onCreate={() => void newConversation()} />
      <div className="assistant-panel">
        {loading ? <div className="assistant-state" role="status">Loading conversations…</div> : conversation ? <><div aria-live="polite" className="message-list">{conversation.messages.length === 0 ? <div className="assistant-state"><strong>Start a conversation</strong><span>Ask about your NexusOS system or anything you are building.</span></div> : conversation.messages.map((message) => <article className={`assistant-message ${message.role}`} key={message.id}><span className="message-role">{message.role === "user" ? "You" : "Nexus"}</span><p>{message.content}</p></article>)}</div><form className="assistant-composer" onSubmit={submit}><textarea aria-label="Message assistant" maxLength={4000} onChange={(event) => setDraft(event.target.value)} placeholder="Ask NexusOS…" value={draft} /><div><span>{draft.length}/4000 · Provider stays server-side</span><button className="primary-button" disabled={!draft.trim() || sending} type="submit">{sending ? "Thinking…" : "Send"}</button></div></form></> : <div className="assistant-state"><strong>No conversation selected</strong><button className="text-button" onClick={() => void newConversation()} type="button">Create one</button></div>}
        {error && <div className="inline-state error-state" role="alert"><strong>Assistant unavailable.</strong><span>{error === "ai_provider_disabled" ? "Configure an AI provider on the server to send messages." : error}</span><button className="text-button" onClick={() => void loadConversations()} type="button">Retry</button></div>}
      </div>
    </div>
  </section>;
}
