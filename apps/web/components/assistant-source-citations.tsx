import type { SourceReference } from "../lib/assistant";

export function AssistantSourceCitations({ sources, onOpenSource }: { sources: SourceReference[]; onOpenSource: (source: SourceReference) => void }) {
  if (sources.length === 0) return null;
  return <details className="assistant-sources">
    <summary>Retrieved from {sources.length} source{sources.length === 1 ? "" : "s"}</summary>
    <ol>
      {sources.map((source) => <li key={source.chunk_id}>
        <button className="assistant-source-link" onClick={() => onOpenSource(source)} type="button">{source.title}</button>
        <span>{source.source_type === "note" ? "Note" : "External source"} v{source.source_version} · {source.retrieval_mode}</span>
      </li>)}
    </ol>
  </details>;
}
