"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { PartnerNavOption } from "@/components/navigation/PartnerNavSelect";

type PresenterPartnerNavSelectProps = {
  disabled?: boolean;
  onApply: (partnerIds: string[]) => void;
  partners: PartnerNavOption[];
  selectedPartnerIds: string[];
};

export function PresenterPartnerNavSelect({
  disabled = false,
  onApply,
  partners,
  selectedPartnerIds,
}: PresenterPartnerNavSelectProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [draftPartnerIds, setDraftPartnerIds] = useState<string[]>(selectedPartnerIds);

  const selectedPartnerSet = useMemo(() => new Set(selectedPartnerIds), [selectedPartnerIds]);
  const draftPartnerSet = useMemo(() => new Set(draftPartnerIds), [draftPartnerIds]);
  const filteredPartners = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return partners;
    }
    return partners.filter((partner) =>
      [partner.name, partner.description ?? ""].join(" ").toLowerCase().includes(query),
    );
  }, [partners, search]);

  const canOpen = !disabled && partners.length > 0;
  const triggerLabel = getTriggerLabel(partners, selectedPartnerIds);

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

  useEffect(() => {
    if (open) {
      setSearch("");
      setDraftPartnerIds(selectedPartnerIds);
    }
  }, [open, selectedPartnerIds]);

  function togglePartner(partnerId: string) {
    setDraftPartnerIds((current) =>
      current.includes(partnerId)
        ? current.filter((item) => item !== partnerId)
        : [...current, partnerId],
    );
  }

  function applyPartnerIds(partnerIds: string[]) {
    onApply(partnerIds);
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
        <span className="partner-nav-value">{triggerLabel}</span>
        {canOpen ? <span className="partner-nav-caret" aria-hidden="true" /> : null}
      </button>

      {open ? (
        <div className="partner-nav-menu presenter-partner-menu" role="menu" aria-label="Presenter partners">
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
            <button
              type="button"
              role="menuitem"
              className={!selectedPartnerIds.length ? "partner-nav-option active" : "partner-nav-option"}
              onClick={() => applyPartnerIds([])}
            >
              <span className="partner-nav-tile all">All</span>
              <span className="partner-nav-option-copy">
                <strong>All Partners</strong>
                <small>{partners.length} partner{partners.length === 1 ? "" : "s"}</small>
              </span>
              <span className="partner-nav-option-status">
                {!selectedPartnerIds.length ? "Active" : ""}
              </span>
            </button>

            {filteredPartners.map((partner) => {
              const isActive = selectedPartnerSet.has(partner.id);
              const isChecked = draftPartnerSet.has(partner.id);
              return (
                <div
                  key={partner.id}
                  role="menuitem"
                  className={isActive || isChecked ? "partner-nav-option multi active" : "partner-nav-option multi"}
                >
                  <label className="partner-nav-checkwrap" aria-label={`Include ${partner.name}`}>
                    <input
                      className="partner-nav-checkbox"
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => togglePartner(partner.id)}
                    />
                  </label>
                  <button
                    type="button"
                    className="partner-nav-option-single"
                    onClick={() => applyPartnerIds([partner.id])}
                  >
                    <span className="partner-nav-tile">{getPartnerInitials(partner.name)}</span>
                    <span className="partner-nav-option-copy">
                      <strong>{partner.name}</strong>
                      <small>{formatUpdateCount(partner.updatesCount)}</small>
                    </span>
                  </button>
                  <span className="partner-nav-option-status">{isActive ? "Active" : ""}</span>
                </div>
              );
            })}
          </div>
          {!filteredPartners.length ? <p className="partner-nav-empty">No partners found</p> : null}
          <div className="partner-nav-footer">
            <button
              type="button"
              className="partner-nav-footer-button"
              onClick={() => setDraftPartnerIds([])}
            >
              Clear
            </button>
            <button
              type="button"
              className="partner-nav-footer-button primary"
              disabled={!draftPartnerIds.length}
              onClick={() => applyPartnerIds(draftPartnerIds)}
            >
              Select multiple
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function getTriggerLabel(partners: PartnerNavOption[], selectedPartnerIds: string[]) {
  if (!selectedPartnerIds.length) {
    return "All partners";
  }
  if (selectedPartnerIds.length === 1) {
    return partners.find((partner) => partner.id === selectedPartnerIds[0])?.name ?? "Selected partner";
  }
  return `${selectedPartnerIds.length} partners selected`;
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
  return `${count} update${count === 1 ? "" : "s"}`;
}
