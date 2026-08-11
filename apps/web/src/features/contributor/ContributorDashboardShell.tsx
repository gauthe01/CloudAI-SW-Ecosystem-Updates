"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { GlobalLoader } from "@/components/foundation/GlobalLoader";
import {
  ContributorDashboardContext,
  ContributorPartner,
  getContributorDashboardContext,
} from "@/features/contributor/contributor-partners-api";
import { ContributorConnectedSourcesPanel } from "@/features/contributor/ContributorConnectedSourcesPanel";
import { ContributorPartnerMetadataPanel } from "@/features/contributor/ContributorPartnerMetadataPanel";
import { ContributorUpdatesPanel } from "@/features/contributor/ContributorUpdatesPanel";
import { ManualUpdateForm } from "@/features/contributor/ManualUpdateForm";

type ContributorDashboardShellProps = {
  partner: ContributorPartner;
  canSwitchPartner: boolean;
  onSwitchPartner: () => void;
};

type ContributorDashboardTab =
  | "partner_metadata"
  | "pending_updates"
  | "approved_updates"
  | "connected_sources";

const tabs: { id: ContributorDashboardTab; label: string }[] = [
  { id: "partner_metadata", label: "Partner Metadata" },
  { id: "pending_updates", label: "Pending Updates" },
  { id: "approved_updates", label: "Approved Updates" },
  { id: "connected_sources", label: "Connected sources" },
];

const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

type CycleParts = {
  year: number;
  month: number;
};

export function ContributorDashboardShell({
  partner,
  canSwitchPartner,
  onSwitchPartner,
}: ContributorDashboardShellProps) {
  const [context, setContext] = useState<ContributorDashboardContext | null>(null);
  const [activeTab, setActiveTab] = useState<ContributorDashboardTab>("partner_metadata");
  const [search, setSearch] = useState("");
  const [cycle, setCycle] = useState("");
  const [addUpdateOpen, setAddUpdateOpen] = useState(false);
  const [updatesReloadKey, setUpdatesReloadKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    getContributorDashboardContext(partner.partner_id)
      .then((nextContext) => {
        if (mounted) {
          setContext(nextContext);
          setActiveTab(readTabFromUrl() ?? "partner_metadata");
          setCycle(nextContext.active_cycle);
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load dashboard.");
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [partner.partner_id]);

  const activePartner = context?.partner ?? partner;
  const activeCycleLabel = formatCycleLabel(cycle) ?? context?.active_cycle_label ?? cycle;
  const tabCounts = context?.tab_counts;

  function refreshDashboardContext() {
    getContributorDashboardContext(partner.partner_id)
      .then((nextContext) => setContext(nextContext))
      .catch(() => undefined);
  }

  function handleManualUpdateCreated() {
    setActiveTab("pending_updates");
    selectTab("pending_updates", setActiveTab);
    setUpdatesReloadKey((current) => current + 1);
    refreshDashboardContext();
  }

  if (!loading && !error && addUpdateOpen && cycle) {
    return (
      <div className="contributor-dashboard-shell add-update-mode">
        <ManualUpdateForm
          partnerId={activePartner.partner_id}
          partnerName={activePartner.name}
          cycle={cycle}
          cycleLabel={activeCycleLabel}
          onCancel={() => setAddUpdateOpen(false)}
          onCreated={handleManualUpdateCreated}
        />
      </div>
    );
  }

  return (
    <div className="contributor-dashboard-shell">
      <div className="contributor-page-head">
        <div className="contributor-page-identity">
          <div className="contributor-page-copy">
            <h3>{activePartner.name}</h3>
          </div>

          <input
            className="contributor-update-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search updates..."
            aria-label="Search contributor dashboard"
          />
        </div>

        <div className="contributor-page-actions">
          {canSwitchPartner ? (
            <button className="ghost-action" type="button" onClick={onSwitchPartner}>
              Switch partner
            </button>
          ) : null}

          <CyclePicker cycle={cycle} disabled={!cycle} onChange={setCycle} />

          <button
            className="contributor-add-update-action"
            type="button"
            onClick={() => setAddUpdateOpen(true)}
            disabled={!cycle}
          >
            + Add update
          </button>
        </div>
      </div>

      {error ? <p className="workspace-error inline-error">{error}</p> : null}
      {loading ? (
        <GlobalLoader
          label="Loading contributor dashboard"
          detail="Collecting partner updates, metadata, and source status."
        />
      ) : null}

      {!loading && !error ? (
        <>
          <nav className="contributor-dashboard-tabs" aria-label="Contributor dashboard tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={activeTab === tab.id ? "active" : ""}
                onClick={() => selectTab(tab.id, setActiveTab)}
              >
                <span>{tab.label}</span>
                {shouldShowTabCount(tab.id) && getTabCount(tab.id, tabCounts) !== null ? (
                  <strong>{getTabCount(tab.id, tabCounts)}</strong>
                ) : null}
              </button>
            ))}
          </nav>

          <DashboardTabPanel
            activeTab={activeTab}
            partnerId={activePartner.partner_id}
            activeCycle={cycle}
            activeCycleLabel={activeCycleLabel}
            search={search}
            reloadKey={updatesReloadKey}
            onLifecycleChange={refreshDashboardContext}
          />
        </>
      ) : null}
    </div>
  );
}

function CyclePicker({
  cycle,
  disabled,
  onChange,
}: {
  cycle: string;
  disabled: boolean;
  onChange: (cycle: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<"months" | "years">("months");
  const parsedCycle = parseCycle(cycle);
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  const [selectedYear, setSelectedYear] = useState(parsedCycle?.year ?? currentYear);
  const pickerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (parsedCycle) {
      setSelectedYear(parsedCycle.year);
    }
  }, [parsedCycle?.year]);

  useEffect(() => {
    function handleDocumentClick(event: MouseEvent) {
      if (!pickerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleDocumentClick);
    return () => document.removeEventListener("mousedown", handleDocumentClick);
  }, []);

  const previousCycle = parsedCycle ? addMonths(parsedCycle, -1) : null;
  const nextCycle =
    parsedCycle && !isFutureCycle(addMonths(parsedCycle, 1), currentYear, currentMonth)
      ? addMonths(parsedCycle, 1)
      : null;
  const yearOptions = useMemo(
    () => Array.from({ length: 7 }, (_, index) => currentYear + 1 - index),
    [currentYear],
  );

  function handleToggle() {
    if (disabled) {
      return;
    }
    setOpen((current) => !current);
    setView("months");
  }

  function handleMonthSelect(month: number) {
    const next = { year: selectedYear, month };
    if (isFutureCycle(next, currentYear, currentMonth)) {
      return;
    }
    onChange(formatCycleValue(next));
    setOpen(false);
    setView("months");
  }

  function handleYearSelect(year: number) {
    if (year > currentYear) {
      return;
    }
    setSelectedYear(year);
    setView("months");
  }

  return (
    <div className={`cycle-picker${open ? " open" : ""}`} ref={pickerRef}>
      <div className="cycle-picker-control">
        {previousCycle ? (
          <button
            className="cycle-picker-nav"
            type="button"
            aria-label="Previous month"
            onClick={() => onChange(formatCycleValue(previousCycle))}
            disabled={disabled}
          >
            ‹
          </button>
        ) : (
          <span className="cycle-picker-nav disabled" aria-disabled="true">
            ‹
          </span>
        )}

        <button
          className="cycle-picker-label"
          type="button"
          onClick={handleToggle}
          disabled={disabled}
          aria-expanded={open}
          aria-label="Open cycle picker"
        >
          {formatCycleLabel(cycle) ?? "Select month"}
        </button>

        {nextCycle ? (
          <button
            className="cycle-picker-nav"
            type="button"
            aria-label="Next month"
            onClick={() => onChange(formatCycleValue(nextCycle))}
            disabled={disabled}
          >
            ›
          </button>
        ) : (
          <span className="cycle-picker-nav disabled" aria-disabled="true">
            ›
          </span>
        )}
      </div>

      <div className="cycle-picker-menu" role="dialog" aria-label="Cycle picker">
        <button className="cycle-picker-year" type="button" onClick={() => setView("years")}>
          {selectedYear}
        </button>

        <div className={`cycle-picker-view${view === "months" ? " active" : ""}`}>
          <div className="cycle-month-grid">
            {monthLabels.map((label, index) => {
              const month = index + 1;
              const monthCycle = { year: selectedYear, month };
              const isDisabled = isFutureCycle(monthCycle, currentYear, currentMonth);
              const isActive =
                parsedCycle?.year === selectedYear && parsedCycle?.month === month;
              return (
                <button
                  key={label}
                  className={`cycle-month${isActive ? " active" : ""}${
                    isDisabled ? " disabled" : ""
                  }`}
                  type="button"
                  disabled={isDisabled}
                  onClick={() => handleMonthSelect(month)}
                >
                  {label}
                </button>
              );
            })}
          </div>
          <div className="cycle-picker-note">Future months are not selectable</div>
        </div>

        <div className={`cycle-picker-view${view === "years" ? " active" : ""}`}>
          <div className="cycle-year-grid">
            {yearOptions.map((year) => {
              const isDisabled = year > currentYear;
              return (
                <button
                  key={year}
                  className={`cycle-year-option${year === selectedYear ? " active" : ""}${
                    isDisabled ? " disabled" : ""
                  }`}
                  type="button"
                  disabled={isDisabled}
                  onClick={() => handleYearSelect(year)}
                >
                  {year}
                </button>
              );
            })}
          </div>
          <div className="cycle-picker-note">Years after {currentYear} are visible but not selectable</div>
        </div>
      </div>
    </div>
  );
}

function shouldShowTabCount(tabId: ContributorDashboardTab): boolean {
  return tabId === "pending_updates" || tabId === "approved_updates";
}

function selectTab(
  tabId: ContributorDashboardTab,
  setActiveTab: (tabId: ContributorDashboardTab) => void,
) {
  setActiveTab(tabId);
  const url = new URL(window.location.href);
  url.searchParams.set("contributor_tab", tabId);
  window.history.replaceState(null, "", url);
}

function readTabFromUrl(): ContributorDashboardTab | null {
  const tab = new URL(window.location.href).searchParams.get("contributor_tab");
  return isContributorDashboardTab(tab) ? tab : null;
}

function isContributorDashboardTab(value: string | null): value is ContributorDashboardTab {
  return tabs.some((tab) => tab.id === value);
}

function DashboardTabPanel({
  activeTab,
  partnerId,
  activeCycle,
  activeCycleLabel,
  search,
  reloadKey,
  onLifecycleChange,
}: {
  activeTab: ContributorDashboardTab;
  partnerId: string;
  activeCycle: string;
  activeCycleLabel: string;
  search: string;
  reloadKey: number;
  onLifecycleChange: () => void;
}) {
  if (activeTab === "partner_metadata") {
    return (
      <ContributorPartnerMetadataPanel
        partnerId={partnerId}
        cycle={activeCycle}
        cycleLabel={activeCycleLabel}
      />
    );
  }

  if (activeTab === "pending_updates" || activeTab === "approved_updates") {
    return (
      <ContributorUpdatesPanel
        partnerId={partnerId}
        cycle={activeCycle}
        cycleLabel={activeCycleLabel}
        status={activeTab === "pending_updates" ? "pending" : "approved"}
        search={search}
        reloadKey={reloadKey}
        onLifecycleChange={onLifecycleChange}
      />
    );
  }

  return (
    <ContributorConnectedSourcesPanel
      partnerId={partnerId}
      onSourcesChange={onLifecycleChange}
    />
  );
}

function getTabCount(
  tabId: ContributorDashboardTab,
  tabCounts: ContributorDashboardContext["tab_counts"] | undefined,
): number | null {
  if (!tabCounts) {
    return null;
  }
  if (tabId === "pending_updates") {
    return tabCounts.pending_updates;
  }
  if (tabId === "approved_updates") {
    return tabCounts.approved_updates;
  }
  if (tabId === "connected_sources") {
    return tabCounts.connected_sources;
  }
  return null;
}

function parseCycle(cycle: string): CycleParts | null {
  const match = /^(\d{4})-(\d{2})$/.exec(cycle);
  if (!match) {
    return null;
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
    return null;
  }

  return { year, month };
}

function formatCycleValue(cycle: CycleParts): string {
  return `${cycle.year}-${String(cycle.month).padStart(2, "0")}`;
}

function formatCycleLabel(cycle: string): string | null {
  const parsed = parseCycle(cycle);
  if (!parsed) {
    return null;
  }

  return `${new Intl.DateTimeFormat("en", { month: "long" }).format(
    new Date(parsed.year, parsed.month - 1, 1),
  )} ${parsed.year}`;
}

function addMonths(cycle: CycleParts, delta: number): CycleParts {
  const monthIndex = cycle.year * 12 + (cycle.month - 1) + delta;
  return {
    year: Math.floor(monthIndex / 12),
    month: (monthIndex % 12) + 1,
  };
}

function isFutureCycle(cycle: CycleParts, currentYear: number, currentMonth: number): boolean {
  return cycle.year > currentYear || (cycle.year === currentYear && cycle.month > currentMonth);
}
