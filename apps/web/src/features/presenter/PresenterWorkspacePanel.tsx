"use client";

import {
  type CSSProperties,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactElement,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { GlobalLoader } from "@/components/foundation/GlobalLoader";
import {
  DraftEmail,
  PresenterAskAnswer,
  PresenterDecisionBoard,
  PresenterDecisionBoardSignal,
  PresenterExecutiveSummary,
  PresenterMetadata,
  PresenterPartner,
  PresenterPeriodQuery,
  PresenterUpdate,
  askPresenterAi,
  draftPresenterEmail,
  generatePresenterDecisionBoard,
  generatePresenterExecutiveSummary,
  getPresenterMetadata,
  listPresenterUpdates,
  synthesizePresenterAiVoice,
  transcribePresenterAiVoice,
} from "@/features/presenter/presenter-api";

type PresenterWorkspacePanelProps = {
  askAiOpen: boolean;
  emailRequestKey: number;
  onAskAiClose: () => void;
  onPartnerSelectionChange: (partnerIds: string[]) => void;
  onPeriodChange: (period: PresenterPeriodQuery) => void;
  partners: PresenterPartner[];
  period: PresenterPeriodQuery;
  section: string;
  selectedPartnerIds: string[];
};

type PresenterAiMessage = {
  id: number;
  kind: "user" | "assistant";
  text: string;
  answer?: PresenterAskAnswer;
  error?: boolean;
  pending?: boolean;
};

export function PresenterWorkspacePanel({
  askAiOpen,
  emailRequestKey,
  onAskAiClose,
  onPartnerSelectionChange,
  onPeriodChange,
  partners,
  period,
  section,
  selectedPartnerIds,
}: PresenterWorkspacePanelProps) {
  const [search, setSearch] = useState("");
  const [updates, setUpdates] = useState<PresenterUpdate[]>([]);
  const [metadata, setMetadata] = useState<PresenterMetadata | null>(null);
  const [executiveSummary, setExecutiveSummary] = useState<PresenterExecutiveSummary | null>(null);
  const [decisionBoard, setDecisionBoard] = useState<PresenterDecisionBoard | null>(null);
  const [draftEmail, setDraftEmail] = useState<DraftEmail | null>(null);
  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [decisionBoardLoading, setDecisionBoardLoading] = useState(false);
  const [busyEmail, setBusyEmail] = useState(false);
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [emailCopyNotice, setEmailCopyNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [decisionBoardError, setDecisionBoardError] = useState<string | null>(null);
  const cycle = period.cycle;
  const selectedPartnerScopeKey = [...selectedPartnerIds].sort().join("|");

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    const singlePartnerId = selectedPartnerIds.length === 1 ? selectedPartnerIds[0] : null;

    Promise.all([
      listPresenterUpdates({
        cycle,
        dateStart: period.dateStart,
        dateEnd: period.dateEnd,
        partnerIds: selectedPartnerIds,
        search,
      }),
      singlePartnerId ? getPresenterMetadata(singlePartnerId, cycle) : Promise.resolve(null),
    ])
      .then(([nextUpdates, nextMetadata]) => {
        if (mounted) {
          setUpdates(nextUpdates);
          setMetadata(nextMetadata);
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load presenter view.");
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
  }, [cycle, period.dateEnd, period.dateStart, search, selectedPartnerScopeKey]);

  useEffect(() => {
    let mounted = true;
    if (section !== "Executive Summary") {
      return () => {
        mounted = false;
      };
    }
    setSummaryLoading(true);
    setSummaryError(null);
    generatePresenterExecutiveSummary({
      cycle,
      dateStart: period.dateStart,
      dateEnd: period.dateEnd,
      partnerIds: selectedPartnerIds,
    })
      .then((nextSummary) => {
        if (mounted) {
          setExecutiveSummary(nextSummary);
        }
      })
      .catch((error) => {
        if (mounted) {
          setSummaryError(error instanceof Error ? error.message : "Unable to generate executive summary.");
          setExecutiveSummary(null);
        }
      })
      .finally(() => {
        if (mounted) {
          setSummaryLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [cycle, period.dateEnd, period.dateStart, section, selectedPartnerScopeKey]);

  useEffect(() => {
    let mounted = true;
    if (section !== "Decision Board") {
      return () => {
        mounted = false;
      };
    }
    setDecisionBoardLoading(true);
    setDecisionBoardError(null);
    generatePresenterDecisionBoard({
      cycle,
      dateStart: period.dateStart,
      dateEnd: period.dateEnd,
      partnerIds: selectedPartnerIds,
    })
      .then((nextBoard) => {
        if (mounted) {
          setDecisionBoard(nextBoard);
        }
      })
      .catch((error) => {
        if (mounted) {
          setDecisionBoardError(error instanceof Error ? error.message : "Unable to generate decision board.");
          setDecisionBoard(null);
        }
      })
      .finally(() => {
        if (mounted) {
          setDecisionBoardLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [cycle, period.dateEnd, period.dateStart, section, selectedPartnerScopeKey]);

  useEffect(() => {
    if (emailRequestKey <= 0) {
      return;
    }
    void handleDraftEmail();
  }, [emailRequestKey]);

  async function handleDraftEmail() {
    setBusyEmail(true);
    setEmailModalOpen(true);
    setEmailCopyNotice(null);
    setError(null);
    try {
      setDraftEmail(
        await draftPresenterEmail({
          cycle,
          dateStart: period.dateStart,
          dateEnd: period.dateEnd,
          partnerIds: selectedPartnerIds,
        }),
      );
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to draft email.");
    } finally {
      setBusyEmail(false);
    }
  }

  const selectedPartner = useMemo(
    () =>
      selectedPartnerIds.length === 1
        ? partners.find((partner) => partner.partner_id === selectedPartnerIds[0]) ?? null
        : null,
    [partners, selectedPartnerScopeKey],
  );
  const scopeLabel = selectedPartner
    ? selectedPartner.name
    : selectedPartnerIds.length
      ? `${selectedPartnerIds.length} partners selected`
      : "All Partners";

  return (
    <div className={askAiOpen ? "presenter-workspace ask-ai-open" : "presenter-workspace"}>
      <section className="presenter-intel-header" aria-label="Presenter intelligence controls">
        <div className="presenter-intel-header-left">
          <div className="presenter-intel-copy">
            <h1>{scopeLabel}</h1>
          </div>
          <div className="presenter-search-wrap">
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search updates..."
              aria-label="Search approved updates"
            />
          </div>
        </div>
        <div className="presenter-intel-actions">
          <div className="presenter-cycle-control" aria-label="Reporting period">
            <PresenterPeriodPicker
              period={period}
              onChange={(nextPeriod) => {
                setDraftEmail(null);
                setEmailCopyNotice(null);
                onPeriodChange(nextPeriod);
              }}
            />
          </div>
        </div>
      </section>

      {error ? <p className="workspace-error inline-error">{error}</p> : null}

      <div className={askAiOpen ? "presenter-intel-layout with-ai" : "presenter-intel-layout"}>
        <div className="presenter-intel-main">
          {section === "Executive Summary" ? (
            <ExecutiveSummaryPanel
              error={summaryError}
              loading={summaryLoading}
              search={search}
              summary={executiveSummary}
            />
          ) : null}

          {section === "Decision Board" ? (
            <DecisionBoardPanel
              board={decisionBoard}
              error={decisionBoardError}
              loading={decisionBoardLoading}
              search={search}
            />
          ) : null}

          {section === "Partner Updates" ? (
            <PartnerIntelligencePanel
              cycle={cycle}
              loading={loading}
              metadata={metadata}
              partners={partners}
              selectedPartner={selectedPartner}
              updates={updates}
            />
          ) : null}

          {section === "Event Calendar" ? (
            <EventCalendarPanel loading={loading} />
          ) : null}
        </div>

        {askAiOpen ? (
          <AskAiPanel
            partners={partners}
            period={period}
            selectedPartnerIds={selectedPartnerIds}
            selectedPartner={selectedPartner}
            onClose={onAskAiClose}
            onPartnerSelectionChange={onPartnerSelectionChange}
          />
        ) : null}
      </div>
      <PresenterEmailModal
        busy={busyEmail}
        copyNotice={emailCopyNotice}
        draftEmail={draftEmail}
        open={emailModalOpen}
        onClose={() => {
          setEmailModalOpen(false);
          setEmailCopyNotice(null);
        }}
        onCopyNotice={setEmailCopyNotice}
        onRefresh={handleDraftEmail}
      />
    </div>
  );
}

function PresenterPeriodPicker({
  period,
  onChange,
}: {
  period: PresenterPeriodQuery;
  onChange: (period: PresenterPeriodQuery) => void;
}) {
  const pickerRef = useRef<HTMLDivElement | null>(null);
  const rangeStartRef = useRef<HTMLInputElement | null>(null);
  const rangeEndRef = useRef<HTMLInputElement | null>(null);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"month" | "range">(
    period.dateStart && period.dateEnd ? "range" : "month",
  );
  const [viewYear, setViewYear] = useState(parseCycle(period.cycle)?.year ?? new Date().getFullYear());
  const [rangeStart, setRangeStart] = useState(
    period.dateStart ?? `${period.cycle}-01`,
  );
  const [rangeEnd, setRangeEnd] = useState(period.dateEnd ?? lastDayOfCycle(period.cycle));
  const currentMonth = currentCycle();

  useEffect(() => {
    setMode(period.dateStart && period.dateEnd ? "range" : "month");
    setRangeStart(period.dateStart ?? `${period.cycle}-01`);
    setRangeEnd(period.dateEnd ?? lastDayOfCycle(period.cycle));
    setViewYear(parseCycle(period.cycle)?.year ?? new Date().getFullYear());
  }, [period.cycle, period.dateEnd, period.dateStart]);

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (!pickerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  function handleShift(months: number) {
    if (period.dateStart && period.dateEnd) {
      const nextStart = shiftIsoDateByMonths(period.dateStart, months);
      const nextEnd = shiftIsoDateByMonths(period.dateEnd, months);
      if (nextStart && nextEnd && nextEnd.slice(0, 7) <= currentMonth) {
        onChange({ cycle: nextEnd.slice(0, 7), dateStart: nextStart, dateEnd: nextEnd });
      }
      return;
    }
    const nextCycle = shiftCycle(period.cycle, months);
    if (nextCycle <= currentMonth) {
      onChange({ cycle: nextCycle, dateStart: null, dateEnd: null });
    }
  }

  function selectMonth(month: number) {
    const nextCycle = `${viewYear}-${String(month).padStart(2, "0")}`;
    if (nextCycle > currentMonth) {
      return;
    }
    onChange({ cycle: nextCycle, dateStart: null, dateEnd: null });
    setOpen(false);
  }

  function applyRange() {
    const nextRangeStart = rangeStartRef.current?.value || rangeStart;
    const nextRangeEnd = rangeEndRef.current?.value || rangeEnd;
    if (
      !nextRangeStart ||
      !nextRangeEnd ||
      nextRangeStart > nextRangeEnd ||
      nextRangeEnd.slice(0, 7) > currentMonth
    ) {
      return;
    }
    onChange({
      cycle: nextRangeEnd.slice(0, 7),
      dateStart: nextRangeStart,
      dateEnd: nextRangeEnd,
    });
    setOpen(false);
  }

  const rangeInvalid =
    !rangeStart || !rangeEnd || rangeStart > rangeEnd || rangeEnd.slice(0, 7) > currentMonth;

  return (
    <div className={`presenter-period-picker${open ? " open" : ""}`} ref={pickerRef}>
      <button
        type="button"
        className="presenter-period-nav"
        aria-label="Previous reporting period"
        onClick={() => handleShift(-1)}
      >
        ‹
      </button>
      <button
        type="button"
        className="presenter-period-summary"
        aria-expanded={open}
        aria-label="Open reporting period picker"
        onClick={() => setOpen((current) => !current)}
      >
        {formatPeriodLabel(period)}
      </button>
      <button
        type="button"
        className="presenter-period-nav"
        aria-label="Next reporting period"
        onClick={() => handleShift(1)}
        disabled={
          period.dateStart && period.dateEnd
            ? period.dateEnd.slice(0, 7) >= currentMonth
            : period.cycle >= currentMonth
        }
      >
        ›
      </button>
      <div className="presenter-period-menu" role="dialog" aria-label="Reporting period picker">
        <div className="presenter-period-menu-head">
          <button
            type="button"
            className="presenter-period-year"
            onClick={() => setViewYear((year) => Math.max(2020, year - 1))}
          >
            {viewYear}
          </button>
          <div className="presenter-period-tabs" role="tablist" aria-label="Reporting period type">
            <button
              type="button"
              className={mode === "month" ? "active" : ""}
              onClick={() => setMode("month")}
            >
              Month
            </button>
            <button
              type="button"
              className={mode === "range" ? "active" : ""}
              onClick={() => setMode("range")}
            >
              Range
            </button>
          </div>
          <button
            type="button"
            className="presenter-period-year-next"
            onClick={() => setViewYear((year) => Math.min(new Date().getFullYear(), year + 1))}
            disabled={viewYear >= new Date().getFullYear()}
            aria-label="Next year"
          >
            ›
          </button>
        </div>
        {mode === "month" ? (
          <>
            <div className="presenter-period-month-grid">
              {MONTH_LABELS.map((label, index) => {
                const month = index + 1;
                const cycleValue = `${viewYear}-${String(month).padStart(2, "0")}`;
                const disabled = cycleValue > currentMonth;
                return (
                  <button
                    type="button"
                    key={label}
                    className={cycleValue === period.cycle && !period.dateStart ? "active" : ""}
                    disabled={disabled}
                    onClick={() => selectMonth(month)}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            <div className="presenter-period-note">Future months are not selectable</div>
          </>
        ) : (
          <div className="presenter-period-range-view">
            <div className="presenter-period-range-fields">
              <label>
                <span>Start date</span>
                <input
                  ref={rangeStartRef}
                  type="date"
                  value={rangeStart}
                  max={rangeEnd || undefined}
                  onChange={(event) => setRangeStart(event.target.value)}
                />
              </label>
              <label>
                <span>End date</span>
                <input
                  ref={rangeEndRef}
                  type="date"
                  value={rangeEnd}
                  min={rangeStart || undefined}
                  max={lastDayOfCycle(currentMonth)}
                  onChange={(event) => setRangeEnd(event.target.value)}
                />
              </label>
            </div>
            <div className="presenter-period-range-selected">
              {rangeInvalid ? "Select a valid past or current reporting range." : `${rangeStart} to ${rangeEnd}`}
            </div>
            <button
              type="button"
              className="presenter-period-apply"
              disabled={rangeInvalid}
              onClick={applyRange}
            >
              Apply range
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function PresenterEmailModal({
  busy,
  copyNotice,
  draftEmail,
  open,
  onClose,
  onCopyNotice,
  onRefresh,
}: {
  busy: boolean;
  copyNotice: string | null;
  draftEmail: DraftEmail | null;
  open: boolean;
  onClose: () => void;
  onCopyNotice: (notice: string | null) => void;
  onRefresh: () => void;
}) {
  if (!open) {
    return null;
  }

  async function copyEmail() {
    if (!draftEmail) {
      return;
    }
    const text = `Subject: ${draftEmail.subject}\n\n${draftEmail.body}`;
    try {
      await navigator.clipboard.writeText(text);
      onCopyNotice("Copied formatted email to clipboard.");
    } catch {
      onCopyNotice("Unable to copy email.");
    }
  }

  return (
    <div className="presenter-email-modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="presenter-email-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="presenter-email-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="presenter-email-modal-head">
          <h2 id="presenter-email-title">Generate email for this period</h2>
          <button type="button" aria-label="Close email modal" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="presenter-email-modal-body">
          {busy ? (
            <GlobalLoader
              label="Drafting email"
              detail="Composing from approved updates in the selected period."
              size="compact"
              tone="ai"
            />
          ) : null}
          {!busy && draftEmail ? (
            <>
              <div className="presenter-email-subject-row">
                <span>Subject: {draftEmail.subject}</span>
                <button type="button" aria-label="Copy formatted email" onClick={copyEmail}>
                  Copy
                </button>
              </div>
              <pre className="presenter-email-preview">{draftEmail.body}</pre>
              {copyNotice ? <p className="presenter-email-copy-notice">{copyNotice}</p> : null}
            </>
          ) : null}
          {!busy && !draftEmail ? (
            <div className="presenter-email-empty">
              Generate the email preview to review the presenter-ready draft.
            </div>
          ) : null}
        </div>
        <div className="presenter-email-modal-actions">
          <button className="modal-btn secondary disabled" type="button" disabled>
            Connect Outlook
          </button>
          <button className="modal-btn secondary" type="button" onClick={onRefresh} disabled={busy}>
            Regenerate
          </button>
          <button className="modal-btn primary" type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </section>
    </div>
  );
}

function ExecutiveSummaryPanel({
  error,
  loading,
  search,
  summary,
}: {
  error: string | null;
  loading: boolean;
  search: string;
  summary: PresenterExecutiveSummary | null;
}) {
  if (loading) {
    return (
      <GlobalLoader
        label="Generating executive summary"
        detail="Reading approved updates for this selected scope."
        tone="ai"
      />
    );
  }
  const searchTerm = search.trim();
  const visibleBullets = filterSummaryBullets(summary?.bullets ?? [], searchTerm);
  const groupedBullets = groupSummaryBulletsByCategory(visibleBullets);
  return (
    <section className="presenter-panel executive-summary-panel">
      <div className="executive-summary-card">
        <div className="executive-summary-head">
          <span className="executive-summary-mark" aria-hidden="true" />
          <div>
            <h2>Executive Summary</h2>
            <p>Generated from approved updates in the selected scope.</p>
          </div>
        </div>
        {error ? <p className="workspace-error inline-error">{error}</p> : null}
        {!error && !summary?.bullets.length ? (
          <p className="executive-summary-empty">
            {summary?.source_note ?? "No approved updates found for this selection."}
          </p>
        ) : null}
        {!error && summary?.bullets.length && !visibleBullets.length ? (
          <p className="executive-summary-empty">No executive summary lines match the search term.</p>
        ) : null}
        {groupedBullets.length ? (
          <div className="executive-summary-groups">
            {groupedBullets.map((category) => (
              <section className="executive-summary-category" key={category.label}>
                <h3>{renderHighlightedText(category.label, searchTerm)}</h3>
                <div className="executive-summary-category-body">
                  {category.partners.map((group) =>
                    group.heading ? (
                      <section className="executive-summary-group" key={group.heading}>
                        <h4>{renderHighlightedText(`${group.heading}:`, searchTerm)}</h4>
                        <ul className="executive-summary-list nested">
                          {group.items.map((item) => (
                            <li key={`${group.heading}-${item}`}>
                              {renderHighlightedText(item, searchTerm)}
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : (
                      <ul className="executive-summary-list" key={`${category.label}-ungrouped`}>
                        {group.items.map((item) => (
                          <li key={item}>{renderHighlightedText(item, searchTerm)}</li>
                        ))}
                      </ul>
                    ),
                  )}
                </div>
              </section>
            ))}
          </div>
        ) : null}
        {summary?.source_note && summary.bullets.length ? (
          <p className="executive-summary-note">{summary.source_note}</p>
        ) : null}
      </div>
    </section>
  );
}

function DecisionBoardPanel({
  board,
  error,
  loading,
  search,
}: {
  board: PresenterDecisionBoard | null;
  error: string | null;
  loading: boolean;
  search: string;
}) {
  if (loading) {
    return (
      <GlobalLoader
        label="Generating decision board"
        detail="Identifying grounded decisions, asks, risks, and watch items."
        tone="ai"
      />
    );
  }
  const searchTerm = search.trim();
  const visibleSignals = filterDecisionBoardSignals(board?.signals ?? [], searchTerm);
  const groupedSignals = groupDecisionBoardSignals(visibleSignals);

  return (
    <section className="presenter-panel decision-board-panel">
      <div className="decision-board-card">
        <div className="decision-board-head">
          <span className="decision-board-mark" aria-hidden="true" />
          <div>
            <h2>Decision Board</h2>
            <p>Generated from approved updates in the selected scope.</p>
          </div>
          {board?.signals.length ? (
            <span className="decision-board-count">{board.signals.length} open</span>
          ) : null}
        </div>
        {error ? <p className="workspace-error inline-error">{error}</p> : null}
        {!error && !board?.signals.length ? (
          <p className="decision-board-empty">
            {board?.source_note ??
              "No open blockers, risks, deadlines, or action items detected for this selection."}
          </p>
        ) : null}
        {!error && board?.signals.length && !visibleSignals.length ? (
          <p className="decision-board-empty">No decision board items match the search term.</p>
        ) : null}
        {visibleSignals.length ? (
          <div className="decision-board-groups">
            {groupedSignals.map((group) => (
              <section
                className={`decision-board-group ${group.priority.toLowerCase()}`}
                key={group.priority}
              >
                <div className="decision-board-group-head">
                  <span>{group.label}</span>
                  <span>{group.count}</span>
                </div>
                <div className="decision-board-stack">
                  {group.partners.map((partnerGroup) => (
                    <article
                      className={`decision-board-item ${group.priority.toLowerCase()}`}
                      key={`${group.priority}-${partnerGroup.partnerId}`}
                    >
                      <div className="decision-board-item-partner">
                        {renderHighlightedText(partnerGroup.partnerName, searchTerm)}
                      </div>
                      <ul className="decision-board-item-list">
                        {partnerGroup.items.map((item, index) => (
                          <li
                            className="decision-board-item-entry"
                            key={`${item.update_id ?? item.metadata_risk_id ?? item.title}-${index}`}
                          >
                            <div className="decision-board-item-title">
                              {renderHighlightedText(item.title, searchTerm)}
                            </div>
                            <p className="decision-board-item-copy">
                              <span>Update</span>
                              {renderHighlightedText(item.update_line, searchTerm)}
                            </p>
                            {item.action ? (
                              <p className="decision-board-item-action">
                                <span>Action</span>
                                {renderHighlightedText(item.action, searchTerm)}
                              </p>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : null}
        {board?.source_note && board.signals.length ? (
          <p className="decision-board-note">{board.source_note}</p>
        ) : null}
      </div>
    </section>
  );
}

function PartnerIntelligencePanel({
  cycle,
  loading,
  metadata,
  partners,
  selectedPartner,
  updates,
}: {
  cycle: string;
  loading: boolean;
  metadata: PresenterMetadata | null;
  partners: PresenterPartner[];
  selectedPartner: PresenterPartner | null;
  updates: PresenterUpdate[];
}) {
  const [metadataCollapsed, setMetadataCollapsed] = useState(false);
  const [metadataWidth, setMetadataWidth] = useState(420);

  if (loading) {
    return (
      <GlobalLoader
        label="Loading partner intelligence"
        detail="Gathering approved updates and partner metadata."
      />
    );
  }

  function startMetadataResize(event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = metadataWidth;

    function handleMove(moveEvent: PointerEvent) {
      const nextWidth = clamp(startWidth + moveEvent.clientX - startX, 280, 720);
      setMetadataWidth(nextWidth);
    }

    function handleUp() {
      document.removeEventListener("pointermove", handleMove);
      document.removeEventListener("pointerup", handleUp);
    }

    document.addEventListener("pointermove", handleMove);
    document.addEventListener("pointerup", handleUp);
  }

  const layoutStyle = selectedPartner
    ? ({
        "--presenter-meta-width": metadataCollapsed ? "190px" : `${metadataWidth}px`,
      } as CSSProperties)
    : undefined;

  return (
    <div
      className={
        selectedPartner
          ? `presenter-board-layout with-metadata${metadataCollapsed ? " metadata-collapsed" : ""}`
          : "presenter-board-layout"
      }
      style={layoutStyle}
    >
      {selectedPartner ? (
        <PresenterMetadataPane
          collapsed={metadataCollapsed}
          cycle={cycle}
          metadata={metadata}
          onResizeStart={startMetadataResize}
          onToggleCollapsed={() => setMetadataCollapsed((current) => !current)}
          selectedPartner={selectedPartner}
        />
      ) : null}
      <section className="presenter-feed" aria-label="Approved updates">
        <PresenterUpdatesFeed partners={partners} updates={updates} />
      </section>
    </div>
  );
}

function EventCalendarPanel({ loading }: { loading: boolean }) {
  if (loading) {
    return <GlobalLoader label="Loading event calendar" detail="Preparing events for this period." />;
  }

  return (
    <section className="presenter-panel">
      <div className="presenter-empty-module">
        <strong>Event Calendar</strong>
        <span>Calendar events will appear here once this presenter module is connected.</span>
      </div>
    </section>
  );
}

function DraftEmailPanel({
  busyEmail,
  draftEmail,
  loading,
  onDraftEmail,
  updates,
}: {
  busyEmail: boolean;
  draftEmail: DraftEmail | null;
  loading: boolean;
  onDraftEmail: () => void;
  updates: PresenterUpdate[];
}) {
  return (
    <section className="presenter-panel">
      <div className="presenter-panel-heading">
        <div>
          <p className="eyebrow">{updates.length} approved update(s)</p>
          <h3>Draft Email</h3>
        </div>
        <button
          className="primary-action compact-action"
          type="button"
          disabled={busyEmail || loading}
          onClick={onDraftEmail}
        >
          {busyEmail ? "Drafting" : "Draft email"}
        </button>
      </div>
      {draftEmail ? (
        <div className="draft-email-preview">
          <strong>{draftEmail.subject}</strong>
          <pre>{draftEmail.body}</pre>
        </div>
      ) : (
        <p className="muted-copy">Generate a read-only draft from approved updates.</p>
      )}
    </section>
  );
}

function PresenterUpdatesFeed({
  partners,
  updates,
}: {
  partners: PresenterPartner[];
  updates: PresenterUpdate[];
}) {
  const groups = groupUpdatesByPartner(updates, partners);
  if (!groups.length) {
    return (
      <div className="presenter-feed-empty">
        <strong>No approved updates yet</strong>
        <span>Approved contributor updates for this scope and cycle will appear here.</span>
      </div>
    );
  }

  return (
    <div className="presenter-feed-stack">
      {groups.map((group) => (
        <article className="presenter-feed-card" key={group.partnerId}>
          <div className="presenter-feed-meta">
            <span
              className="presenter-feed-partner-dot"
              style={{ backgroundColor: partnerColor(group.partnerName) }}
              aria-hidden="true"
            />
            <span className="presenter-feed-partner">{group.partnerName}</span>
          </div>
          <div
            className={
              group.items.length > 1
                ? "presenter-feed-update-list multi"
                : "presenter-feed-update-list single"
            }
          >
            {group.items.map((update) => (
              <div
                className={group.items.length > 1 ? "presenter-feed-update-row multi" : "presenter-feed-update-row"}
                key={update.update_id}
              >
                {group.items.length > 1 ? (
                  <span className="presenter-feed-update-marker" aria-hidden="true" />
                ) : null}
                <PresenterUpdateSummary update={update} />
              </div>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function PresenterUpdateSummary({ update }: { update: PresenterUpdate }) {
  if (looksLikeAllowedUpdateHtml(update.summary)) {
    return (
      <div
        className="presenter-feed-summary"
        dangerouslySetInnerHTML={{ __html: normalizePresenterSummaryHtml(update.summary) }}
      />
    );
  }
  return <div className="presenter-feed-summary">{update.summary}</div>;
}

function PresenterMetadataPane({
  collapsed,
  cycle,
  metadata,
  onResizeStart,
  onToggleCollapsed,
  selectedPartner,
}: {
  collapsed: boolean;
  cycle: string;
  metadata: PresenterMetadata | null;
  onResizeStart: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onToggleCollapsed: () => void;
  selectedPartner: PresenterPartner;
}) {
  return (
    <aside className={collapsed ? "presenter-meta-pane collapsed" : "presenter-meta-pane"} aria-label="Partner metadata">
      <div className="presenter-meta-head">
        <div className="presenter-meta-title">Partner Metadata</div>
        <button
          className="presenter-meta-toggle"
          type="button"
          aria-label={collapsed ? "Expand partner metadata" : "Collapse partner metadata"}
          onClick={onToggleCollapsed}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>
      {!collapsed ? (
        <div
          className="presenter-meta-resize"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize partner metadata"
          onPointerDown={onResizeStart}
        />
      ) : null}
      {collapsed ? null : (
      <div className="presenter-meta-body">
        <div className="presenter-meta-card">
          <div className="presenter-meta-card-title">Status</div>
          <div className="presenter-meta-card-body presenter-meta-grid">
            <div>
              <div className="presenter-meta-label">Status</div>
              <span className={`presenter-meta-status-pill status-${metadata?.status ?? "green"}`}>
                {metadata?.status ?? "Not set"}
              </span>
            </div>
            <div>
              <div className="presenter-meta-label">Cycle</div>
              <div className="presenter-meta-value">{formatCycleLabel(cycle)}</div>
            </div>
          </div>
        </div>

        <PresenterMetaTextCard title="Why this partner" value={metadata?.why_this_partner} />
        <PresenterMetaTextCard title="Highlights / status" value={metadata?.highlights_status} />
        <PresenterMetaTextCard title="Business priority" value={metadata?.business_priority} />
        <PresenterMetaTextCard title="Goals" value={metadata?.goals} />
        <PresenterMetaTextCard title="Execution timeline" value={metadata?.execution_timeline} />
        <PresenterRisksTable metadata={metadata} />
        <PresenterResources metadata={metadata} selectedPartnerName={selectedPartner.name} />
      </div>
      )}
    </aside>
  );
}

function PresenterMetaTextCard({
  title,
  value,
}: {
  title: string;
  value: string | null | undefined;
}) {
  const items = splitMetadataValue(value);
  return (
    <div className="presenter-meta-card">
      <div className="presenter-meta-card-title">{title}</div>
      <div className="presenter-meta-card-body">
        {items.length ? (
          <ul className="presenter-meta-bullets">
            {items.map((item) => (
              <li key={item}>{renderHighlightedText(item, "")}</li>
            ))}
          </ul>
        ) : (
          <div className="presenter-meta-muted">Not set</div>
        )}
      </div>
    </div>
  );
}

function PresenterRisksTable({ metadata }: { metadata: PresenterMetadata | null }) {
  return (
    <div className="presenter-meta-card">
      <div className="presenter-meta-card-title">Key risks & issues</div>
      <div className="presenter-meta-card-body">
      <table className="presenter-meta-table">
        <thead>
          <tr>
            <th>Risk</th>
            <th>Severity</th>
            <th>Assigned</th>
            <th>Ramification</th>
          </tr>
        </thead>
        <tbody>
          {!metadata?.risks.length ? (
            <tr>
              <td colSpan={4}>Not set</td>
            </tr>
          ) : null}
          {metadata?.risks.map((risk) => (
            <tr key={risk.description}>
              <td>{risk.description}</td>
              <td>
                <span className={`presenter-meta-severity severity-${(risk.severity ?? "").toLowerCase()}`}>
                  {risk.severity ?? "Not set"}
                </span>
              </td>
              <td>{risk.assigned_to ?? "Unassigned"}</td>
              <td>{risk.ramification ?? "None"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}

function PresenterResources({
  metadata,
  selectedPartnerName,
}: {
  metadata: PresenterMetadata | null;
  selectedPartnerName: string;
}) {
  const visibleResources = metadata?.resources.filter((resource) => !resource.disabled) ?? [];

  return (
    <div className="presenter-meta-card">
      <div className="presenter-meta-card-title">Resource library</div>
      <div className="presenter-meta-card-body">
        {visibleResources.length ? (
          <table className="presenter-meta-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Resource</th>
              </tr>
            </thead>
            <tbody>
              {visibleResources.map((resource) => (
                <tr key={resource.resource_link_id}>
                  <td>{resource.title}</td>
                  <td>
                    <a
                      className="presenter-meta-link"
                      href={resource.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {resource.url}
                    </a>
                    {resource.description ? (
                      <div className="presenter-meta-note">{resource.description}</div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="presenter-meta-muted">No resources saved for {selectedPartnerName}.</div>
        )}
      </div>
    </div>
  );
}

function AskAiPanel({
  partners,
  period,
  selectedPartnerIds,
  selectedPartner,
  onClose,
  onPartnerSelectionChange,
}: {
  partners: PresenterPartner[];
  period: PresenterPeriodQuery;
  selectedPartnerIds: string[];
  selectedPartner: PresenterPartner | null;
  onClose: () => void;
  onPartnerSelectionChange: (partnerIds: string[]) => void;
}) {
  const [question, setQuestion] = useState("");
  const [scopeSearch, setScopeSearch] = useState("");
  const [panelWidth, setPanelWidth] = useState(540);
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<PresenterAiMessage[]>([]);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [recording, setRecording] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [lastVoiceReply, setLastVoiceReply] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const recordingStartedAtRef = useRef(0);
  const recordingStopTimerRef = useRef<number | null>(null);
  const replyAudioRef = useRef<HTMLAudioElement | null>(null);
  const replyAudioUrlRef = useRef<string | null>(null);
  const scopeLabel = selectedPartner
    ? selectedPartner.name
    : selectedPartnerIds.length
      ? `${selectedPartnerIds.length} partners`
      : "All Partners";
  const filteredPartners = partners.filter((partner) =>
    partner.name.toLowerCase().includes(scopeSearch.trim().toLowerCase()),
  );

  useEffect(() => {
    return () => {
      stopVoiceRecording();
      stopReplyAudio();
    };
  }, []);

  async function submitQuestion(value: string, options: { speak?: boolean } = {}) {
    const cleaned = value.trim();
    if (!cleaned || busy) {
      return;
    }
    const userId = Date.now();
    const assistantId = userId + 1;
    setMessages((current) => [
      ...current,
      { id: userId, kind: "user", text: cleaned },
      { id: assistantId, kind: "assistant", text: "Thinking through the selected approved context...", pending: true },
    ]);
    setQuestion("");
    setBusy(true);
    try {
      const answer = await askPresenterAi({
        cycle: period.cycle,
        dateStart: period.dateStart,
        dateEnd: period.dateEnd,
        partnerIds: selectedPartnerIds,
        question: cleaned,
      });
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? { id: assistantId, kind: "assistant", text: answer.answer, answer }
            : message,
        ),
      );
      if (options.speak) {
        await speakAssistantAnswer(answer.answer);
      }
    } catch (error) {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                id: assistantId,
                kind: "assistant",
                text: error instanceof Error ? error.message : "Unable to ask AI assistant.",
                error: true,
              }
            : message,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  async function speakAssistantAnswer(text: string) {
    const cleaned = text.trim();
    if (!cleaned) {
      return;
    }
    try {
      setVoiceStatus("Generating voice reply...");
      stopReplyAudio();
      const blob = await synthesizePresenterAiVoice(cleaned);
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      replyAudioUrlRef.current = audioUrl;
      replyAudioRef.current = audio;
      audio.addEventListener("ended", () => {
        setVoiceStatus("");
        stopReplyAudio();
      });
      setVoiceStatus("Speaking...");
      setLastVoiceReply(cleaned);
      setSpeaking(true);
      await audio.play();
    } catch {
      setSpeaking(false);
      setVoiceStatus("Voice reply is unavailable.");
    }
  }

  function stopReplyAudio() {
    if (replyAudioRef.current) {
      replyAudioRef.current.pause();
      replyAudioRef.current.currentTime = 0;
      replyAudioRef.current = null;
    }
    if (replyAudioUrlRef.current) {
      URL.revokeObjectURL(replyAudioUrlRef.current);
      replyAudioUrlRef.current = null;
    }
    setSpeaking(false);
  }

  async function handleVoiceClick() {
    if (recording) {
      stopVoiceRecording();
      return;
    }
    if (busy) {
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setVoiceStatus("Voice input is not supported in this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const options =
        MediaRecorder.isTypeSupported?.("audio/webm")
          ? { mimeType: "audio/webm" }
          : undefined;
      const recorder = new MediaRecorder(stream, options);
      audioStreamRef.current = stream;
      recorderRef.current = recorder;
      audioChunksRef.current = [];
      recordingStartedAtRef.current = Date.now();
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size) {
          audioChunksRef.current.push(event.data);
        }
      });
      recorder.addEventListener("stop", () => {
        void handleVoiceRecordingStopped();
      });
      recorder.start();
      setRecording(true);
      setVoiceStatus("Listening... click the mic again to stop.");
      recordingStopTimerRef.current = window.setTimeout(stopVoiceRecording, 60000);
    } catch {
      setVoiceStatus("Microphone access is blocked.");
    }
  }

  function stopVoiceRecording() {
    if (recordingStopTimerRef.current) {
      window.clearTimeout(recordingStopTimerRef.current);
      recordingStopTimerRef.current = null;
    }
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
      return;
    }
    stopVoiceStream();
    setRecording(false);
  }

  function stopVoiceStream() {
    audioStreamRef.current?.getTracks().forEach((track) => track.stop());
    audioStreamRef.current = null;
    recorderRef.current = null;
  }

  async function handleVoiceRecordingStopped() {
    const durationMs = Date.now() - recordingStartedAtRef.current;
    const mimeType = recorderRef.current?.mimeType || "audio/webm";
    const blob = new Blob(audioChunksRef.current, { type: mimeType });
    stopVoiceStream();
    setRecording(false);
    if (!blob.size) {
      setVoiceStatus("I could not hear anything. Try again or type your question.");
      return;
    }
    try {
      setVoiceStatus("Transcribing...");
      const transcript = await transcribePresenterAiVoice({ audio: blob, durationMs });
      setQuestion(transcript);
      setVoiceStatus("Transcript ready. Asking assistant...");
      await submitQuestion(transcript, { speak: true });
      setVoiceStatus("");
    } catch {
      setVoiceStatus("Could not transcribe audio. Try again or type your question.");
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitQuestion(question);
  }

  function startPanelResize(event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = panelWidth;

    function handleMove(moveEvent: PointerEvent) {
      setPanelWidth(clamp(startWidth + startX - moveEvent.clientX, 420, 820));
    }

    function handleUp() {
      document.removeEventListener("pointermove", handleMove);
      document.removeEventListener("pointerup", handleUp);
    }

    document.addEventListener("pointermove", handleMove);
    document.addEventListener("pointerup", handleUp);
  }

  return (
    <aside
      className="presenter-ai-panel"
      aria-label="Ask AI"
      style={{ "--presenter-ai-width": `${panelWidth}px` } as CSSProperties}
    >
      <div
        className="presenter-ai-resize"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize Ask AI panel"
        onPointerDown={startPanelResize}
      />
      <div className="presenter-ai-panel-head">
        <div className="presenter-ai-title">
          <span className="presenter-ai-status-dot" aria-hidden="true" />
          <span className="presenter-ai-title-main">AI Assistant</span>
          <span className="presenter-ai-title-scope">· {scopeLabel}</span>
        </div>
        <button type="button" className="presenter-ai-close" aria-label="Close Ask AI" onClick={onClose}>
          ×
        </button>
      </div>
      <div className="presenter-ai-config">
        <span>Grounded mode</span>
        <strong>Approved updates + metadata</strong>
      </div>
      <div className="presenter-ai-scope">
        <div className="presenter-ai-scope-main">
          <span>Scope:</span>
          <strong className="presenter-ai-scope-pill">{scopeLabel}</strong>
        </div>
        <details className="presenter-ai-scope-switch">
          <summary>Change</summary>
          <div className="presenter-ai-scope-menu">
            <input
              className="presenter-ai-scope-search"
              value={scopeSearch}
              onChange={(event) => setScopeSearch(event.target.value)}
              placeholder="Search partners..."
              aria-label="Search AI scope partners"
            />
            <div className="presenter-ai-scope-list">
              <button
                type="button"
                className={!selectedPartnerIds.length ? "presenter-ai-scope-option active" : "presenter-ai-scope-option"}
                onClick={() => onPartnerSelectionChange([])}
              >
                <span className="presenter-ai-scope-icon all">AP</span>
                <span>
                  <span className="presenter-ai-scope-title">All Partners</span>
                  <span className="presenter-ai-scope-sub">{partners.length} partners</span>
                </span>
                {!selectedPartnerIds.length ? <span className="presenter-ai-scope-check">✓</span> : null}
              </button>
              {filteredPartners.map((partner) => {
                const active = selectedPartnerIds.length === 1 && selectedPartnerIds[0] === partner.partner_id;
                return (
                  <button
                    type="button"
                    className={active ? "presenter-ai-scope-option active" : "presenter-ai-scope-option"}
                    key={partner.partner_id}
                    onClick={() => onPartnerSelectionChange([partner.partner_id])}
                  >
                    <span
                      className="presenter-ai-scope-icon"
                      style={{ backgroundColor: partnerColor(partner.name) }}
                    >
                      {getPartnerInitials(partner.name)}
                    </span>
                    <span>
                      <span className="presenter-ai-scope-title">{partner.name}</span>
                      <span className="presenter-ai-scope-sub">
                        {partner.approved_updates_count} update
                        {partner.approved_updates_count === 1 ? "" : "s"}
                      </span>
                    </span>
                    {active ? <span className="presenter-ai-scope-check">✓</span> : null}
                  </button>
                );
              })}
              {!filteredPartners.length ? (
                <div className="presenter-ai-scope-empty">No partners found</div>
              ) : null}
            </div>
          </div>
        </details>
      </div>
      <div className="presenter-ai-messages">
        <div className="presenter-ai-greeting">
          <span className="presenter-ai-greeting-mark">✦</span>
          <div className="presenter-ai-greeting-text">Hi, what can I help you with today?</div>
        </div>
        <div className="presenter-ai-suggestion-label">Try asking</div>
        <div className="presenter-ai-suggestions" aria-label="Suggested questions">
          {["What changed this cycle?", "What is coming up next month?", "Summarize the biggest risks and asks."].map(
            (item) => (
              <button
                className="presenter-ai-suggestion"
                type="button"
                key={item}
                disabled={busy}
                onClick={() => void submitQuestion(item)}
              >
                {item}
              </button>
            ),
          )}
        </div>
        {messages.map((message) => (
          <div
            className={
              message.kind === "user"
                ? "presenter-ai-turn presenter-ai-turn-user"
                : "presenter-ai-turn presenter-ai-turn-assistant"
            }
            key={message.id}
          >
            {message.kind === "assistant" ? (
              <span className="presenter-ai-assistant-avatar">✦</span>
            ) : null}
            <div
              className={
                message.kind === "user" ? "presenter-ai-bubble question" : "presenter-ai-answer-shell"
              }
            >
              <div
                className={
                  message.error
                    ? "presenter-ai-answer-text error"
                    : message.pending
                      ? "presenter-ai-answer-text pending"
                      : "presenter-ai-answer-text"
                }
              >
                {message.answer && !message.pending && !message.error ? (
                  <PresenterAiAnswer
                    answer={message.answer}
                    onFollowup={(nextQuestion) => void submitQuestion(nextQuestion)}
                  />
                ) : (
                  renderAskAiText(message.text)
                )}
              </div>
            </div>
            {message.kind === "user" ? <span className="presenter-ai-user-avatar">You</span> : null}
          </div>
        ))}
      </div>
      <form className="presenter-ai-input" onSubmit={handleSubmit}>
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about a partner, source, or cycle..."
          aria-label="Ask AI"
          autoComplete="off"
          disabled={busy}
        />
        <button
          className={recording ? "presenter-ai-voice-button recording" : "presenter-ai-voice-button"}
          type="button"
          aria-label={recording ? "Stop voice recording" : "Ask with voice"}
          title={recording ? "Stop recording" : "Ask with voice"}
          disabled={busy && !recording}
          onClick={() => void handleVoiceClick()}
        >
          {recording ? (
            <span className="presenter-ai-voice-stop" aria-hidden="true" />
          ) : (
            <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
              <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z" />
              <path d="M19 11a7 7 0 0 1-14 0" />
              <path d="M12 18v3" />
              <path d="M8 21h8" />
            </svg>
          )}
        </button>
        <button className="presenter-ai-send" type="submit" aria-label="Send AI question" title="Send" disabled={busy} />
        {voiceStatus || lastVoiceReply ? (
          <div className="presenter-ai-voice-status">
            {voiceStatus ? <span>{voiceStatus}</span> : null}
            {speaking ? (
              <button type="button" onClick={stopReplyAudio}>
                Stop
              </button>
            ) : lastVoiceReply ? (
              <button type="button" onClick={() => void speakAssistantAnswer(lastVoiceReply)}>
                Replay
              </button>
            ) : null}
          </div>
        ) : null}
      </form>
    </aside>
  );
}

function PresenterAiAnswer({
  answer,
  onFollowup,
}: {
  answer: PresenterAskAnswer;
  onFollowup: (question: string) => void;
}) {
  return (
    <div className="presenter-ai-structured-answer">
      <p>{answer.answer}</p>
      {answer.bullets.length ? (
        <ul className="presenter-ai-list">
          {answer.bullets.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      {answer.sections.map((section) => (
        <section className="presenter-ai-section" key={`${section.title}-${section.body ?? ""}`}>
          <h4>{section.title}</h4>
          {section.body ? <p>{section.body}</p> : null}
          {section.bullets.length ? (
            <ul className="presenter-ai-list">
              {section.bullets.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ))}
      {answer.tables.map((table) => (
        <div className="presenter-ai-table-wrap" key={`${table.title ?? "table"}-${table.columns.join("-")}`}>
          {table.title ? <h4>{table.title}</h4> : null}
          <table className="presenter-ai-table">
            <thead>
              <tr>
                {table.columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, rowIndex) => (
                <tr key={`${row.join("-")}-${rowIndex}`}>
                  {table.columns.map((column, columnIndex) => (
                    <td key={`${column}-${columnIndex}`}>{row[columnIndex] ?? ""}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      {answer.suggested_followups.length ? (
        <div className="presenter-ai-followups" aria-label="Suggested follow-up questions">
          {answer.suggested_followups.map((question) => (
            <button type="button" key={question} onClick={() => onFollowup(question)}>
              {question}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function formatPeriodLabel(period: PresenterPeriodQuery): string {
  if (period.dateStart && period.dateEnd) {
    return `${formatShortDate(period.dateStart)} - ${formatShortDate(period.dateEnd)}`;
  }
  return formatCycleLabel(period.cycle);
}

function formatShortDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function formatCycleLabel(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}-01T00:00:00`));
}

function parseCycle(cycle: string): { year: number; month: number } | null {
  const match = /^(\d{4})-(\d{2})$/.exec(cycle);
  if (!match) {
    return null;
  }
  return { year: Number(match[1]), month: Number(match[2]) };
}

function currentCycle(): string {
  return new Date().toISOString().slice(0, 7);
}

function shiftCycle(value: string, months: number): string {
  const [year, month] = value.split("-").map(Number);
  const next = new Date(year, month - 1 + months, 1);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`;
}

function lastDayOfCycle(cycle: string): string {
  const parsed = parseCycle(cycle);
  if (!parsed) {
    return `${cycle}-01`;
  }
  const lastDay = new Date(parsed.year, parsed.month, 0);
  return `${lastDay.getFullYear()}-${String(lastDay.getMonth() + 1).padStart(2, "0")}-${String(
    lastDay.getDate(),
  ).padStart(2, "0")}`;
}

function shiftIsoDateByMonths(value: string, months: number): string | null {
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) {
    return null;
  }
  const next = new Date(year, month - 1 + months, day);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-${String(
    next.getDate(),
  ).padStart(2, "0")}`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function groupUpdatesByPartner(updates: PresenterUpdate[], partners: PresenterPartner[]) {
  const partnerOrder = new Map(partners.map((partner, index) => [partner.partner_id, index]));
  const groups = new Map<string, { partnerId: string; partnerName: string; items: PresenterUpdate[] }>();
  for (const update of updates) {
    const topicLabel = update.topic_label || update.partner_name || "Events/Topics";
    const groupId = update.scope === "topic" || !update.partner_id ? `topic:${topicLabel}` : update.partner_id;
    const groupName =
      update.scope === "topic" || !update.partner_id ? topicLabel : update.partner_name;
    const existing = groups.get(groupId);
    if (existing) {
      existing.items.push(update);
    } else {
      groups.set(groupId, {
        partnerId: groupId,
        partnerName: groupName,
        items: [update],
      });
    }
  }
  return Array.from(groups.values()).sort((a, b) => {
    const orderA = partnerOrder.get(a.partnerId) ?? Number.MAX_SAFE_INTEGER;
    const orderB = partnerOrder.get(b.partnerId) ?? Number.MAX_SAFE_INTEGER;
    if (orderA !== orderB) {
      return orderA - orderB;
    }
    return a.partnerName.localeCompare(b.partnerName);
  });
}

function splitMetadataValue(value: string | null | undefined): string[] {
  const text = value ?? "";
  if (!text.trim()) {
    return [];
  }

  const blocks = text
    .split(/\n{2,}|•/)
    .map((item) => cleanMetadataListItem(item))
    .filter(Boolean);
  if (blocks.length > 1) {
    return blocks;
  }

  const lines = text.split("\n");
  const hasIndentedContinuation = lines.some((line) => /^\s+[-*•\d.]/.test(line));
  if (!hasIndentedContinuation && lines.length > 1) {
    return lines.map((item) => cleanMetadataListItem(item)).filter(Boolean);
  }

  return [cleanMetadataListItem(text)].filter(Boolean);
}

function cleanMetadataListItem(value: string): string {
  return value.replace(/^\s*[-*]\s+/, "").trim();
}

function filterSummaryBullets(bullets: string[], searchTerm: string): string[] {
  const cleanedSearch = searchTerm.toLowerCase();
  if (!cleanedSearch) {
    return bullets;
  }
  return bullets.filter((bullet) => bullet.toLowerCase().includes(cleanedSearch));
}

const EXECUTIVE_SUMMARY_CATEGORY_ORDER = [
  "HyperScalers",
  "OSVs",
  "ISVs",
  "Customers",
  "Other Partners",
];

const EXECUTIVE_SUMMARY_PARTNER_CATEGORY: Record<string, string> = {
  amazon: "HyperScalers",
  "amazon web services": "HyperScalers",
  aws: "HyperScalers",
  gcp: "HyperScalers",
  google: "HyperScalers",
  "google cloud": "HyperScalers",
  microsoft: "HyperScalers",
  msft: "HyperScalers",

  canonical: "OSVs",
  redhat: "OSVs",
  "red hat": "OSVs",
  rhel: "OSVs",
  rhat: "OSVs",
  suse: "OSVs",

  "sap hana cloud": "ISVs",
  cohere: "ISVs",
  databricks: "ISVs",
  elastic: "ISVs",
  elasticco: "ISVs",
  mongodb: "ISVs",
  mistral: "ISVs",
  nutanix: "ISVs",
  pinecone: "ISVs",
  rafay: "ISVs",
  "rafay systems": "ISVs",
  redis: "ISVs",
  tinkerblox: "ISVs",
  tinklrbox: "ISVs",
  vmware: "ISVs",

  jpmc: "Customers",
  "jp morgan": "Customers",
  "jp morgan chase": "Customers",
  optum: "Customers",
  salesforce: "Customers",
  teradata: "Customers",
  uber: "Customers",
  uhg: "Customers",
  "united health group": "Customers",
};

function groupSummaryBulletsByCategory(bullets: string[]) {
  const partnerGroups = groupSummaryBulletsByPartner(bullets);
  const categoryMap = new Map<
    string,
    { label: string; partners: Array<{ heading: string | null; items: string[] }> }
  >();

  for (const group of partnerGroups) {
    const categoryLabel = group.heading
      ? executiveSummaryCategoryForPartner(group.heading)
      : "Other Partners";
    const existing = categoryMap.get(categoryLabel);
    if (existing) {
      existing.partners.push(group);
    } else {
      categoryMap.set(categoryLabel, { label: categoryLabel, partners: [group] });
    }
  }

  return EXECUTIVE_SUMMARY_CATEGORY_ORDER.flatMap((label) => {
    const category = categoryMap.get(label);
    return category ? [category] : [];
  });
}

function groupSummaryBulletsByPartner(bullets: string[]) {
  const groups: Array<{ heading: string | null; items: string[] }> = [];
  const groupIndex = new Map<string, { heading: string | null; items: string[] }>();
  for (const bullet of bullets) {
    const parsed = parseSummaryBulletLeadIn(bullet);
    if (!parsed) {
      const ungrouped = groups.find((group) => group.heading === null);
      if (ungrouped) {
        ungrouped.items.push(bullet);
      } else {
        groups.push({ heading: null, items: [bullet] });
      }
      continue;
    }
    const existing = groupIndex.get(parsed.heading);
    if (existing) {
      existing.items.push(parsed.item);
    } else {
      const group = { heading: parsed.heading, items: [parsed.item] };
      groupIndex.set(parsed.heading, group);
      groups.push(group);
    }
  }
  return groups;
}

function executiveSummaryCategoryForPartner(partnerName: string): string {
  const normalizedName = normalizeExecutiveSummaryPartnerName(partnerName);
  return EXECUTIVE_SUMMARY_PARTNER_CATEGORY[normalizedName] ?? "Other Partners";
}

function normalizeExecutiveSummaryPartnerName(partnerName: string): string {
  return partnerName
    .trim()
    .toLowerCase()
    .replace(/\./g, "")
    .replace(/\s+/g, " ");
}

function parseSummaryBulletLeadIn(bullet: string): { heading: string; item: string } | null {
  const match = /^([^:]{2,80}):\s+(.+)$/.exec(bullet.trim());
  if (!match) {
    return null;
  }
  const heading = match[1].trim();
  const item = match[2].trim();
  if (!heading || !item || /^https?\/\//i.test(heading)) {
    return null;
  }
  return { heading, item };
}

function filterDecisionBoardSignals(
  signals: PresenterDecisionBoardSignal[],
  searchTerm: string,
): PresenterDecisionBoardSignal[] {
  const cleanedSearch = searchTerm.toLowerCase();
  if (!cleanedSearch) {
    return signals;
  }
  return signals.filter((signal) =>
    [
      signal.partner_name,
      signal.priority,
      signal.title,
      signal.update_line,
      signal.action,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(cleanedSearch),
  );
}

function groupDecisionBoardSignals(signals: PresenterDecisionBoardSignal[]) {
  const groups = [
    {
      priority: "P1",
      label: "Critical",
      items: [] as PresenterDecisionBoardSignal[],
    },
    {
      priority: "P2",
      label: "Urgent",
      items: [] as PresenterDecisionBoardSignal[],
    },
    {
      priority: "P3",
      label: "Watch",
      items: [] as PresenterDecisionBoardSignal[],
    },
  ];
  const fallback = groups[2];
  for (const signal of signals) {
    const group = groups.find((item) => item.priority === signal.priority) ?? fallback;
    group.items.push(signal);
  }
  return groups
    .filter((group) => group.items.length > 0)
    .map((group) => ({
      ...group,
      count: group.items.length,
      partners: groupDecisionBoardSignalsByPartner(group.items),
    }));
}

function groupDecisionBoardSignalsByPartner(signals: PresenterDecisionBoardSignal[]) {
  const partnerGroups = new Map<
    string,
    { partnerId: string; partnerName: string; items: PresenterDecisionBoardSignal[] }
  >();
  for (const signal of signals) {
    const partnerName = signal.partner_name ?? "Selected partner";
    const partnerId = signal.partner_id ?? `partner:${partnerName}`;
    const existing = partnerGroups.get(partnerId);
    if (existing) {
      existing.items.push(signal);
    } else {
      partnerGroups.set(partnerId, {
        partnerId,
        partnerName,
        items: [signal],
      });
    }
  }
  return Array.from(partnerGroups.values());
}

function renderHighlightedText(text: string, searchTerm: string): Array<string | ReactElement> {
  const parts: Array<string | ReactElement> = [];
  const linkPattern = /\[([^\]]+)\]\((https?:\/\/[^)\s]+|mailto:[^)\s]+|\/[^)\s]*|#[^)\s]+)\)/g;
  let lastIndex = 0;
  let match = linkPattern.exec(text);
  while (match) {
    if (match.index > lastIndex) {
      parts.push(...highlightPlainText(text.slice(lastIndex, match.index), searchTerm));
    }
    parts.push(
      <a href={match[2]} key={`${match[1]}-${match.index}`} target="_blank" rel="noreferrer">
        {highlightPlainText(match[1], searchTerm)}
      </a>,
    );
    lastIndex = match.index + match[0].length;
    match = linkPattern.exec(text);
  }
  if (lastIndex < text.length) {
    parts.push(...highlightPlainText(text.slice(lastIndex), searchTerm));
  }
  return parts.length ? parts : [text];
}

function highlightPlainText(text: string, searchTerm: string): Array<string | ReactElement> {
  const cleanedSearch = searchTerm.trim();
  if (!cleanedSearch) {
    return [text];
  }
  const pattern = new RegExp(`(${escapeRegExp(cleanedSearch)})`, "ig");
  return text.split(pattern).map((part, index) =>
    part.toLowerCase() === cleanedSearch.toLowerCase() ? (
      <mark key={`${part}-${index}`}>{part}</mark>
    ) : (
      part
    ),
  );
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function renderAskAiText(text: string): ReactElement[] {
  const lines = text.split("\n");
  return lines.map((line, lineIndex) => (
    <span key={`${lineIndex}-${line}`}>
      {renderAskAiInlineLinks(line)}
      {lineIndex < lines.length - 1 ? <br /> : null}
    </span>
  ));
}

function renderAskAiInlineLinks(text: string): Array<string | ReactElement> {
  const parts: Array<string | ReactElement> = [];
  const linkPattern = /\[([^\]]+)\]\((https?:\/\/[^)\s]+|mailto:[^)\s]+|\/[^)\s]*|#[^)\s]+)\)/g;
  let lastIndex = 0;
  let match = linkPattern.exec(text);
  while (match) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <a href={match[2]} key={`${match[1]}-${match.index}`} target="_blank" rel="noreferrer">
        {match[1]}
      </a>,
    );
    lastIndex = match.index + match[0].length;
    match = linkPattern.exec(text);
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts.length ? parts : [text];
}

function looksLikeAllowedUpdateHtml(value: string): boolean {
  return /<\/?(a|strong|b|em|i|u|ol|ul|li|p|br|div)\b/i.test(value);
}

function normalizePresenterSummaryHtml(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  return trimmed
    .replace(/<\/p>\s*<p\b[^>]*>/gi, "<br>")
    .replace(/^<p\b[^>]*>/i, "")
    .replace(/<\/p>$/i, "")
    .replace(/<p\b[^>]*>/gi, "")
    .replace(/<\/p>/gi, "<br>");
}

function getPartnerInitials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function partnerColor(name: string): string {
  const colors = ["#0ea5c7", "#2563eb", "#14b8a6", "#7c3aed", "#059669", "#d97706", "#475569"];
  const total = name.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return colors[total % colors.length];
}
