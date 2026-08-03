import type { ReactNode } from "react";

export function AssistantActionConfirmation({ tool, arguments: args, onApprove, onReject }: { tool: string; arguments: Record<string, unknown>; onApprove: () => void; onReject: () => void }): ReactNode {
  return <div className="assistant-confirmation" role="dialog" aria-label="Confirm assistant action"><p className="eyebrow">Action requires confirmation</p><strong>{tool.replace("tasks.", "Task ")}</strong><p>{typeof args.title === "string" ? `“${args.title}”` : typeof args.task_id === "string" ? `Task ${args.task_id}` : "The assistant proposed a task change."}</p><div><button className="primary-button" onClick={onApprove} type="button">Confirm</button><button className="text-button" onClick={onReject} type="button">Reject</button></div></div>;
}
