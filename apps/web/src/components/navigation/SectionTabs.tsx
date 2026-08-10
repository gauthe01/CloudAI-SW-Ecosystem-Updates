"use client";

export type SectionTab = {
  id: string;
  label: string;
};

type SectionTabsProps = {
  activeTabId: string;
  ariaLabel: string;
  onChange: (tabId: string) => void;
  tabs: SectionTab[];
};

export function SectionTabs({ activeTabId, ariaLabel, onChange, tabs }: SectionTabsProps) {
  return (
    <section className="workspace-tabs" aria-label={ariaLabel} role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={tab.id === activeTabId ? "workspace-tab active" : "workspace-tab"}
          type="button"
          role="tab"
          aria-selected={tab.id === activeTabId}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </section>
  );
}
