"use client";

import {
  FormEvent,
  type DragEvent,
  type MouseEvent,
  type ClipboardEvent,
  type KeyboardEvent,
  useMemo,
  useRef,
  useState,
  useEffect,
} from "react";

import {
  PartnerUpdate,
  createContributorManualUpdate,
} from "@/features/contributor/contributor-updates-api";

const MAX_SUMMARY_LENGTH = 500;

type ManualUpdateFormProps = {
  partnerId: string;
  partnerName: string;
  cycle: string;
  cycleLabel: string;
  onCancel: () => void;
  onCreated: (update: PartnerUpdate) => void;
};

type DraftAttachment = {
  id: string;
  name: string;
  size: number;
  url: string;
  objectUrl: string;
};

type SavedPreview = {
  id: string;
  summary: string;
  attachments: DraftAttachment[];
};

type ToolbarCommand = "bold" | "italic" | "underline" | "insertOrderedList" | "insertUnorderedList";

type ActiveToolbarState = {
  bold: boolean;
  italic: boolean;
  underline: boolean;
  orderedList: boolean;
  unorderedList: boolean;
};

type LinkDialogState = {
  text: string;
  url: string;
  error: string | null;
};

export function ManualUpdateForm({
  partnerId,
  partnerName,
  cycle,
  cycleLabel,
  onCancel,
  onCreated,
}: ManualUpdateFormProps) {
  const editorRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const selectedRangeRef = useRef<Range | null>(null);
  const objectUrlsRef = useRef<Set<string>>(new Set());
  const [summaryHtml, setSummaryHtml] = useState("");
  const [summaryText, setSummaryText] = useState("");
  const [attachments, setAttachments] = useState<DraftAttachment[]>([]);
  const [savedPreviews, setSavedPreviews] = useState<SavedPreview[]>([]);
  const [activeToolbar, setActiveToolbar] = useState<ActiveToolbarState>({
    bold: false,
    italic: false,
    underline: false,
    orderedList: false,
    unorderedList: false,
  });
  const [linkDialog, setLinkDialog] = useState<LinkDialogState | null>(null);
  const [dragging, setDragging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const remainingCharacters = MAX_SUMMARY_LENGTH - summaryText.length;

  useEffect(() => {
    return () => {
      objectUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      objectUrlsRef.current.clear();
    };
  }, []);

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timer = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const cycleContext = useMemo(() => `${partnerName} · ${cycleLabel}`, [cycleLabel, partnerName]);

  function syncEditorState() {
    const editor = editorRef.current;
    if (!editor) {
      return;
    }
    setSummaryHtml(editor.innerHTML.trim());
    setSummaryText(editor.innerText.replace(/\n{3,}/g, "\n\n"));
    rememberSelectedRange();
    updateActiveToolbar();
    if (editor.classList.contains("invalid") && editor.innerText.trim()) {
      editor.classList.remove("invalid");
    }
  }

  function rememberSelectedRange() {
    const range = getSelectedEditorRange();
    if (range) {
      selectedRangeRef.current = range;
    }
  }

  function updateActiveToolbar() {
    setActiveToolbar({
      bold: document.queryCommandState("bold"),
      italic: document.queryCommandState("italic"),
      underline: document.queryCommandState("underline"),
      orderedList: document.queryCommandState("insertOrderedList"),
      unorderedList: document.queryCommandState("insertUnorderedList"),
    });
  }

  function applyCommand(command: ToolbarCommand) {
    const selectedRange = getSelectedEditorRange() ?? selectedRangeRef.current;
    const isListCommand = command === "insertOrderedList" || command === "insertUnorderedList";
    if (isListCommand) {
      if (selectedRange && !selectedRange.collapsed) {
        restoreEditorRange(selectedRange);
      } else {
        editorRef.current?.focus();
      }
      setError(null);
      document.execCommand(command, false);
      syncEditorState();
      return;
    }

    if (!selectedRange || selectedRange.collapsed) {
      setError("Select text in the update summary before applying formatting.");
      editorRef.current?.focus();
      return;
    }

    restoreEditorRange(selectedRange);
    setError(null);
    document.execCommand(command, false);
    syncEditorState();
  }

  function applyLink() {
    const selectedRange = getSelectedEditorRange() ?? selectedRangeRef.current;
    if (!selectedRange || selectedRange.collapsed) {
      setError("Select text in the update summary before attaching a link.");
      editorRef.current?.focus();
      return;
    }

    setError(null);
    selectedRangeRef.current = selectedRange;
    setLinkDialog({
      text: selectedRange.toString(),
      url: "",
      error: null,
    });
  }

  function applyLinkDialog() {
    if (!linkDialog || !selectedRangeRef.current) {
      return;
    }

    const href = normalizeHref(linkDialog.url);
    const text = linkDialog.text.trim();
    if (!text || !href) {
      setLinkDialog({
        ...linkDialog,
        error: !text ? "Link text cannot be empty." : "Enter a valid URL or file path.",
      });
      return;
    }

    restoreEditorRange(selectedRangeRef.current);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    anchor.textContent = text;
    selectedRangeRef.current.deleteContents();
    selectedRangeRef.current.insertNode(anchor);
    selectedRangeRef.current.setStartAfter(anchor);
    selectedRangeRef.current.collapse(true);
    restoreEditorRange(selectedRangeRef.current);
    setLinkDialog(null);
    setError(null);
    syncEditorState();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!summaryText.trim()) {
      editorRef.current?.classList.add("invalid");
      editorRef.current?.focus();
      setError("Update summary is required.");
      return;
    }

    if (remainingCharacters < 0) {
      editorRef.current?.focus();
      setError(`Update summary must be ${MAX_SUMMARY_LENGTH} characters or fewer.`);
      return;
    }

    setSaving(true);
    try {
      const update = await createContributorManualUpdate(partnerId, cycle, {
        title: deriveUpdateTitle(summaryText),
        summary: summaryHtml || escapeHtml(summaryText),
      });
      const savedAttachments = attachments;
      setSavedPreviews((current) => [
        { id: update.update_id, summary: update.summary, attachments: savedAttachments },
        ...current,
      ]);
      clearDraft();
      setToast("Update staged. You can add another one.");
      onCreated(update);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to save update.");
    } finally {
      setSaving(false);
    }
  }

  function clearDraft() {
    if (editorRef.current) {
      editorRef.current.innerHTML = "";
      editorRef.current.classList.remove("invalid");
    }
    setSummaryHtml("");
    setSummaryText("");
    setAttachments([]);
    selectedRangeRef.current = null;
    setLinkDialog(null);
    updateActiveToolbar();
  }

  function addAttachmentFiles(files: FileList | File[]) {
    const nextAttachments = Array.from(files).map((file) => {
      const id = `${file.name}-${file.size}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const objectUrl = URL.createObjectURL(file);
      objectUrlsRef.current.add(objectUrl);
      return {
        id,
        name: file.name,
        size: file.size,
        url: `${window.location.origin}${window.location.pathname}#${encodeURIComponent(id)}`,
        objectUrl,
      };
    });

    if (nextAttachments.length) {
      setAttachments((current) => [...current, ...nextAttachments]);
      setToast(`${nextAttachments.length} attachment${nextAttachments.length === 1 ? "" : "s"} staged.`);
    }
  }

  function handleFilesSelected() {
    if (fileInputRef.current?.files) {
      addAttachmentFiles(fileInputRef.current.files);
      fileInputRef.current.value = "";
    }
  }

  function handleDrag(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setDragging(event.type === "dragenter" || event.type === "dragover");
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setDragging(false);
    if (event.dataTransfer.files.length) {
      addAttachmentFiles(event.dataTransfer.files);
    }
  }

  function removeAttachment(event: MouseEvent<HTMLButtonElement>, attachmentId: string) {
    event.preventDefault();
    setAttachments((current) => {
      const attachment = current.find((item) => item.id === attachmentId);
      if (attachment) {
        URL.revokeObjectURL(attachment.objectUrl);
        objectUrlsRef.current.delete(attachment.objectUrl);
      }
      return current.filter((item) => item.id !== attachmentId);
    });
  }

  async function copyAttachmentUrl(attachment: DraftAttachment) {
    try {
      await copyText(attachment.url);
      setToast("Attachment link copied to clipboard.");
    } catch {
      setError("Unable to copy attachment link.");
    }
  }

  function getSelectedEditorRange(): Range | null {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection || selection.rangeCount === 0 || selection.isCollapsed) {
      return null;
    }

    const range = selection.getRangeAt(0);
    const anchorNode = selection.anchorNode;
    const focusNode = selection.focusNode;
    if (
      !anchorNode ||
      !focusNode ||
      (!editor.contains(anchorNode) && anchorNode !== editor) ||
      (!editor.contains(focusNode) && focusNode !== editor)
    ) {
      return null;
    }

    return range.cloneRange();
  }

  function restoreEditorRange(range: Range) {
    const selection = window.getSelection();
    if (!selection) {
      return;
    }
    editorRef.current?.focus();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function insertAnchorAtSelection(label: string, href: string) {
    const selectedRange = getSelectedEditorRange();
    const editor = editorRef.current;
    if (!editor) {
      return;
    }

    if (selectedRange) {
      restoreEditorRange(selectedRange);
    } else {
      editor.focus();
    }

    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    anchor.textContent = label;

    const selection = window.getSelection();
    const range = selection?.rangeCount ? selection.getRangeAt(0) : document.createRange();
    if (!selection?.rangeCount) {
      range.selectNodeContents(editor);
      range.collapse(false);
    }
    range.deleteContents();
    range.insertNode(anchor);
    range.setStartAfter(anchor);
    range.collapse(true);
    restoreEditorRange(range);
  }

  function handleEditorPaste(event: ClipboardEvent<HTMLDivElement>) {
    const pastedText = event.clipboardData.getData("text/plain").trim();
    const href = normalizeHref(pastedText);
    if (!href) {
      return;
    }

    event.preventDefault();
    insertAnchorAtSelection(linkLabelFromHref(href), href);
    syncEditorState();
  }

  function handleLinkDialogKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    applyLinkDialog();
  }

  return (
    <form className="add-update-screen" onSubmit={handleSubmit}>
      {toast ? (
        <div className="add-update-toast" role="status" aria-live="polite">
          {toast}
        </div>
      ) : null}

      <div className="add-update-head">
        <button className="add-update-back" type="button" onClick={onCancel}>
          ‹ {partnerName}
        </button>
        <span className="add-update-head-divider" aria-hidden="true" />
        <div className="add-update-title-block">
          <h3>Add update</h3>
          <p>{cycleContext}</p>
        </div>
        <div className="add-update-cycle" aria-label={`Selected period ${cycleLabel}`}>
          <span aria-hidden="true">‹</span>
          <strong>{cycleLabel}</strong>
          <span aria-hidden="true">›</span>
        </div>
        <button className="add-update-cancel" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="add-update-save" type="submit" disabled={saving}>
          {saving ? "Saving..." : "Save update"}
        </button>
      </div>

      <section className="add-update-workspace" aria-label="Add update workspace">
        <aside className="add-update-source-panel" aria-label="Update source">
          <div className="add-update-source-grid">
            <button className="add-update-source-card active" type="button" aria-pressed="true">
              <span className="add-update-source-icon" aria-hidden="true">
                <ManualIcon />
              </span>
              <strong>Manual</strong>
              <span>Type directly</span>
            </button>
            <button
              className="add-update-source-card disabled"
              type="button"
              disabled
              aria-disabled="true"
            >
              <span className="add-update-source-icon" aria-hidden="true">
                <FilesIcon />
              </span>
              <strong>Files</strong>
              <span>Upload & prompt</span>
            </button>
          </div>
        </aside>

        <div className="add-update-panel">
          <div className="add-update-editor-field">
            <label htmlFor="manual-update-summary-editor">Update summary *</label>
            <div className="add-update-rte-toolbar" aria-label="Text formatting toolbar">
              <button
                className={activeToolbar.bold ? "active" : ""}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => applyCommand("bold")}
                aria-label="Bold"
                title="Bold"
              >
                B
              </button>
              <button
                className={`italic${activeToolbar.italic ? " active" : ""}`}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => applyCommand("italic")}
                aria-label="Italic"
                title="Italic"
              >
                I
              </button>
              <button
                className={`underline${activeToolbar.underline ? " active" : ""}`}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => applyCommand("underline")}
                aria-label="Underline"
                title="Underline"
              >
                U
              </button>
              <span className="add-update-toolbar-separator" aria-hidden="true" />
              <button
                className={activeToolbar.orderedList ? "active" : ""}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => applyCommand("insertOrderedList")}
                aria-label="Numbered list"
                title="Numbered list"
              >
                1.
              </button>
              <button
                className={activeToolbar.unorderedList ? "active" : ""}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => applyCommand("insertUnorderedList")}
                aria-label="Bulleted list"
                title="Bulleted list"
              >
                <BulletListIcon />
              </button>
              <button
                className={linkDialog ? "active" : ""}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={applyLink}
                aria-label="Attach link"
                title="Attach link"
              >
                <LinkIcon />
              </button>
              <span className={`add-update-character-count${remainingCharacters < 0 ? " over" : ""}`}>
                {summaryText.length} / {MAX_SUMMARY_LENGTH}
              </span>
            </div>
            <div
              id="manual-update-summary-editor"
              ref={editorRef}
              className="add-update-summary-editor"
              contentEditable
              role="textbox"
              aria-multiline="true"
              aria-label="Update summary"
              data-placeholder="Describe what happened, what was agreed, or what needs action..."
              onInput={syncEditorState}
              onBlur={syncEditorState}
              onKeyUp={syncEditorState}
              onMouseUp={syncEditorState}
              onPaste={handleEditorPaste}
              suppressContentEditableWarning
            />
            {linkDialog ? (
              <div className="add-update-link-popover" role="dialog" aria-label="Add hyperlink">
                <div className="add-update-link-title">Add hyperlink</div>
                <label>
                  <span>Link text</span>
                  <input
                    className="active"
                    value={linkDialog.text}
                    onChange={(event) =>
                      setLinkDialog({ ...linkDialog, text: event.target.value, error: null })
                    }
                    onKeyDown={handleLinkDialogKeyDown}
                    maxLength={200}
                  />
                </label>
                <label>
                  <span>URL or file path</span>
                  <input
                    value={linkDialog.url}
                    onChange={(event) =>
                      setLinkDialog({ ...linkDialog, url: event.target.value, error: null })
                    }
                    onKeyDown={handleLinkDialogKeyDown}
                    maxLength={2000}
                    placeholder="https:// or paste a file URL..."
                    autoFocus
                  />
                </label>
                {linkDialog.error ? <p>{linkDialog.error}</p> : null}
                <div className="add-update-link-actions">
                  <button type="button" onClick={() => setLinkDialog(null)}>
                    Cancel
                  </button>
                  <button className="primary" type="button" onClick={applyLinkDialog}>
                    Apply link
                  </button>
                </div>
              </div>
            ) : null}
          </div>

          {error ? <p className="workspace-error inline-error add-update-error">{error}</p> : null}

          <div className="add-update-attachments">
            <div className="add-update-attachments-head">
              <strong>Attachments</strong>
              <button type="button" onClick={() => fileInputRef.current?.click()}>
                + Browse files
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              accept=".docx,.pdf,.pptx,.txt,.csv,.json,.eml,.vtt,.srt,.png,.jpg,.jpeg,.webp"
              onChange={handleFilesSelected}
            />
            <div
              className={`add-update-dropzone${dragging ? " dragging" : ""}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
            >
              Drag files here or browse to attach
            </div>
            {attachments.length ? (
              <div className="add-update-attachment-list" aria-live="polite">
                {attachments.map((attachment) => (
                  <div className="add-update-attachment-row" key={attachment.id}>
                    <span>
                      <strong>{attachment.name}</strong>
                      <small>Ready · {formatBytes(attachment.size)}</small>
                    </span>
                    <span className="add-update-attachment-actions">
                      <button type="button" onClick={() => copyAttachmentUrl(attachment)}>
                        Copy link
                      </button>
                      <button type="button" onClick={(event) => removeAttachment(event, attachment.id)}>
                        ×
                      </button>
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <section className="add-update-preview" aria-label="Saved manual update previews">
            <span>Preview</span>
            <div className="add-update-preview-list" aria-live="polite">
              {savedPreviews.length ? (
                savedPreviews.map((preview) => (
                  <article className="add-update-preview-card" key={preview.id}>
                    <div className="add-update-preview-top">
                      <strong>Manual</strong>
                      <small>Just now</small>
                    </div>
                    <div
                      className="add-update-preview-summary"
                      dangerouslySetInnerHTML={{ __html: preview.summary }}
                    />
                    <div className="add-update-preview-footer">
                      <div className="add-update-preview-links">
                        {preview.attachments.map((attachment) => (
                          <button
                            key={attachment.id}
                            type="button"
                            onClick={() => copyAttachmentUrl(attachment)}
                          >
                            <LinkIcon />
                            <span>{attachment.name}</span>
                          </button>
                        ))}
                      </div>
                      <em>Staged for review</em>
                    </div>
                  </article>
                ))
              ) : (
                <div className="add-update-preview-empty">
                  Saved manual updates will appear here so you can review what you have staged in this session.
                </div>
              )}
            </div>
          </section>
        </div>
      </section>
    </form>
  );
}

function deriveUpdateTitle(summary: string): string {
  const firstLine = summary
    .replace(/\s+/g, " ")
    .trim()
    .split(/(?<=[.!?])\s/)[0]
    ?.trim();
  return (firstLine || "Manual update").slice(0, 120);
}

function normalizeHref(value: string): string {
  const cleaned = value.trim();
  if (!cleaned) {
    return "";
  }
  if (/^(https?:\/\/|mailto:|\/|#)/i.test(cleaned)) {
    return cleaned;
  }
  if (/^[^\s@]+\.[^\s@]+/.test(cleaned)) {
    return `https://${cleaned}`;
  }
  return "";
}

function linkLabelFromHref(href: string): string {
  const clean = href.split("?")[0].split("#")[0];
  const fallback = href.startsWith("#") ? href.slice(1) : href;
  const lastPart = clean.split("/").filter(Boolean).pop() ?? fallback;
  try {
    return decodeURIComponent(lastPart) || href;
  } catch {
    return lastPart || href;
  }
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character] ?? character;
  });
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

function ManualIcon() {
  return (
    <svg viewBox="0 0 26 26" fill="none" focusable="false">
      <path
        d="M11.5 3.5H3.3A2.3 2.3 0 0 0 1 5.8v16.3a2.3 2.3 0 0 0 2.3 2.4h16.4a2.3 2.3 0 0 0 2.3-2.4V14"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M20.3 1.7a2.5 2.5 0 0 1 3.5 3.5L12.7 16.3 8 17.5l1.2-4.7L20.3 1.7Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function FilesIcon() {
  return (
    <svg viewBox="0 0 25 27" fill="none" focusable="false">
      <path
        d="M23.7 12.3 13 23a7 7 0 0 1-9.9-9.9L13.8 2.4a4.7 4.7 0 0 1 6.6 6.6L9.6 19.7a2.3 2.3 0 1 1-3.3-3.3l9.9-9.9"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path
        d="M10.6 13.4a2 2 0 0 0 2.8 0L17 9.9a3 3 0 0 0-4.2-4.3l-1.5 1.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M13.4 10.6a2 2 0 0 0-2.8 0L7 14.1a3 3 0 0 0 4.2 4.3l1.5-1.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function BulletListIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path
        d="M8 7h11M8 12h11M8 17h11"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M4.5 7h.01M4.5 12h.01M4.5 17h.01"
        stroke="currentColor"
        strokeWidth="3.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
