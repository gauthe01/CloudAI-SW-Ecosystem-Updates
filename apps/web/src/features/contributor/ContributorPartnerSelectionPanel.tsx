"use client";

import { useMemo, useState } from "react";
import type { CSSProperties } from "react";

import { GlobalLoader } from "@/components/foundation/GlobalLoader";
import { ContributorDashboardShell } from "@/features/contributor/ContributorDashboardShell";
import { ContributorPartner } from "@/features/contributor/contributor-partners-api";

type ContributorPartnerSelectionPanelProps = {
  error: string | null;
  loading: boolean;
  onSelectPartner: (partnerId: string | null) => void;
  partners: ContributorPartner[];
  selectedPartnerId: string | null;
  userName: string;
};

export function ContributorPartnerSelectionPanel({
  error,
  loading,
  onSelectPartner,
  partners,
  selectedPartnerId,
  userName,
}: ContributorPartnerSelectionPanelProps) {
  const [search, setSearch] = useState("");

  const filteredPartners = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return partners;
    }
    return partners.filter(
      (partner) =>
        partner.name.toLowerCase().includes(query) ||
        (partner.description ?? "").toLowerCase().includes(query),
    );
  }, [partners, search]);

  const selectedPartner = partners.find((partner) => partner.partner_id === selectedPartnerId);
  const shouldShowSelector = partners.length > 1 && !selectedPartner;

  return (
    <div className="assigned-partners-panel">
      {shouldShowSelector ? (
        <div className="contributor-partner-selection-header">
          <h2>
            {getPacificGreeting()}, {userName}
          </h2>
        </div>
      ) : null}

      {shouldShowSelector ? null : (
        <div className="visually-hidden">
          <h2>Partner Workspace</h2>
        </div>
      )}

      {error ? <p className="workspace-error inline-error">{error}</p> : null}
      {loading ? (
        <GlobalLoader
          label="Loading assigned partners"
          detail="Checking which partner workspaces are available to you."
        />
      ) : null}

      {!loading && partners.length === 0 ? (
        <div>
          <p className="muted-copy">No partners assigned yet</p>
        </div>
      ) : null}

      {!loading && partners.length > 1 && !selectedPartner ? (
        <>
          <div className="partner-selection-toolbar">
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search assigned partners"
              aria-label="Search assigned partners"
            />
          </div>

          <div className="partner-selection-grid">
            {filteredPartners.map((partner) => (
              <PartnerCard
                key={partner.partner_id}
                partner={partner}
                onSelect={() => onSelectPartner(partner.partner_id)}
              />
            ))}
          </div>
        </>
      ) : null}

      {!loading && selectedPartner ? (
        <ContributorDashboardShell
          partner={selectedPartner}
          canSwitchPartner={false}
          onSwitchPartner={() => onSelectPartner(null)}
        />
      ) : null}
    </div>
  );
}

function PartnerCard({
  partner,
  onSelect,
}: {
  partner: ContributorPartner;
  onSelect: () => void;
}) {
  const color = partnerColor(partner.name);

  return (
    <button
      className="partner-selection-card"
      style={{ "--partner-color": color } as CSSProperties}
      type="button"
      onClick={onSelect}
    >
      <span className="partner-selection-card-top">
        <span>
          <strong>{partner.name}</strong>
        </span>
      </span>
      <PartnerMetrics partner={partner} />
      <span className="partner-selection-last-active">
        <span>Last active</span>
        <strong>{formatLastActivity(partner.last_activity_at)}</strong>
      </span>
    </button>
  );
}

function PartnerMetrics({ partner }: { partner: ContributorPartner }) {
  return (
    <dl className="partner-metrics">
      <div>
        <dt>Updates</dt>
        <dd>{partner.updates_count}</dd>
      </div>
      <div>
        <dt>Integrations</dt>
        <dd>{partner.connected_sources_count}</dd>
      </div>
    </dl>
  );
}

function partnerColor(name: string): string {
  const colors = ["#0b5d7a", "#5b3aa4", "#2f7a4d", "#1f5f9f", "#92400e", "#9b1c1c"];
  const index = Array.from(name).reduce((sum, char) => sum + char.charCodeAt(0), 0) % colors.length;
  return colors[index];
}

function getPacificGreeting(): string {
  const hourPart = new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    hourCycle: "h23",
    timeZone: "America/Los_Angeles",
  })
    .formatToParts(new Date())
    .find((part) => part.type === "hour");
  const hour = Number(hourPart?.value ?? "0");

  if (hour < 12) {
    return "Good morning";
  }
  if (hour < 17) {
    return "Good afternoon";
  }
  return "Good evening";
}

function formatLastActivity(value: string | null): string {
  if (!value) {
    return "Not yet";
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}
