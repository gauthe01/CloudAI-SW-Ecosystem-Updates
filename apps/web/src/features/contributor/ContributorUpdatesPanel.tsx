"use client";

import { useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode } from "react";

import {
  PartnerUpdate,
  approveContributorPartnerUpdate,
  dismissContributorPartnerUpdate,
  editContributorPartnerUpdate,
  listContributorPartnerUpdates,
} from "@/features/contributor/contributor-updates-api";

type ContributorUpdatesPanelProps = {
  partnerId: string;
  cycle: string;
  cycleLabel: string;
  status: "pending" | "approved";
  search: string;
  reloadKey: number;
  onLifecycleChange: () => void;
};

type EditState = {
  updateId: string;
  title: string;
  summary: string;
};

type DateFilter = "cycle" | "7" | "30";
type SourceFilterKey = "manual" | "jira" | "slack" | "files" | "github" | "email";

const SOURCE_FILTERS: { value: SourceFilterKey; label: string }[] = [
  { value: "manual", label: "Manual" },
  { value: "jira", label: "Jira" },
  { value: "slack", label: "Slack" },
  { value: "files", label: "Files" },
  { value: "github", label: "GitHub" },
  { value: "email", label: "Email" },
];

export function ContributorUpdatesPanel({
  partnerId,
  cycle,
  status,
  search,
  reloadKey,
  onLifecycleChange,
}: ContributorUpdatesPanelProps) {
  const [updates, setUpdates] = useState<PartnerUpdate[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyUpdateId, setBusyUpdateId] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditState | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [selectedSources, setSelectedSources] = useState<SourceFilterKey[]>([]);
  const [dateFilter, setDateFilter] = useState<DateFilter>("cycle");
  const [openSourceUpdateId, setOpenSourceUpdateId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const filterRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    listContributorPartnerUpdates({ partnerId, cycle, status, search })
      .then((nextUpdates) => {
        if (mounted) {
          setUpdates(nextUpdates);
          setOpenSourceUpdateId(null);
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load updates.");
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
  }, [partnerId, cycle, status, search, reloadKey]);

  useEffect(() => {
    if (!filterOpen) {
      return;
    }

    function closeWhenOutside(event: PointerEvent) {
      const target = event.target;
      if (target instanceof Node && filterRef.current?.contains(target)) {
        return;
      }
      setFilterOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setFilterOpen(false);
      }
    }

    document.addEventListener("pointerdown", closeWhenOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeWhenOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [filterOpen]);

  async function handleApprove(updateId: string) {
    await runAction(updateId, () => approveContributorPartnerUpdate(partnerId, updateId));
  }

  async function handleDismiss(updateId: string) {
    await runAction(updateId, () => dismissContributorPartnerUpdate(partnerId, updateId));
  }

  async function handleBulkAction(action: "approve" | "dismiss") {
    if (
      action === "dismiss" &&
      !window.confirm(`Dismiss ${filteredUpdates.length} pending update(s)? This removes them from the active queue.`)
    ) {
      return;
    }
    setError(null);
    try {
      for (const update of filteredUpdates) {
        setBusyUpdateId(update.update_id);
        if (action === "approve") {
          await approveContributorPartnerUpdate(partnerId, update.update_id);
        } else {
          await dismissContributorPartnerUpdate(partnerId, update.update_id);
        }
      }
      setUpdates((current) =>
        current.filter((update) => !filteredUpdates.some((item) => item.update_id === update.update_id)),
      );
      onLifecycleChange();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to update lifecycle.");
    } finally {
      setBusyUpdateId(null);
    }
  }

  async function runAction(updateId: string, action: () => Promise<PartnerUpdate>) {
    setBusyUpdateId(updateId);
    setError(null);
    try {
      await action();
      setUpdates((current) => current.filter((update) => update.update_id !== updateId));
      onLifecycleChange();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to update lifecycle.");
    } finally {
      setBusyUpdateId(null);
    }
  }

  async function handleEditSave() {
    if (!editing) {
      return;
    }
    setBusyUpdateId(editing.updateId);
    setError(null);
    try {
      const savedUpdate = await editContributorPartnerUpdate(partnerId, editing.updateId, {
        title: editing.title,
        summary: editing.summary,
      });
      setUpdates((current) =>
        current.map((update) => (update.update_id === savedUpdate.update_id ? savedUpdate : update)),
      );
      setEditing(null);
      setOpenSourceUpdateId(null);
      onLifecycleChange();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to edit update.");
    } finally {
      setBusyUpdateId(null);
    }
  }

  const heading = status === "pending" ? "Pending Updates" : "Approved Updates";
  const emptyLabel = status === "pending" ? "No pending updates" : "No approved updates";
  const sourceOptions = SOURCE_FILTERS;
  const filteredUpdates = useMemo(
    () =>
      updates.filter((update) => {
        const sourceMatches =
          selectedSources.length === 0 || selectedSources.includes(sourceKey(update));
        const dateMatches = dateMatchesFilter(update.created_at, dateFilter);
        return sourceMatches && dateMatches;
      }),
    [updates, selectedSources, dateFilter],
  );

  return (
    <section className="contributor-tab-panel" aria-label={heading}>
      <div className="contributor-update-list-head">
        <div className="contributor-filter-pills" aria-live="polite">
          {selectedSources.map((source) => (
            <button
              key={source}
              className="contributor-filter-pill"
              type="button"
              onClick={() =>
                setSelectedSources((current) => current.filter((item) => item !== source))
              }
            >
              <span aria-hidden="true" />
              {sourceOptions.find((option) => option.value === source)?.label ?? source}
              <strong aria-hidden="true">×</strong>
            </button>
          ))}
          {dateFilter !== "cycle" ? (
            <button
              className="contributor-filter-pill date"
              type="button"
              onClick={() => setDateFilter("cycle")}
            >
              <span aria-hidden="true" />
              {dateFilter === "7" ? "Last 7 days" : "Last 30 days"}
              <strong aria-hidden="true">×</strong>
            </button>
          ) : null}
        </div>

        {status === "pending" ? (
          <div className="contributor-update-actions">
            <div className={`contributor-filter${filterOpen ? " open" : ""}`} ref={filterRef}>
              <button
                className="contributor-filter-trigger"
                type="button"
                onClick={() => setFilterOpen((current) => !current)}
                aria-expanded={filterOpen}
              >
                <FilterIcon />
                Filter
              </button>
              <div className="contributor-filter-menu">
                <div className="contributor-filter-title">Source</div>
                <div className="contributor-filter-source-list">
                  {sourceOptions.length ? (
                    sourceOptions.map((option) => (
                      <label className="contributor-filter-option" key={option.value}>
                        <input
                          type="checkbox"
                          checked={selectedSources.includes(option.value)}
                          onChange={(event) =>
                            setSelectedSources((current) =>
                              event.target.checked
                                ? [...current, option.value]
                                : current.filter((item) => item !== option.value),
                            )
                          }
                        />
                        <span className="contributor-filter-box" aria-hidden="true" />
                        <span>{option.label}</span>
                      </label>
                    ))
                  ) : (
                    <p className="contributor-filter-empty">No sources yet</p>
                  )}
                </div>
                <div className="contributor-filter-divider" />
                <div className="contributor-filter-title">Date added</div>
                {[
                  ["cycle", "This cycle"],
                  ["7", "Last 7 days"],
                  ["30", "Last 30 days"],
                ].map(([value, label]) => (
                  <label className="contributor-filter-option" key={value}>
                    <input
                      type="radio"
                      name="contributor-date-filter"
                      checked={dateFilter === value}
                      onChange={() => setDateFilter(value as DateFilter)}
                    />
                    <span className="contributor-filter-ring" aria-hidden="true" />
                    <span>{label}</span>
                  </label>
                ))}
                <div className="contributor-filter-actions">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedSources([]);
                      setDateFilter("cycle");
                    }}
                  >
                    Clear all
                  </button>
                  <button type="button" onClick={() => setFilterOpen(false)}>
                    Apply
                  </button>
                </div>
              </div>
            </div>
            <button
              type="button"
              disabled={!filteredUpdates.length || Boolean(busyUpdateId)}
              onClick={() => handleBulkAction("dismiss")}
            >
              Dismiss all
            </button>
            <button
              type="button"
              disabled={!filteredUpdates.length || Boolean(busyUpdateId)}
              onClick={() => handleBulkAction("approve")}
            >
              Approve all
            </button>
          </div>
        ) : null}
      </div>

      {error ? <p className="workspace-error inline-error">{error}</p> : null}

      <div className="contributor-update-list">
        {loading ? <div className="contributor-update-empty">Loading updates</div> : null}
        {!loading && !filteredUpdates.length ? (
          <div className="contributor-update-empty">{emptyLabel}</div>
        ) : null}
        {!loading
          ? filteredUpdates.map((update) => (
              <UpdateRow
                key={update.update_id}
                busy={busyUpdateId === update.update_id}
                editing={editing?.updateId === update.update_id ? editing : null}
                onApprove={() => handleApprove(update.update_id)}
                onDismiss={() => handleDismiss(update.update_id)}
                onEdit={() => {
                  setOpenSourceUpdateId(null);
                  setEditing({
                    updateId: update.update_id,
                    title: update.title,
                    summary: update.summary,
                  });
                }}
                onEditChange={(summary) =>
                  editing?.updateId === update.update_id
                    ? setEditing({ ...editing, summary })
                    : undefined
                }
                onEditCancel={() => setEditing(null)}
                onEditSave={handleEditSave}
                onSourceToggle={() =>
                  setOpenSourceUpdateId((current) =>
                    current === update.update_id ? null : update.update_id,
                  )
                }
                onSourceClose={() => setOpenSourceUpdateId(null)}
                sourceOpen={openSourceUpdateId === update.update_id}
                status={status}
                update={update}
              />
            ))
          : null}
      </div>
    </section>
  );
}

function UpdateRow({
  busy,
  editing,
  onApprove,
  onDismiss,
  onEdit,
  onEditCancel,
  onEditChange,
  onEditSave,
  onSourceClose,
  onSourceToggle,
  sourceOpen,
  status,
  update,
}: {
  busy: boolean;
  editing: EditState | null;
  onApprove: () => void;
  onDismiss: () => void;
  onEdit: () => void;
  onEditCancel: () => void;
  onEditChange: (summary: string) => void;
  onEditSave: () => void;
  onSourceClose: () => void;
  onSourceToggle: () => void;
  sourceOpen: boolean;
  status: "pending" | "approved";
  update: PartnerUpdate;
}) {
  function handleRowClick(event: MouseEvent<HTMLDivElement>) {
    if (editing || isInteractiveRowTarget(event.target)) {
      return;
    }
    if (!canRevealSource(update)) {
      onSourceClose();
      return;
    }
    onSourceToggle();
  }

  const canReveal = canRevealSource(update);
  return (
    <div
      className={`contributor-update-row ${status}${editing ? " editing" : ""}${sourceOpen ? " source-open" : ""}`}
      onClick={handleRowClick}
    >
      {status === "pending" ? (
        <input className="contributor-update-checkbox" type="checkbox" aria-label="Select update" />
      ) : null}
      <SourceChip open={sourceOpen} update={update} onToggle={canReveal ? onSourceToggle : undefined} />
      {editing ? (
        <RichTextEditor updateId={update.update_id} value={editing.summary} onChange={onEditChange} />
      ) : (
        <div className="contributor-update-summary">
          <div
            className="contributor-update-summary-copy"
            dangerouslySetInnerHTML={{ __html: update.summary || escapeHtml(update.title) }}
          />
          {canReveal ? <SourceMeta open={sourceOpen} update={update} /> : null}
        </div>
      )}
      {status === "pending" ? (
        editing ? (
          <div className="contributor-row-actions">
            <button className="approve" type="button" disabled={busy} onClick={onEditSave}>
              Save
            </button>
            <button type="button" disabled={busy} onClick={onEditCancel}>
              Cancel
            </button>
          </div>
        ) : (
          <div className="contributor-row-actions">
            <button className="approve" type="button" disabled={busy} onClick={onApprove}>
              Approve
            </button>
            <button type="button" disabled={busy} onClick={onEdit}>
              Edit
            </button>
            <button className="dismiss" type="button" disabled={busy} onClick={onDismiss}>
              Dismiss
            </button>
          </div>
        )
      ) : (
        <div className="contributor-approved-meta">
          <strong>{formatDate(update.approved_at)}</strong>
        </div>
      )}
    </div>
  );
}

function RichTextEditor({
  onChange,
  updateId,
  value,
}: {
  onChange: (summary: string) => void;
  updateId: string;
  value: string;
}) {
  const editorRef = useRef<HTMLDivElement | null>(null);
  const selectedRangeRef = useRef<Range | null>(null);
  const targetAnchorRef = useRef<HTMLAnchorElement | null>(null);
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkText, setLinkText] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);

  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.innerHTML = value;
      rememberSelection();
    }
  }, [updateId]);

  function syncValue() {
    onChange(editorRef.current?.innerHTML ?? "");
  }

  function rememberSelection() {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection?.rangeCount) {
      return;
    }
    const range = selection.getRangeAt(0);
    if (containsSelectionNode(editor, range.startContainer) && containsSelectionNode(editor, range.endContainer)) {
      selectedRangeRef.current = range.cloneRange();
    }
  }

  function restoreSelectionOrEnd() {
    const editor = editorRef.current;
    if (!editor) {
      return;
    }
    editor.focus();
    const selection = window.getSelection();
    if (!selection) {
      return;
    }
    selection.removeAllRanges();
    if (selectedRangeRef.current) {
      selection.addRange(selectedRangeRef.current);
      return;
    }
    const range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
    selection.addRange(range);
  }

  function applyCommand(command: "bold" | "italic" | "underline" | "insertOrderedList" | "insertUnorderedList") {
    restoreSelectionOrEnd();
    document.execCommand(command, false);
    syncValue();
    rememberSelection();
    editorRef.current?.focus();
  }

  function openLinkEditor(anchor?: HTMLAnchorElement) {
    const editor = editorRef.current;
    if (!editor) {
      return;
    }
    if (anchor) {
      targetAnchorRef.current = anchor;
      selectedRangeRef.current = null;
      setLinkText(anchor.textContent ?? "");
      setLinkUrl(anchor.getAttribute("href") ?? "");
      setLinkError(null);
      setLinkOpen(true);
      return;
    }

    const range = selectedRangeRef.current;
    if (!range || range.collapsed) {
      editor.focus();
      setLinkError("Select text in the update first, then attach a link.");
      setLinkText("");
      setLinkUrl("");
      targetAnchorRef.current = null;
      setLinkOpen(true);
      return;
    }

    targetAnchorRef.current = null;
    setLinkText(range.toString());
    setLinkUrl("");
    setLinkError(null);
    setLinkOpen(true);
  }

  function applyLink() {
    const editor = editorRef.current;
    const text = linkText.trim();
    const href = normalizeEditorHref(linkUrl);
    if (!editor || !text || !href) {
      setLinkError(!text ? "Link text is required." : "Enter a valid http, https, or mailto link.");
      return;
    }

    const anchor = targetAnchorRef.current;
    if (anchor) {
      anchor.textContent = text;
      anchor.setAttribute("href", href);
      anchor.setAttribute("target", "_blank");
      anchor.setAttribute("rel", "noopener noreferrer");
    } else {
      restoreSelectionOrEnd();
      const selection = window.getSelection();
      const range = selectedRangeRef.current;
      if (!selection || !range || range.collapsed) {
        setLinkError("Select text in the update first, then attach a link.");
        return;
      }
      const nextAnchor = document.createElement("a");
      nextAnchor.href = href;
      nextAnchor.target = "_blank";
      nextAnchor.rel = "noopener noreferrer";
      nextAnchor.textContent = text;
      range.deleteContents();
      range.insertNode(nextAnchor);
      range.setStartAfter(nextAnchor);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    setLinkOpen(false);
    setLinkError(null);
    syncValue();
    rememberSelection();
    editor.focus();
  }

  function removeLink() {
    const anchor = targetAnchorRef.current;
    if (!anchor) {
      return;
    }
    anchor.replaceWith(document.createTextNode(anchor.textContent ?? ""));
    targetAnchorRef.current = null;
    setLinkOpen(false);
    syncValue();
    rememberSelection();
    editorRef.current?.focus();
  }

  return (
    <div className={`contributor-row-edit${linkOpen ? " link-open" : ""}`}>
      <div className="contributor-row-rte-bar" aria-label="Text formatting toolbar">
        <ToolbarButton label="Bold" onClick={() => applyCommand("bold")}>
          B
        </ToolbarButton>
        <ToolbarButton className="italic" label="Italic" onClick={() => applyCommand("italic")}>
          I
        </ToolbarButton>
        <ToolbarButton className="underline" label="Underline" onClick={() => applyCommand("underline")}>
          U
        </ToolbarButton>
        <span aria-hidden="true" />
        <ToolbarButton label="Numbered list" onClick={() => applyCommand("insertOrderedList")}>
          1.
        </ToolbarButton>
        <ToolbarButton label="Bulleted list" onClick={() => applyCommand("insertUnorderedList")}>
          •
        </ToolbarButton>
        <ToolbarButton label="Attach link" onClick={() => openLinkEditor()}>
          Link
        </ToolbarButton>
      </div>
      {linkOpen ? (
        <div className="contributor-row-link-popover" role="dialog" aria-label="Attach link">
          <label>
            <span>Text</span>
            <input value={linkText} onChange={(event) => setLinkText(event.target.value)} />
          </label>
          <label>
            <span>Link</span>
            <input
              value={linkUrl}
              onChange={(event) => setLinkUrl(event.target.value)}
              placeholder="https://example.com"
            />
          </label>
          {linkError ? <p>{linkError}</p> : null}
          <div className="contributor-row-link-actions">
            {targetAnchorRef.current ? (
              <button type="button" onClick={removeLink}>
                Remove
              </button>
            ) : null}
            <button type="button" onClick={() => setLinkOpen(false)}>
              Cancel
            </button>
            <button type="button" onClick={applyLink}>
              Apply
            </button>
          </div>
        </div>
      ) : null}
      <div
        ref={editorRef}
        className="contributor-row-edit-area"
        contentEditable
        role="textbox"
        aria-label="Edit update summary"
        aria-multiline="true"
        suppressContentEditableWarning
        onBlur={rememberSelection}
        onClick={(event) => {
          const anchor = (event.target as HTMLElement).closest("a");
          if (anchor && editorRef.current?.contains(anchor)) {
            event.preventDefault();
            openLinkEditor(anchor as HTMLAnchorElement);
            return;
          }
          rememberSelection();
        }}
        onInput={() => {
          syncValue();
          rememberSelection();
        }}
        onKeyUp={rememberSelection}
        onMouseUp={rememberSelection}
        onPaste={(event) => {
          event.preventDefault();
          const text = event.clipboardData.getData("text/plain");
          restoreSelectionOrEnd();
          document.execCommand("insertText", false, text);
          syncValue();
          rememberSelection();
        }}
      />
    </div>
  );
}

function ToolbarButton({
  children,
  className,
  label,
  onClick,
}: {
  children: ReactNode;
  className?: string;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={className}
      type="button"
      aria-label={label}
      title={label}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function SourceChip({
  onToggle,
  open,
  update,
}: {
  onToggle?: () => void;
  open: boolean;
  update: PartnerUpdate;
}) {
  const label = sourceLabel(update);
  const className = `contributor-source-chip source-${sourceKey(update)}${onToggle ? "" : " static"}`;
  if (!onToggle) {
    return <span className={className}>{label}</span>;
  }
  return (
    <button className={className} type="button" onClick={onToggle} aria-expanded={open}>
      {label}
    </button>
  );
}

function SourceMeta({ open, update }: { open: boolean; update: PartnerUpdate }) {
  return (
    <div className={`contributor-update-source-meta${open ? " open" : ""}`}>
      <div>
        <strong>Source:</strong> {sourceDetailLabel(update)}
      </div>
      {update.source_url ? (
        <a href={update.source_url} target="_blank" rel="noreferrer">
          {update.source_url}
        </a>
      ) : null}
    </div>
  );
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Not yet";
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function sourceKey(update: PartnerUpdate): SourceFilterKey {
  if (["file", "sharepoint", "confluence"].includes(update.source_type)) {
    return "files";
  }
  if (update.source_type === "email") {
    return "email";
  }
  if (update.source_type === "github") {
    return "github";
  }
  if (update.source_type === "jira") {
    return "jira";
  }
  if (update.source_type === "slack") {
    return "slack";
  }
  return "manual";
}

function sourceLabel(update: PartnerUpdate): string {
  return SOURCE_FILTERS.find((option) => option.value === sourceKey(update))?.label ?? "Manual";
}

function sourceDetailLabel(update: PartnerUpdate): string {
  if (update.source_label) {
    return update.source_label;
  }

  return sourceLabel(update);
}

function canRevealSource(update: PartnerUpdate): boolean {
  return ["github", "jira", "files"].includes(sourceKey(update));
}

function dateMatchesFilter(value: string, dateFilter: DateFilter): boolean {
  if (dateFilter === "cycle") {
    return true;
  }

  const created = new Date(value).getTime();
  const days = dateFilter === "7" ? 7 : 30;
  return created >= Date.now() - days * 24 * 60 * 60 * 1000;
}

function FilterIcon() {
  return (
    <svg className="contributor-filter-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path
        d="M4 5h16l-6.2 7.1v4.5l-3.6 2v-6.5L4 5Z"
        fill="currentColor"
      />
    </svg>
  );
}

function containsSelectionNode(editor: HTMLElement, node: Node) {
  return node === editor || editor.contains(node);
}

function isInteractiveRowTarget(target: EventTarget) {
  return (
    target instanceof Element &&
    Boolean(target.closest("button, a, input, textarea, select, [contenteditable='true']"))
  );
}

function normalizeEditorHref(value: string): string | null {
  const cleaned = value.trim();
  if (!cleaned) {
    return null;
  }

  try {
    const parsed = new URL(cleaned);
    return ["http:", "https:", "mailto:"].includes(parsed.protocol) ? cleaned : null;
  } catch {
    if (/^[\w.+-]+@[\w.-]+\.[a-z]{2,}$/i.test(cleaned)) {
      return `mailto:${cleaned}`;
    }
    return null;
  }
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
