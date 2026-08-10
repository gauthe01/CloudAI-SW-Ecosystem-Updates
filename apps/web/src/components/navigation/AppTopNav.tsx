import type { ReactNode } from "react";

type AppTopNavProps = {
  eyebrow: string;
  actions?: ReactNode;
  context?: ReactNode;
};

export function AppTopNav({ eyebrow, actions, context }: AppTopNavProps) {
  return (
    <header className="workspace-topbar">
      <div className="workspace-nav-left">
        <span className="workspace-product-label">{eyebrow}</span>
        {context}
      </div>
      {actions ? <div className="workspace-topbar-actions">{actions}</div> : null}
    </header>
  );
}
