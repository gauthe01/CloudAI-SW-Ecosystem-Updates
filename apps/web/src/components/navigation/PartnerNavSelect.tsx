"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export type PartnerNavOption = {
  id: string;
  name: string;
  description?: string | null;
  updatesCount?: number;
};

type PartnerNavSelectProps = {
  disabled?: boolean;
  onSelect: (partnerId: string | null) => void;
  partners: PartnerNavOption[];
  selectedPartnerId: string | null;
};

export function PartnerNavSelect({
  disabled = false,
  onSelect,
  partners,
  selectedPartnerId,
}: PartnerNavSelectProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const selectedPartner =
    partners.find((partner) => partner.id === selectedPartnerId) ?? (partners.length === 1 ? partners[0] : null);
  const canOpen = !disabled && partners.length > 1;

  const filteredPartners = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return partners;
    }
    return partners.filter((partner) =>
      [partner.name, partner.description ?? ""].join(" ").toLowerCase().includes(query),
    );
  }, [partners, search]);

  useEffect(() => {
    function closeOnOutsideClick(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  function handleSelect(partnerId: string | null) {
    onSelect(partnerId);
    setOpen(false);
    setSearch("");
  }

  return (
    <div className={open ? "partner-nav-select open" : "partner-nav-select"} ref={rootRef}>
      <button
        type="button"
        className="partner-nav-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={!canOpen}
        onClick={() => {
          if (canOpen) {
            setOpen((current) => !current);
          }
        }}
      >
        <span className="partner-nav-label">Select the partner</span>
        <span className="partner-nav-value">{selectedPartner?.name ?? "Select partner"}</span>
        {canOpen ? <span className="partner-nav-caret" aria-hidden="true" /> : null}
      </button>

      {open ? (
        <div className="partner-nav-menu" role="menu" aria-label="Assigned partners">
          <input
            className="partner-nav-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search partners..."
            aria-label="Search partners"
            autoComplete="off"
          />
          <div className="partner-nav-list">
            {filteredPartners.map((partner) => {
              const isActive = partner.id === selectedPartner?.id;
              return (
                <button
                  key={partner.id}
                  type="button"
                  role="menuitem"
                  className={isActive ? "partner-nav-option active" : "partner-nav-option"}
                  onClick={() => handleSelect(partner.id)}
                >
                  <span className="partner-nav-tile">{getPartnerInitials(partner.name)}</span>
                  <span className="partner-nav-option-copy">
                    <strong>{partner.name}</strong>
                    <small>{formatUpdateCount(partner.updatesCount)}</small>
                  </span>
                  <span className="partner-nav-option-status">{isActive ? "Active" : ""}</span>
                </button>
              );
            })}
          </div>
          {!filteredPartners.length ? (
            <p className="partner-nav-empty">No matching partners.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function getPartnerInitials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function formatUpdateCount(value: number | undefined) {
  const count = value ?? 0;
  return `${count} pending update${count === 1 ? "" : "s"}`;
}
