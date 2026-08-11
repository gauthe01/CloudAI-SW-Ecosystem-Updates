"use client";

import { type FormEvent, type TextareaHTMLAttributes, useEffect, useRef, useState } from "react";

import { GlobalLoader } from "@/components/foundation/GlobalLoader";
import {
  PartnerHealthStatus,
  PartnerMetadata,
  PartnerMetadataPayload,
  PartnerMetadataRisk,
  PartnerResourceLink,
  getContributorPartnerMetadata,
  saveContributorPartnerMetadata,
} from "@/features/contributor/contributor-metadata-api";

type ContributorPartnerMetadataPanelProps = {
  partnerId: string;
  cycle: string;
  cycleLabel: string;
};

type MetadataFormState = {
  status: PartnerHealthStatus | "";
  why_this_partner: string;
  business_priority: string;
  highlights_status: string;
  goals: string;
  execution_timeline: EditableTimelineRow[];
  risks: EditableRisk[];
  resources: EditableResource[];
};

type RequiredMetadataField =
  | "why_this_partner"
  | "business_priority"
  | "highlights_status"
  | "goals";

type MetadataToast = {
  message: string;
  tone: "success" | "error";
};

type EditableTimelineRow = {
  local_id: string;
  milestone: string;
  target_date: string;
};

type EditableRisk = Omit<PartnerMetadataRisk, "risk_id"> & {
  local_id: string;
  risk_id?: string | null;
};

type EditableResource = Omit<PartnerResourceLink, "resource_link_id"> & {
  local_id: string;
  resource_link_id?: string;
};

const statusOptions: { value: PartnerHealthStatus; label: string }[] = [
  { value: "green", label: "Green" },
  { value: "amber", label: "Amber" },
  { value: "red", label: "Red" },
];
const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function ContributorPartnerMetadataPanel({
  partnerId,
  cycle,
}: ContributorPartnerMetadataPanelProps) {
  const [form, setForm] = useState<MetadataFormState>(emptyForm());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [copying, setCopying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<MetadataToast | null>(null);
  const [missingRequiredFields, setMissingRequiredFields] = useState<RequiredMetadataField[]>([]);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    setToast(null);
    setMissingRequiredFields([]);

    getContributorPartnerMetadata(partnerId, cycle)
      .then((metadata) => {
        if (mounted) {
          setForm(metadataToForm(metadata));
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load metadata.");
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
  }, [partnerId, cycle]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setToast(null);

    const validationResult = validateRequiredMetadata(form);
    if (validationResult) {
      setMissingRequiredFields(validationResult.missingFields);
      setToast({ message: validationResult.message, tone: "error" });
      setSaving(false);
      return;
    }

    try {
      const savedMetadata = await saveContributorPartnerMetadata(
        partnerId,
        cycle,
        formToPayload(form),
      );
      setForm(metadataToForm(savedMetadata));
      setMissingRequiredFields([]);
      setToast({ message: "Metadata saved.", tone: "success" });
    } catch (error) {
      setToast({
        message: error instanceof Error ? error.message : "Unable to save metadata.",
        tone: "error",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleCopyFromPreviousMonth() {
    const previousCycle = previousMonthValue(cycle);
    setCopying(true);
    setError(null);
    setToast(null);

    try {
      const previousMetadata = await getContributorPartnerMetadata(partnerId, previousCycle);
      if (!previousMetadata.metadata_id) {
        setToast({
          message: `No metadata saved for ${formatMonthLabel(previousCycle)}.`,
          tone: "error",
        });
        return;
      }

      setForm(metadataToForm(previousMetadata));
      setMissingRequiredFields([]);
      setToast({
        message: `Copied metadata from ${formatMonthLabel(previousCycle)}. Review and save to apply it here.`,
        tone: "success",
      });
    } catch (error) {
      setToast({
        message:
          error instanceof Error
            ? error.message
            : `Unable to copy metadata from ${formatMonthLabel(previousCycle)}.`,
        tone: "error",
      });
    } finally {
      setCopying(false);
    }
  }

  useEffect(() => {
    if (!toast) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timeoutId);
  }, [toast]);

  function updateField(field: keyof MetadataFormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    if (isRequiredMetadataField(field) && hasRequiredText(value)) {
      setMissingRequiredFields((current) => current.filter((item) => item !== field));
    }
  }

  function updateRisk(localId: string, updates: Partial<EditableRisk>) {
    setForm((current) => ({
      ...current,
      risks: current.risks.map((risk) =>
        risk.local_id === localId ? { ...risk, ...updates } : risk,
      ),
    }));
  }

  function updateResource(localId: string, updates: Partial<EditableResource>) {
    setForm((current) => ({
      ...current,
      resources: current.resources.map((resource) =>
        resource.local_id === localId ? { ...resource, ...updates } : resource,
      ),
    }));
  }

  function updateTimeline(localId: string, updates: Partial<EditableTimelineRow>) {
    setForm((current) => ({
      ...current,
      execution_timeline: current.execution_timeline.map((row) =>
        row.local_id === localId ? { ...row, ...updates } : row,
      ),
    }));
  }

  function addTimelineRow() {
    setForm((current) => ({
      ...current,
      execution_timeline: [...current.execution_timeline, emptyTimelineRow()],
    }));
  }

  function removeTimelineRow(localId: string) {
    setForm((current) => ({
      ...current,
      execution_timeline:
        current.execution_timeline.length > 1
          ? current.execution_timeline.filter((row) => row.local_id !== localId)
          : [emptyTimelineRow()],
    }));
  }

  function updateListField(
    field: "business_priority" | "highlights_status" | "goals",
    index: number,
    value: string,
  ) {
    const rows = listFieldRows(form[field]);
    rows[index] = value;
    updateField(field, rows.join("\n"));
  }

  function addListFieldRow(field: "business_priority" | "highlights_status" | "goals") {
    updateField(field, [...listFieldRows(form[field]), ""].join("\n"));
  }

  function removeListFieldRow(
    field: "business_priority" | "highlights_status" | "goals",
    index: number,
  ) {
    const rows = listFieldRows(form[field]);
    const nextRows = rows.length > 1 ? rows.filter((_, rowIndex) => rowIndex !== index) : [""];
    updateField(field, nextRows.join("\n"));
  }

  function addRisk() {
    setForm((current) => ({ ...current, risks: [...current.risks, emptyRisk()] }));
  }

  function removeRisk(localId: string) {
    setForm((current) => ({
      ...current,
      risks: current.risks.length > 1 ? current.risks.filter((risk) => risk.local_id !== localId) : [emptyRisk()],
    }));
  }

  function addResource() {
    setForm((current) => ({ ...current, resources: [...current.resources, emptyResource()] }));
  }

  function removeResource(localId: string) {
    setForm((current) => ({
      ...current,
      resources: current.resources.filter((resource) => resource.local_id !== localId),
    }));
  }

  if (loading) {
    return (
      <GlobalLoader
        label="Loading partner metadata"
        detail="Fetching saved partner context for this cycle."
      />
    );
  }

  const isMissingRequiredField = (field: RequiredMetadataField) =>
    missingRequiredFields.includes(field);
  const previousCycle = previousMonthValue(cycle);

  return (
    <form className="metadata-form gold-metadata-form" onSubmit={handleSubmit}>
      {error ? <p className="workspace-error inline-error">{error}</p> : null}
      {toast ? (
        <div
          className={`metadata-save-toast ${toast.tone}`}
          role="status"
          aria-live="polite"
        >
          {toast.message}
        </div>
      ) : null}

      <div className="metadata-action-toolbar">
        <button
          className="metadata-copy-action"
          type="button"
          onClick={handleCopyFromPreviousMonth}
          disabled={copying || saving}
        >
          {copying ? "Copying" : `Copy from ${formatMonthLabel(previousCycle)}`}
        </button>
        <button className="metadata-save-action" type="submit" disabled={saving || copying}>
          {saving ? "Saving" : "Save Metadata"}
        </button>
      </div>

      <section className="metadata-card">
        <div className="metadata-card-head">
          <span>Partner Metadata</span>
        </div>
        <div className="metadata-card-body metadata-status-body">
          <div className="metadata-field">
            <div className="metadata-label">Status</div>
            <div className="metadata-status-options">
              {statusOptions.map((option) => (
                <label key={option.value} data-status={option.value}>
                  <input
                    type="radio"
                    name="metadata-status"
                    value={option.value}
                    checked={form.status === option.value}
                    onChange={() => updateField("status", option.value)}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section
        className={
          isMissingRequiredField("why_this_partner")
            ? "metadata-card metadata-required-card invalid"
            : "metadata-card metadata-required-card"
        }
      >
        <div className="metadata-card-head">
          <span>Why this partner</span>
          <span className="metadata-required-badge">Required</span>
        </div>
        <div className="metadata-card-body">
          <AutoGrowTextarea
            className={
              isMissingRequiredField("why_this_partner")
                ? "metadata-textarea metadata-textarea-large invalid"
                : "metadata-textarea metadata-textarea-large"
            }
            value={form.why_this_partner}
            onChange={(event) => updateField("why_this_partner", event.target.value)}
            maxLength={2000}
            aria-invalid={isMissingRequiredField("why_this_partner")}
          />
        </div>
      </section>

      <div className="metadata-grid">
        <MetadataListCard
          label="Business priority"
          required
          invalid={isMissingRequiredField("business_priority")}
          rows={listFieldRows(form.business_priority)}
          onAdd={() => addListFieldRow("business_priority")}
          onRemove={(index) => removeListFieldRow("business_priority", index)}
          onUpdate={(index, value) => updateListField("business_priority", index, value)}
        />
        <MetadataListCard
          label="Highlights / status"
          required
          invalid={isMissingRequiredField("highlights_status")}
          rows={listFieldRows(form.highlights_status)}
          onAdd={() => addListFieldRow("highlights_status")}
          onRemove={(index) => removeListFieldRow("highlights_status", index)}
          onUpdate={(index, value) => updateListField("highlights_status", index, value)}
        />
        <MetadataListCard
          label="Goals"
          required
          invalid={isMissingRequiredField("goals")}
          rows={listFieldRows(form.goals)}
          onAdd={() => addListFieldRow("goals")}
          onRemove={(index) => removeListFieldRow("goals", index)}
          onUpdate={(index, value) => updateListField("goals", index, value)}
        />
      </div>

      <section className="metadata-card">
        <div className="metadata-card-head">
          <span>Execution timeline</span>
          <button className="metadata-add-action" type="button" onClick={addTimelineRow}>
            + Add milestone
          </button>
        </div>
        <div className="metadata-card-body metadata-table-body">
          {form.execution_timeline.map((row) => (
            <div className="metadata-table-row metadata-timeline-row" key={row.local_id}>
              <AutoGrowTextarea
                value={row.milestone}
                onChange={(event) => updateTimeline(row.local_id, { milestone: event.target.value })}
                maxLength={300}
                placeholder="Milestone"
                rows={1}
              />
              <MetadataMonthPicker
                value={row.target_date}
                placeholder="Target Date"
                onChange={(value) => updateTimeline(row.local_id, { target_date: value })}
              />
              <button
                className="metadata-row-remove"
                type="button"
                onClick={() => removeTimelineRow(row.local_id)}
                aria-label="Remove milestone"
              >
                x
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="metadata-card">
        <div className="metadata-card-head">
          <span>Key risks & issues</span>
          <button className="metadata-add-action" type="button" onClick={addRisk}>
            + Add risk
          </button>
        </div>
        <div className="metadata-card-body metadata-table-body">
          {form.risks.map((risk, index) => (
            <div className="metadata-table-row metadata-risk-row" key={risk.local_id}>
              <input className="metadata-input" value={index + 1} aria-label="Risk number" readOnly />
              <AutoGrowTextarea
                value={risk.description}
                onChange={(event) => updateRisk(risk.local_id, { description: event.target.value })}
                placeholder="Description"
                rows={1}
              />
              <AutoGrowTextarea
                value={risk.green_action ?? ""}
                onChange={(event) => updateRisk(risk.local_id, { green_action: event.target.value })}
                placeholder="Go to green action"
                rows={1}
              />
              <select
                className={`metadata-select metadata-severity severity-${(risk.severity ?? "").toLowerCase()}`}
                value={risk.severity ?? ""}
                onChange={(event) => updateRisk(risk.local_id, { severity: event.target.value })}
              >
                <option value="">Severity</option>
                <option value="High">High</option>
                <option value="Med">Med</option>
                <option value="Low">Low</option>
              </select>
              <input
                className="metadata-input"
                value={risk.assigned_to ?? ""}
                onChange={(event) => updateRisk(risk.local_id, { assigned_to: event.target.value })}
                placeholder="Assigned"
              />
              <MetadataMonthPicker
                value={dateToMonthValue(risk.due_date)}
                placeholder="Due Date"
                onChange={(value) =>
                  updateRisk(risk.local_id, { due_date: monthToDateValue(value) })
                }
              />
              <AutoGrowTextarea
                value={risk.ramification ?? ""}
                onChange={(event) => updateRisk(risk.local_id, { ramification: event.target.value })}
                placeholder="Ramification"
                rows={1}
              />
              <button
                className="metadata-row-remove"
                type="button"
                onClick={() => removeRisk(risk.local_id)}
                aria-label={`Remove risk ${index + 1}`}
              >
                x
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="metadata-card">
        <div className="metadata-card-head">
          <span>Resource library</span>
          <button className="metadata-add-action" type="button" onClick={addResource}>
            + Add link
          </button>
        </div>
        <div className="metadata-card-body metadata-table-body">
          {form.resources.map((resource) => (
            <div className="metadata-table-row metadata-resource-row" key={resource.local_id}>
              <select className="metadata-select" defaultValue="other" disabled={resource.disabled}>
                <option value="jira">Jira</option>
                <option value="confluence">Confluence</option>
                <option value="repository">Repository</option>
                <option value="document">Document</option>
                <option value="sharepoint">SharePoint</option>
                <option value="other">Other</option>
              </select>
              <AutoGrowTextarea
                value={resource.title}
                onChange={(event) => updateResource(resource.local_id, { title: event.target.value })}
                placeholder="Title"
                rows={1}
                disabled={resource.disabled}
              />
              <AutoGrowTextarea
                value={resource.url}
                onChange={(event) => updateResource(resource.local_id, { url: event.target.value })}
                placeholder="https://..."
                rows={1}
                disabled={resource.disabled}
              />
              <AutoGrowTextarea
                value={resource.description ?? ""}
                onChange={(event) =>
                  updateResource(resource.local_id, { description: event.target.value })
                }
                placeholder="Description"
                rows={1}
                disabled={resource.disabled}
              />
              <button
                className="metadata-row-remove"
                type="button"
                onClick={() => removeResource(resource.local_id)}
                disabled={resource.disabled}
                aria-label={`Remove ${resource.title || "resource link"}`}
              >
                x
              </button>
            </div>
          ))}
        </div>
      </section>
    </form>
  );
}

function MetadataListCard({
  invalid = false,
  label,
  onAdd,
  onRemove,
  onUpdate,
  required = false,
  rows,
}: {
  invalid?: boolean;
  label: string;
  onAdd: () => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, value: string) => void;
  required?: boolean;
  rows: string[];
}) {
  return (
    <section
      className={
        invalid
          ? "metadata-card metadata-required-card invalid"
          : required
            ? "metadata-card metadata-required-card"
            : "metadata-card"
      }
    >
      <div className="metadata-card-head">
        <span>{label}</span>
        <div className="metadata-card-head-actions">
          {required ? <span className="metadata-required-badge">Required</span> : null}
          <button className="metadata-add-action" type="button" onClick={onAdd}>
            + Add
          </button>
        </div>
      </div>
      <div className="metadata-card-body metadata-list">
        {rows.map((row, index) => (
          <div className="metadata-list-row" key={`${label}-${index}`}>
            <AutoGrowTextarea
              className={invalid && !hasRequiredText(row) ? "metadata-textarea invalid" : undefined}
              value={row}
              onChange={(event) => onUpdate(index, event.target.value)}
              rows={1}
              maxLength={500}
              aria-invalid={invalid && !hasRequiredText(row)}
            />
            <button
              className="metadata-row-remove"
              type="button"
              onClick={() => onRemove(index)}
              aria-label={`Remove ${label} row ${index + 1}`}
            >
              x
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

function AutoGrowTextarea({
  className = "",
  onChange,
  rows = 1,
  value,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const resolvedClassName = className.includes("metadata-textarea")
    ? className
    : `metadata-textarea${className ? ` ${className}` : ""}`;

  useEffect(() => {
    resizeTextarea(textareaRef.current);
  }, [value]);

  return (
    <textarea
      {...props}
      ref={textareaRef}
      className={resolvedClassName}
      onChange={(event) => {
        resizeTextarea(event.currentTarget);
        onChange?.(event);
      }}
      rows={rows}
      value={value}
    />
  );
}

function resizeTextarea(textarea: HTMLTextAreaElement | null) {
  if (!textarea) {
    return;
  }
  textarea.style.height = "auto";
  textarea.style.height = `${textarea.scrollHeight}px`;
}

function MetadataMonthPicker({
  onChange,
  placeholder,
  value,
}: {
  onChange: (value: string) => void;
  placeholder: string;
  value: string;
}) {
  const pickerRef = useRef<HTMLDivElement | null>(null);
  const parsedValue = parseMonthValue(value);
  const currentYear = new Date().getFullYear();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<"months" | "years">("months");
  const [selectedYear, setSelectedYear] = useState(parsedValue?.year ?? currentYear);

  useEffect(() => {
    if (parsedValue) {
      setSelectedYear(parsedValue.year);
    }
  }, [parsedValue?.year]);

  useEffect(() => {
    function handleDocumentClick(event: MouseEvent) {
      if (!pickerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleDocumentClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleDocumentClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  function handleToggle() {
    setOpen((current) => !current);
    setView("months");
  }

  function handleMonthSelect(month: number) {
    onChange(formatMonthValue({ year: selectedYear, month }));
    setOpen(false);
    setView("months");
  }

  function handleYearSelect(year: number) {
    setSelectedYear(year);
    setView("months");
  }

  function handleClear() {
    onChange("");
    setOpen(false);
    setView("months");
  }

  const yearOptions = Array.from({ length: 21 }, (_, index) => selectedYear - 10 + index);
  const label = parsedValue ? formatMonthLabel(value) : placeholder;

  return (
    <div
      className={`cycle-picker metadata-month-picker${open ? " open" : ""}${
        parsedValue ? "" : " empty"
      }`}
      ref={pickerRef}
    >
      <div className="cycle-picker-control">
        <button
          className="cycle-picker-label"
          type="button"
          onClick={handleToggle}
          aria-expanded={open}
          aria-label={`Open ${placeholder} picker`}
        >
          <span>{label}</span>
          <span className="metadata-calendar-icon" aria-hidden="true" />
        </button>
      </div>

      <div className="cycle-picker-menu" role="dialog" aria-label={`${placeholder} picker`}>
        <button className="cycle-picker-year" type="button" onClick={() => setView("years")}>
          {selectedYear}
        </button>

        <div className={`cycle-picker-view${view === "months" ? " active" : ""}`}>
          <div className="cycle-month-grid">
            {monthLabels.map((monthLabel, index) => {
              const month = index + 1;
              const isActive = parsedValue?.year === selectedYear && parsedValue.month === month;
              return (
                <button
                  key={monthLabel}
                  className={`cycle-month${isActive ? " active" : ""}`}
                  type="button"
                  onClick={() => handleMonthSelect(month)}
                >
                  {monthLabel}
                </button>
              );
            })}
          </div>
          {value ? (
            <button className="metadata-month-clear" type="button" onClick={handleClear}>
              Clear
            </button>
          ) : null}
        </div>

        <div className={`cycle-picker-view${view === "years" ? " active" : ""}`}>
          <div className="cycle-year-grid">
            {yearOptions.map((year) => (
              <button
                key={year}
                className={`cycle-year-option${year === selectedYear ? " active" : ""}`}
                type="button"
                onClick={() => handleYearSelect(year)}
              >
                {year}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function validateRequiredMetadata(
  form: MetadataFormState,
): { message: string; missingFields: RequiredMetadataField[] } | null {
  const missingFields = [
    { field: "why_this_partner", label: "Why this partner", value: form.why_this_partner },
    { field: "business_priority", label: "Business priority", value: form.business_priority },
    { field: "highlights_status", label: "Highlights / status", value: form.highlights_status },
    { field: "goals", label: "Goals", value: form.goals },
  ]
    .filter((item) => !hasRequiredText(item.value));

  if (!missingFields.length) {
    return null;
  }

  const labels = missingFields.map((item) => item.label);
  return {
    message: `${labels.join(", ")} ${labels.length === 1 ? "is" : "are"} required.`,
    missingFields: missingFields.map((item) => item.field as RequiredMetadataField),
  };
}

function hasRequiredText(value: string): boolean {
  return value
    .split("\n")
    .some((row) => row.trim().length > 0);
}

function isRequiredMetadataField(field: keyof MetadataFormState): field is RequiredMetadataField {
  return ["why_this_partner", "business_priority", "highlights_status", "goals"].includes(
    field,
  );
}

function metadataToForm(metadata: PartnerMetadata): MetadataFormState {
  return {
    status: metadata.status ?? "green",
    why_this_partner: metadata.why_this_partner ?? "",
    business_priority: metadata.business_priority ?? "",
    highlights_status: metadata.highlights_status ?? "",
    goals: metadata.goals ?? "",
    execution_timeline: timelineRowsFromText(metadata.execution_timeline),
    risks: metadata.risks.length ? metadata.risks.map(riskToEditable) : [emptyRisk()],
    resources: metadata.resources.length ? metadata.resources.map(resourceToEditable) : [emptyResource()],
  };
}

function formToPayload(form: MetadataFormState): PartnerMetadataPayload {
  return {
    status: form.status || null,
    why_this_partner: valueOrNull(form.why_this_partner),
    business_priority: valueOrNull(form.business_priority),
    highlights_status: valueOrNull(form.highlights_status),
    goals: valueOrNull(form.goals),
    execution_timeline: valueOrNull(timelineRowsToText(form.execution_timeline)),
    risks: form.risks
      .map(({ local_id: _localId, risk_id: _riskId, ...risk }) => ({
        ...risk,
        description: risk.description.trim(),
        green_action: valueOrNull(risk.green_action),
        severity: valueOrNull(risk.severity),
        assigned_to: valueOrNull(risk.assigned_to),
        ramification: valueOrNull(risk.ramification),
      }))
      .filter((risk) => risk.description),
    resources: form.resources
      .filter((resource) => !resource.disabled)
      .map(({ local_id: _localId, resource_link_id: _resourceLinkId, ...resource }) => ({
        title: resource.title.trim(),
        url: resource.url.trim(),
        description: valueOrNull(resource.description),
        source_kind: resource.source_kind,
        disabled: resource.disabled,
        archived_at: resource.archived_at,
      }))
      .filter((resource) => resource.title && resource.url),
  };
}

function emptyForm(): MetadataFormState {
  return {
    status: "green",
    why_this_partner: "",
    business_priority: "",
    highlights_status: "",
    goals: "",
    execution_timeline: [emptyTimelineRow()],
    risks: [emptyRisk()],
    resources: [emptyResource()],
  };
}

function emptyTimelineRow(): EditableTimelineRow {
  return {
    local_id: createLocalId(),
    milestone: "",
    target_date: "",
  };
}

function emptyRisk(): EditableRisk {
  return {
    local_id: createLocalId(),
    risk_id: null,
    description: "",
    green_action: "",
    severity: "",
    assigned_to: "",
    due_date: null,
    ramification: "",
  };
}

function emptyResource(): EditableResource {
  return {
    local_id: createLocalId(),
    title: "",
    url: "",
    description: "",
    source_kind: "manual",
    disabled: false,
    archived_at: null,
  };
}

function riskToEditable(risk: PartnerMetadataRisk): EditableRisk {
  return {
    ...risk,
    local_id: risk.risk_id ?? createLocalId(),
  };
}

function resourceToEditable(resource: PartnerResourceLink): EditableResource {
  return {
    ...resource,
    local_id: resource.resource_link_id ?? createLocalId(),
  };
}

function createLocalId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }

  return `local-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function valueOrNull(value: string | null): string | null {
  const cleaned = value?.trim();
  return cleaned || null;
}

function dateToMonthValue(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  return value.slice(0, 7);
}

function monthToDateValue(value: string | null): string | null {
  const month = valueOrNull(value);
  return month ? `${month}-01` : null;
}

function parseMonthValue(value: string | null | undefined): { year: number; month: number } | null {
  if (!value) {
    return null;
  }
  const match = /^(\d{4})-(\d{2})/.exec(value);
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

function formatMonthValue(value: { year: number; month: number }): string {
  return `${value.year}-${String(value.month).padStart(2, "0")}`;
}

function formatMonthLabel(value: string): string {
  const parsed = parseMonthValue(value);
  if (!parsed) {
    return value;
  }

  const month = new Intl.DateTimeFormat("en", { month: "long" }).format(
    new Date(parsed.year, parsed.month - 1, 1),
  );
  return `${month} ${parsed.year}`;
}

function previousMonthValue(value: string): string {
  const parsed = parseMonthValue(value);
  const current = parsed ?? {
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1,
  };
  const previous = new Date(current.year, current.month - 2, 1);
  return formatMonthValue({
    year: previous.getFullYear(),
    month: previous.getMonth() + 1,
  });
}

function listFieldRows(value: string): string[] {
  const rows = value.split("\n");
  return rows.length ? rows : [""];
}

function timelineRowsFromText(value: string | null): EditableTimelineRow[] {
  if (!value?.trim()) {
    return [emptyTimelineRow()];
  }

  return value.split("\n").map((line) => {
    const [milestone = "", targetDate = ""] = line.split(" | Target: ");
    return {
      local_id: createLocalId(),
      milestone,
      target_date: dateToMonthValue(targetDate.trim()),
    };
  });
}

function timelineRowsToText(rows: EditableTimelineRow[]): string {
  return rows
    .map((row) => {
      const milestone = row.milestone.trim();
      const target = row.target_date.trim();
      if (!milestone && !target) {
        return "";
      }
      return target ? `${milestone} | Target: ${target}` : milestone;
    })
    .filter(Boolean)
    .join("\n");
}
