"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  DraftEmail,
  PresenterAnalysis,
  PresenterMetadata,
  PresenterPartner,
  PresenterUpdate,
  draftPresenterEmail,
  getPresenterAnalysis,
  getPresenterMetadata,
  listPresenterUpdates,
} from "@/features/presenter/presenter-api";

type PresenterWorkspacePanelProps = {
  cycle: string;
  onCycleChange: (cycle: string) => void;
  onPartnerSelectionChange: (partnerIds: string[]) => void;
  onSectionChange: (section: string) => void;
  partners: PresenterPartner[];
  section: string;
  selectedPartnerIds: string[];
};

export function PresenterWorkspacePanel({
  cycle,
  onCycleChange,
  onPartnerSelectionChange,
  onSectionChange,
  partners,
  section,
  selectedPartnerIds,
}: PresenterWorkspacePanelProps) {
  const [search, setSearch] = useState("");
  const [updates, setUpdates] = useState<PresenterUpdate[]>([]);
  const [metadata, setMetadata] = useState<PresenterMetadata | null>(null);
  const [analysis, setAnalysis] = useState<PresenterAnalysis | null>(null);
  const [draftEmail, setDraftEmail] = useState<DraftEmail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyEmail, setBusyEmail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [askAiOpen, setAskAiOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    const singlePartnerId = selectedPartnerIds.length === 1 ? selectedPartnerIds[0] : null;

    Promise.all([
      listPresenterUpdates({ cycle, partnerIds: selectedPartnerIds, search }),
      getPresenterAnalysis({ cycle, partnerIds: selectedPartnerIds }),
      singlePartnerId ? getPresenterMetadata(singlePartnerId, cycle) : Promise.resolve(null),
    ])
      .then(([nextUpdates, nextAnalysis, nextMetadata]) => {
        if (mounted) {
          setUpdates(nextUpdates);
          setAnalysis(nextAnalysis);
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
  }, [cycle, search, selectedPartnerIds]);

  async function handleDraftEmail() {
    setBusyEmail(true);
    setError(null);
    try {
      setDraftEmail(await draftPresenterEmail({ cycle, partnerIds: selectedPartnerIds }));
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
    [partners, selectedPartnerIds],
  );
  const scopeLabel = selectedPartner
    ? selectedPartner.name
    : selectedPartnerIds.length
      ? `${selectedPartnerIds.length} partners selected`
      : "All Partners";
  const scopedPartnerCount = selectedPartnerIds.length || partners.length;
  const visibleUpdateCount = analysis?.update_count ?? updates.length;

  return (
    <div className={askAiOpen ? "presenter-workspace ask-ai-open" : "presenter-workspace"}>
      <section className="presenter-intel-header" aria-label="Presenter intelligence controls">
        <div className="presenter-intel-header-left">
          <div className="presenter-intel-copy">
            <h1>{scopeLabel}</h1>
            <p>
              {visibleUpdateCount} update{visibleUpdateCount === 1 ? "" : "s"} ·{" "}
              {formatCycleLabel(cycle)} · {scopedPartnerCount} of {partners.length} partner
              {partners.length === 1 ? "" : "s"}
            </p>
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
            <button
              type="button"
              className="presenter-cycle-nav"
              aria-label="Previous reporting period"
              onClick={() => {
                onCycleChange(shiftCycle(cycle, -1));
                setDraftEmail(null);
              }}
            >
              ‹
            </button>
            <input
              type="month"
              value={cycle}
              onChange={(event) => {
                onCycleChange(event.target.value);
                setDraftEmail(null);
              }}
              aria-label="Cycle"
            />
            <button
              type="button"
              className="presenter-cycle-nav"
              aria-label="Next reporting period"
              onClick={() => {
                onCycleChange(shiftCycle(cycle, 1));
                setDraftEmail(null);
              }}
            >
              ›
            </button>
          </div>
          <button
            type="button"
            className={askAiOpen ? "presenter-intel-btn primary active" : "presenter-intel-btn primary"}
            onClick={() => setAskAiOpen((current) => !current)}
          >
            <span className="presenter-ai-spark" aria-hidden="true" />
            <span>Ask AI</span>
          </button>
          <button
            type="button"
            className={section === "Decision Board" ? "presenter-intel-btn active" : "presenter-intel-btn"}
            onClick={() => onSectionChange("Decision Board")}
          >
            Deep Analysis
          </button>
        </div>
      </section>

      {error ? <p className="workspace-error inline-error">{error}</p> : null}

      <div className={askAiOpen ? "presenter-intel-layout with-ai" : "presenter-intel-layout"}>
        <div className="presenter-intel-main">
          {section === "Executive Summary" ? (
            <ExecutiveSummaryPanel analysis={analysis} loading={loading} />
          ) : null}

          {section === "Decision Board" ? (
            <DecisionBoardPanel analysis={analysis} loading={loading} />
          ) : null}

          {section === "Partner Intelligence" ? (
            <PartnerIntelligencePanel
              cycle={cycle}
              loading={loading}
              metadata={metadata}
              partners={partners}
              selectedPartnerCount={selectedPartnerIds.length}
              selectedPartner={selectedPartner}
              updates={updates}
            />
          ) : null}

          {section === "Draft Email" ? (
            <DraftEmailPanel
              draftEmail={draftEmail}
              loading={loading}
              onDraftEmail={handleDraftEmail}
              busyEmail={busyEmail}
              updates={updates}
            />
          ) : null}
        </div>

        {askAiOpen ? (
          <AskAiPanel
            analysis={analysis}
            partners={partners}
            selectedPartnerIds={selectedPartnerIds}
            selectedPartner={selectedPartner}
            updates={updates}
            onClose={() => setAskAiOpen(false)}
            onPartnerSelectionChange={onPartnerSelectionChange}
          />
        ) : null}
      </div>
    </div>
  );
}

function ExecutiveSummaryPanel({
  analysis,
  loading,
}: {
  analysis: PresenterAnalysis | null;
  loading: boolean;
}) {
  if (loading) {
    return <p className="muted-copy">Loading executive summary</p>;
  }
  return (
    <section className="presenter-panel">
      <div className="presenter-summary-grid">
        <MetricCard label="Approved Updates" value={analysis?.update_count ?? 0} />
        <MetricCard label="Partners" value={analysis?.partner_count ?? 0} />
        <MetricCard label="Source Types" value={Object.keys(analysis?.source_mix ?? {}).length} />
      </div>
      <div className="presenter-narrative">
        <p>{analysis?.executive_summary}</p>
      </div>
      <SourceMix sourceMix={analysis?.source_mix ?? {}} />
    </section>
  );
}

function DecisionBoardPanel({
  analysis,
  loading,
}: {
  analysis: PresenterAnalysis | null;
  loading: boolean;
}) {
  if (loading) {
    return <p className="muted-copy">Loading decision board</p>;
  }
  return (
    <section className="presenter-panel">
      <div className="contributor-table-wrap">
        <table className="updates-table">
          <thead>
            <tr>
              <th>Partner</th>
              <th>Signal</th>
              <th>Severity</th>
              <th>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {!analysis?.decision_board.length ? (
              <tr>
                <td colSpan={4}>No decision-board signals for this scope</td>
              </tr>
            ) : null}
            {analysis?.decision_board.map((item) => (
              <tr key={`${item.partner_id}-${item.signal}`}>
                <td>{item.partner_name}</td>
                <td>{item.signal}</td>
                <td>
                  <span className={`status-pill ${item.severity.toLowerCase()}`}>
                    {item.severity}
                  </span>
                </td>
                <td>{item.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PartnerIntelligencePanel({
  cycle,
  loading,
  metadata,
  partners,
  selectedPartnerCount,
  selectedPartner,
  updates,
}: {
  cycle: string;
  loading: boolean;
  metadata: PresenterMetadata | null;
  partners: PresenterPartner[];
  selectedPartnerCount: number;
  selectedPartner: PresenterPartner | null;
  updates: PresenterUpdate[];
}) {
  if (loading) {
    return <p className="muted-copy presenter-feed-loading">Loading partner intelligence</p>;
  }

  const scopeHint = selectedPartner
    ? null
    : selectedPartnerCount
      ? "Multiple partners selected. Select one partner to show partner metadata at the side."
      : "All partners selected. Select one partner to show partner metadata at the side.";

  return (
    <div className={selectedPartner ? "presenter-board-layout with-metadata" : "presenter-board-layout"}>
      {selectedPartner ? (
        <PresenterMetadataPane cycle={cycle} metadata={metadata} selectedPartner={selectedPartner} />
      ) : null}
      <section className="presenter-feed" aria-label="Approved updates">
        {scopeHint ? <p className="presenter-scope-hint">{scopeHint}</p> : null}
        <PresenterUpdatesFeed partners={partners} updates={updates} />
      </section>
    </div>
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
        dangerouslySetInnerHTML={{ __html: update.summary }}
      />
    );
  }
  return <div className="presenter-feed-summary">{update.summary}</div>;
}

function PresenterMetadataPane({
  cycle,
  metadata,
  selectedPartner,
}: {
  cycle: string;
  metadata: PresenterMetadata | null;
  selectedPartner: PresenterPartner;
}) {
  return (
    <aside className="presenter-meta-pane" aria-label="Partner metadata">
      <div className="presenter-meta-head">
        <div className="presenter-meta-title">Partner metadata</div>
      </div>
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
              <li key={item}>{item}</li>
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
  return (
    <div className="presenter-meta-card">
      <div className="presenter-meta-card-title">Resource library</div>
      <div className="presenter-meta-card-body">
        {metadata?.resources.length ? (
          <table className="presenter-meta-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Resource</th>
              </tr>
            </thead>
            <tbody>
              {metadata.resources.map((resource) => (
                <tr key={resource.resource_link_id}>
                  <td>{resource.title}</td>
                  <td>
                    <a
                      className="presenter-meta-link"
                      href={resource.url}
                      target="_blank"
                      rel="noreferrer"
                      aria-disabled={resource.disabled}
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

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="presenter-metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SourceMix({ sourceMix }: { sourceMix: Record<string, number> }) {
  const entries = Object.entries(sourceMix);
  if (!entries.length) {
    return <p className="muted-copy">No source mix available.</p>;
  }
  return (
    <div className="source-mix">
      {entries.map(([source, count]) => (
        <span key={source}>
          {source}: {count}
        </span>
      ))}
    </div>
  );
}

function AskAiPanel({
  analysis,
  partners,
  selectedPartnerIds,
  selectedPartner,
  updates,
  onClose,
  onPartnerSelectionChange,
}: {
  analysis: PresenterAnalysis | null;
  partners: PresenterPartner[];
  selectedPartnerIds: string[];
  selectedPartner: PresenterPartner | null;
  updates: PresenterUpdate[];
  onClose: () => void;
  onPartnerSelectionChange: (partnerIds: string[]) => void;
}) {
  const [question, setQuestion] = useState("");
  const [scopeSearch, setScopeSearch] = useState("");
  const [messages, setMessages] = useState<Array<{ id: number; kind: "user" | "assistant"; text: string }>>([]);
  const scopeLabel = selectedPartner
    ? selectedPartner.name
    : selectedPartnerIds.length
      ? `${selectedPartnerIds.length} partners`
      : "All Partners";
  const filteredPartners = partners.filter((partner) =>
    partner.name.toLowerCase().includes(scopeSearch.trim().toLowerCase()),
  );

  function submitQuestion(value: string) {
    const cleaned = value.trim();
    if (!cleaned) {
      return;
    }
    setMessages((current) => [
      ...current,
      { id: Date.now(), kind: "user", text: cleaned },
      {
        id: Date.now() + 1,
        kind: "assistant",
        text: buildAskAiAnswer(cleaned, scopeLabel, analysis, updates),
      },
    ]);
    setQuestion("");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitQuestion(question);
  }

  return (
    <aside className="presenter-ai-panel" aria-label="Ask AI">
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
                onClick={() => submitQuestion(item)}
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
              <div className="presenter-ai-answer-text">{message.text}</div>
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
        />
        <button className="presenter-ai-voice-button" type="button" aria-label="Ask with voice" title="Ask with voice" />
        <button className="presenter-ai-send" type="submit" aria-label="Send AI question" title="Send" />
      </form>
    </aside>
  );
}

function formatCycleLabel(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}-01T00:00:00`));
}

function shiftCycle(value: string, months: number): string {
  const [year, month] = value.split("-").map(Number);
  const next = new Date(year, month - 1 + months, 1);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`;
}

function groupUpdatesByPartner(updates: PresenterUpdate[], partners: PresenterPartner[]) {
  const partnerOrder = new Map(partners.map((partner, index) => [partner.partner_id, index]));
  const groups = new Map<string, { partnerId: string; partnerName: string; items: PresenterUpdate[] }>();
  for (const update of updates) {
    const existing = groups.get(update.partner_id);
    if (existing) {
      existing.items.push(update);
    } else {
      groups.set(update.partner_id, {
        partnerId: update.partner_id,
        partnerName: update.partner_name,
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
  return (value ?? "")
    .split(/\n|•/)
    .map((item) => item.replace(/^\s*[-*]\s+/, "").trim())
    .filter(Boolean);
}

function looksLikeAllowedUpdateHtml(value: string): boolean {
  return /<\/?(a|strong|b|em|i|u|ol|ul|li)\b/i.test(value);
}

function buildAskAiAnswer(
  question: string,
  scopeLabel: string,
  analysis: PresenterAnalysis | null,
  updates: PresenterUpdate[],
): string {
  const updateCount = analysis?.update_count ?? updates.length;
  const partnerCount = analysis?.partner_count ?? new Set(updates.map((update) => update.partner_id)).size;
  const firstUpdate = updates[0]?.summary?.replace(/<[^>]*>/g, "");
  const riskCount = analysis?.decision_board.length ?? 0;

  if (/risk|ask|blocker/i.test(question)) {
    return riskCount
      ? `${scopeLabel} has ${riskCount} decision-board signal${riskCount === 1 ? "" : "s"} in this scope. The approved updates should be reviewed with the metadata risk list before sending a presenter summary.`
      : `${scopeLabel} has no decision-board risks flagged from approved metadata in this scope.`;
  }

  if (/next|month|coming/i.test(question)) {
    return firstUpdate
      ? `${scopeLabel} has ${updateCount} approved update${updateCount === 1 ? "" : "s"} across ${partnerCount} partner${partnerCount === 1 ? "" : "s"}. The most recent signal to carry forward is: ${firstUpdate}`
      : `${scopeLabel} has no approved updates in this scope yet.`;
  }

  return `${scopeLabel} currently has ${updateCount} approved update${updateCount === 1 ? "" : "s"} across ${partnerCount} partner${partnerCount === 1 ? "" : "s"}. ${analysis?.executive_summary ?? "No generated summary is available yet."}`;
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
