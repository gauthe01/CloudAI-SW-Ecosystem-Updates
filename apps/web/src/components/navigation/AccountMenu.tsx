"use client";

import { useEffect, useRef, useState } from "react";

export type AccountMenuView<TViewId extends string> = {
  id: TViewId;
  label: string;
};

type AccountMenuProps<TViewId extends string> = {
  activeViewId: TViewId;
  email: string;
  name: string;
  onSignOut: () => void;
  onSwitchView: (viewId: TViewId) => void;
  switchingViewId?: TViewId | null;
  views: AccountMenuView<TViewId>[];
};

export function AccountMenu<TViewId extends string>({
  activeViewId,
  email,
  name,
  onSignOut,
  onSwitchView,
  switchingViewId,
  views,
}: AccountMenuProps<TViewId>) {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const activeViewLabel = views.find((view) => view.id === activeViewId)?.label;

  useEffect(() => {
    function closeOnOutsideClick(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, []);

  function switchView(viewId: TViewId) {
    onSwitchView(viewId);
    if (viewId !== activeViewId) {
      setMenuOpen(false);
    }
  }

  return (
    <div className="account-menu" ref={menuRef}>
      <button
        className="account-trigger"
        type="button"
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        onClick={() => setMenuOpen((current) => !current)}
      >
        <span className="account-trigger-copy">
          <strong>{name}</strong>
          <small>{activeViewLabel ? `${activeViewLabel} - ${email}` : email}</small>
        </span>
        <span className="account-trigger-caret" aria-hidden="true" />
      </button>

      {menuOpen ? (
        <div className="account-dropdown" role="menu" aria-label="Account menu">
          <div className="account-dropdown-header">
            <strong>{name}</strong>
            <span>{email}</span>
          </div>

          <div className="view-options">
            {views.map((view) => {
              const isActive = view.id === activeViewId;
              return (
                <button
                  key={view.id}
                  type="button"
                  role="menuitem"
                  className="view-option"
                  disabled={isActive || switchingViewId === view.id}
                  aria-current={isActive ? "page" : undefined}
                  onClick={() => switchView(view.id)}
                >
                  <span>{view.label}</span>
                  {isActive ? <strong>Active</strong> : null}
                </button>
              );
            })}
          </div>

          <button className="signout-action" type="button" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
