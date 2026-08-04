import type { SourceReference } from "../lib/assistant";

export function AssistantSourceCitations({ sources, onOpenNote }: { sources: SourceReference[]; onOpenNote: (id: string) => void }) {
  if (sources.length === 0) return null;
  return <details className="assistant-sources">
    <summary>Retrieved from {sources.length} note{sources.length === 1 ? "" : "s"}</summary>
    <ol>
      {sources.map((source) => <li key={source.chunk_id}>
        <button className="assistant-source-link" onClick={() => onOpenNote(source.source_id)} type="button">{source.title}</button>
        <span>Note v{source.source_version} · {source.retrieval_mode}</span>
      </li>)}
    </ol>
  </details>;
}
