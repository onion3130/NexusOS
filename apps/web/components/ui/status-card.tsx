import type { ReactNode } from "react";

type StatusCardProps = {
  eyebrow: string;
  title: string;
  description: string;
  icon: string;
  action?: ReactNode;
};

export function StatusCard({ eyebrow, title, description, icon, action }: StatusCardProps) {
  return (
    <article className="status-card">
      <div className="status-card-icon" aria-hidden="true">{icon}</div>
      <div className="status-card-copy">
        <p className="eyebrow">{eyebrow}</p>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      {action}
    </article>
  );
}

export function LockedState({ title, description }: { title: string; description: string }) {
  return (
    <div className="locked-state" aria-disabled="true">
      <span className="lock-symbol" aria-hidden="true">⌁</span>
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}
