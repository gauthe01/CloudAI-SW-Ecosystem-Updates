"use client";

import { FormEvent, useEffect, useState } from "react";

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

export function ContributorPartnerMetadataPanel({
  partnerId,
  cycle,
}: ContributorPartnerMetadataPanelProps) {
  const [form, setForm] = useState<MetadataFormState>(emptyForm());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    setNotice(null);

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
    setNotice(null);

    try {
      const savedMetadata = await saveContributorPartnerMetadata(
        partnerId,
        cycle,
        formToPayload(form),
      );
      setForm(metadataToForm(savedMetadata));
      setNotice("Metadata saved.");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to save metadata.");
    } finally {
      setSaving(false);
    }
  }

  function updateField(field: keyof MetadataFormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
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
    return <p className="muted-copy">Loading partner metadata</p>;
  }

  return (
    <form className="metadata-form gold-metadata-form" onSubmit={handleSubmit}>
      {error ? <p className="workspace-error inline-error">{error}</p> : null}
      {notice ? <p className="metadata-save-notice">{notice}</p> : null}

      <section className="metadata-card">
        <div className="metadata-card-head">
          <span>Partner Metadata</span>
          <button className="metadata-save-action" type="submit" disabled={saving}>
            {saving ? "Saving" : "Save metadata"}
          </button>
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

      <section className="metadata-card">
        <div className="metadata-card-head">
          <span>Why this partner</span>
        </div>
        <div className="metadata-card-body">
          <textarea
            className="metadata-textarea metadata-textarea-large"
            value={form.why_this_partner}
            onChange={(event) => updateField("why_this_partner", event.target.value)}
            maxLength={2000}
          />
        </div>
      </section>

      <div className="metadata-grid">
        <MetadataListCard
          label="Business priority"
          rows={listFieldRows(form.business_priority)}
          onAdd={() => addListFieldRow("business_priority")}
          onRemove={(index) => removeListFieldRow("business_priority", index)}
          onUpdate={(index, value) => updateListField("business_priority", index, value)}
        />
        <MetadataListCard
          label="Highlights / status"
          rows={listFieldRows(form.highlights_status)}
          onAdd={() => addListFieldRow("highlights_status")}
          onRemove={(index) => removeListFieldRow("highlights_status", index)}
          onUpdate={(index, value) => updateListField("highlights_status", index, value)}
        />
        <MetadataListCard
          label="Goals"
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
              <textarea
                className="metadata-textarea"
                value={row.milestone}
                onChange={(event) => updateTimeline(row.local_id, { milestone: event.target.value })}
                maxLength={300}
                placeholder="Milestone"
                rows={1}
              />
              <span className={`metadata-date-wrap${row.target_date ? " has-value" : ""}`} data-placeholder="Target Date">
                <input
                  className="metadata-input"
                  type="date"
                  value={row.target_date}
                  onChange={(event) => updateTimeline(row.local_id, { target_date: event.target.value })}
                  aria-label="Target Date"
                />
              </span>
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
              <textarea
                className="metadata-textarea"
                value={risk.description}
                onChange={(event) => updateRisk(risk.local_id, { description: event.target.value })}
                placeholder="Description"
                rows={1}
              />
              <textarea
                className="metadata-textarea"
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
              <span className={`metadata-date-wrap${risk.due_date ? " has-value" : ""}`} data-placeholder="Due Date">
                <input
                  className="metadata-input"
                  type="date"
                  value={risk.due_date ?? ""}
                  onChange={(event) =>
                    updateRisk(risk.local_id, { due_date: valueOrNull(event.target.value) })
                  }
                  aria-label="Due Date"
                />
              </span>
              <textarea
                className="metadata-textarea"
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
          {form.resources.map((resource, index) => (
            <div className="metadata-table-row metadata-resource-row" key={resource.local_id}>
              <select className="metadata-select" defaultValue="other" disabled={resource.disabled}>
                <option value="jira">Jira</option>
                <option value="confluence">Confluence</option>
                <option value="repository">Repository</option>
                <option value="document">Document</option>
                <option value="sharepoint">SharePoint</option>
                <option value="other">Other</option>
              </select>
              <textarea
                className="metadata-textarea"
                value={resource.title}
                onChange={(event) => updateResource(resource.local_id, { title: event.target.value })}
                placeholder="Title"
                rows={1}
                disabled={resource.disabled}
              />
              <textarea
                className="metadata-textarea"
                value={resource.url}
                onChange={(event) => updateResource(resource.local_id, { url: event.target.value })}
                placeholder="https://..."
                rows={1}
                disabled={resource.disabled}
              />
              <textarea
                className="metadata-textarea"
                value={resource.description ?? ""}
                onChange={(event) =>
                  updateResource(resource.local_id, { description: event.target.value })
                }
                placeholder="Description"
                rows={1}
                disabled={resource.disabled}
              />
              <label className="metadata-featured">
                <input type="checkbox" defaultChecked={index === 0} disabled={resource.disabled} />
                Featured
              </label>
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
  label,
  onAdd,
  onRemove,
  onUpdate,
  rows,
}: {
  label: string;
  onAdd: () => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, value: string) => void;
  rows: string[];
}) {
  return (
    <section className="metadata-card">
      <div className="metadata-card-head">
        <span>{label}</span>
        <button className="metadata-add-action" type="button" onClick={onAdd}>
          + Add
        </button>
      </div>
      <div className="metadata-card-body metadata-list">
        {rows.map((row, index) => (
          <div className="metadata-list-row" key={`${label}-${index}`}>
            <textarea
              className="metadata-textarea"
              value={row}
              onChange={(event) => onUpdate(index, event.target.value)}
              rows={1}
              maxLength={500}
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
      target_date: targetDate.trim(),
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
