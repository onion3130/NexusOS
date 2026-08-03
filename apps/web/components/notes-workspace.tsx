"use client";

import { useCallback, useEffect, useState } from "react";
import { archiveNote, createNote, deleteNote, listNotes, restoreNote, updateNote, type Note } from "../lib/notes";

export function NotesWorkspace({ onSearch, initialNoteId }: { onSearch: () => void; initialNoteId?: string | null }) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [selected, setSelected] = useState<Note | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [tags, setTags] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { setNotes(await listNotes(showArchived ? "all" : "active")); setError(null); } catch (reason) { setError(reason instanceof Error ? reason.message : "Notes unavailable"); } finally { setLoading(false); }
  }, [showArchived]);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { if (initialNoteId) { const note = notes.find((item) => item.id === initialNoteId); if (note) select(note); } }, [initialNoteId, notes]);

  function select(note: Note) { setSelected(note); setTitle(note.title); setContent(note.content); setTags(note.tags.join(", ")); }
  function newNote() { setSelected(null); setTitle(""); setContent(""); setTags(""); }
  async function save() {
    if (!title.trim() || !content.trim() || saving) return;
    setSaving(true); setError(null);
    try {
      const input = { title: title.trim(), content: content.trim(), tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean) };
      const saved = selected ? await updateNote(selected.id, input) : await createNote(input);
      setSelected(saved); setNotes((items) => selected ? items.map((item) => item.id === saved.id ? saved : item) : [saved, ...items]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save note"); } finally { setSaving(false); }
  }
  async function toggleArchive() {
    if (!selected) return;
    try { const updated = selected.status === "archived" ? await restoreNote(selected.id) : await archiveNote(selected.id); setSelected(updated); setNotes((items) => items.map((item) => item.id === updated.id ? updated : item)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to update note"); }
  }
  async function remove() {
    if (!selected || !window.confirm(`Delete “${selected.title}”?`)) return;
    try { await deleteNote(selected.id); setNotes((items) => items.filter((item) => item.id !== selected.id)); newNote(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to delete note"); }
  }

  return <section aria-labelledby="notes-heading" className="notes-workspace section-block">
    <div className="section-heading"><div><p className="eyebrow">Private knowledge base</p><h2 id="notes-heading">Notes</h2></div><div className="notes-actions"><button className="text-button" onClick={onSearch} type="button">Search notes</button><button className="primary-button" onClick={newNote} type="button">New note</button></div></div>
    <div className="notes-toolbar"><label className="checkbox-label"><input checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} type="checkbox" /> Show archived</label><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div>
    {error && <div className="inline-state error-state" role="alert"><strong>Notes unavailable.</strong><span>{error}</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div>}
    <div className="notes-layout">
      <aside aria-label="Notes list" className="notes-list">{loading ? <p className="conversation-empty">Loading notes…</p> : notes.length === 0 ? <p className="conversation-empty">No notes yet. Start a private note.</p> : notes.map((note) => <button className={`note-list-item${note.id === selected?.id ? " selected" : ""}`} key={note.id} onClick={() => select(note)} type="button"><strong>{note.title}</strong><span>{note.tags.map((tag) => `#${tag}`).join(" ") || "No tags"}</span><small>{new Date(note.updated_at).toLocaleDateString()}{note.status === "archived" ? " · Archived" : ""}</small></button>)}</aside>
      <article aria-label={selected ? "Edit note" : "New note"} className="note-editor"><div className="note-editor-heading"><span className="eyebrow">{selected ? `Version ${selected.content_version}` : "New source"}</span>{selected && <div><button className="text-button" onClick={() => void toggleArchive()} type="button">{selected.status === "archived" ? "Restore" : "Archive"}</button><button className="text-button danger-button" onClick={() => void remove()} type="button">Delete</button></div>}</div><input aria-label="Note title" className="note-title-input" maxLength={160} onChange={(event) => setTitle(event.target.value)} placeholder="Note title" value={title} /><input aria-label="Note tags" className="note-tags-input" maxLength={300} onChange={(event) => setTags(event.target.value)} placeholder="Tags, comma separated" value={tags} /><textarea aria-label="Note content" className="note-content-input" maxLength={100000} onChange={(event) => setContent(event.target.value)} placeholder="Write a note… plain text or Markdown-compatible content" value={content} /><div className="note-editor-footer"><span>{content.length}/100000 · Source content stays private</span><button className="primary-button" disabled={!title.trim() || !content.trim() || saving} onClick={() => void save()} type="button">{saving ? "Saving…" : "Save note"}</button></div></article>
    </div>
  </section>;
}
