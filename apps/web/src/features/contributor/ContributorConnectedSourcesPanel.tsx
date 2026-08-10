"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  ConnectedSource,
  ConnectedSourceRequestPayload,
  ConnectedSourceType,
  archiveContributorConnectedSource,
  createContributorConnectedSource,
  listContributorConnectedSources,
  pauseContributorConnectedSource,
  resumeContributorConnectedSource,
  updateContributorConnectedSource,
} from "@/features/contributor/contributor-connected-sources-api";

type ContributorConnectedSourcesPanelProps = {
  partnerId: string;
  onSourcesChange: () => void;
};

type SourceFormState = {
  sourceType: ConnectedSourceType;
  displayName: string;
  sourceUrl: string;
  channelName: string;
  channelId: string;
  botInvitedConfirmed: boolean;
};

const sourceTypeOptions: Array<{ value: ConnectedSourceType; label: string }> = [
  { value: "jira_issue", label: "Jira Issue" },
  { value: "slack_channel", label: "Slack Channel" },
  { value: "sharepoint_file", label: "SharePoint File" },
  { value: "confluence_page", label: "Confluence Page" },
  { value: "github_repository", label: "GitHub Repository" },
  { value: "github_issue", label: "GitHub Issue" },
  { value: "github_pull_request", label: "GitHub Pull Request" },
];

const sourceTypeCards: Array<{
  value: ConnectedSourceType;
  label: string;
  shortLabel: string;
}> = [
  { value: "slack_channel", label: "Slack", shortLabel: "SL" },
  { value: "jira_issue", label: "Jira", shortLabel: "JI" },
  { value: "sharepoint_file", label: "SharePoint", shortLabel: "SP" },
  { value: "confluence_page", label: "Confluence", shortLabel: "CF" },
  { value: "github_repository", label: "GitHub", shortLabel: "GH" },
];

const emptyForm: SourceFormState = {
  sourceType: "jira_issue",
  displayName: "",
  sourceUrl: "",
  channelName: "",
  channelId: "",
  botInvitedConfirmed: false,
};

export function ContributorConnectedSourcesPanel({
  partnerId,
  onSourcesChange,
}: ContributorConnectedSourcesPanelProps) {
  const [sources, setSources] = useState<ConnectedSource[]>([]);
  const [form, setForm] = useState<SourceFormState>(emptyForm);
  const [editingSource, setEditingSource] = useState<ConnectedSource | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [requestModalOpen, setRequestModalOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    setToastMessage(null);

    listContributorConnectedSources(partnerId)
      .then((nextSources) => {
        if (mounted) {
          setSources(nextSources);
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load connected sources.");
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
  }, [partnerId]);

  useEffect(() => {
    if (!toastMessage) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => setToastMessage(null), 3200);
    return () => window.clearTimeout(timeoutId);
  }, [toastMessage]);

  const visibleSources = useMemo(
    () => sources.filter((source) => source.status !== "archived"),
    [sources],
  );

  function updateForm(updates: Partial<SourceFormState>) {
    setForm((current) => ({ ...current, ...updates }));
  }

  function resetForm() {
    setForm(emptyForm);
    setEditingSource(null);
  }

  function openRequestModal() {
    resetForm();
    setError(null);
    setToastMessage(null);
    setRequestModalOpen(true);
  }

  function closeRequestModal() {
    if (saving) {
      return;
    }
    resetForm();
    setError(null);
    setRequestModalOpen(false);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setToastMessage(null);

    try {
      const payload = formToPayload(form);
      const savedSource = editingSource
        ? await updateContributorConnectedSource(
            partnerId,
            editingSource.connected_source_id,
            payload,
          )
        : await createContributorConnectedSource(partnerId, payload);
      setSources((current) => upsertSource(current, savedSource));
      resetForm();
      setToastMessage(
        editingSource ? "Connected source resubmitted." : "Connected source requested.",
      );
      setRequestModalOpen(false);
      onSourcesChange();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to save connected source.");
    } finally {
      setSaving(false);
    }
  }

  function editSource(source: ConnectedSource) {
    setEditingSource(source);
    setForm(sourceToForm(source));
    setError(null);
    setToastMessage(null);
    setRequestModalOpen(true);
  }

  async function handleAction(
    source: ConnectedSource,
    action: "archive" | "pause" | "resume",
  ) {
    setError(null);
    setToastMessage(null);
    try {
      const updatedSource =
        action === "archive"
          ? await archiveContributorConnectedSource(partnerId, source.connected_source_id)
          : action === "pause"
            ? await pauseContributorConnectedSource(partnerId, source.connected_source_id)
            : await resumeContributorConnectedSource(partnerId, source.connected_source_id);
      setSources((current) => upsertSource(current, updatedSource));
      setToastMessage(`Connected source ${action === "archive" ? "archived" : action + "d"}.`);
      onSourcesChange();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to update connected source.");
    }
  }

  return (
    <section className="contributor-tab-panel" aria-label="Connected Sources">
      <div className="connected-source-toolbar">
        <button className="connected-source-request-action" type="button" onClick={openRequestModal}>
          Request Source +
        </button>
      </div>

      {toastMessage ? (
        <div className="connected-source-toast" role="status" aria-live="polite">
          {toastMessage}
        </div>
      ) : null}

      <ConnectedSourceTable
        sources={visibleSources}
        loading={loading}
        onEdit={editSource}
        onAction={handleAction}
      />

      {requestModalOpen ? (
        <div
          className="source-request-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeRequestModal();
            }
          }}
        >
          <form
            className="source-request-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="source-request-title"
            onSubmit={handleSubmit}
          >
            <div className="source-request-modal-head">
              <h4 id="source-request-title">
                {editingSource ? "Resubmit" : "Add"} {modalSourceLabel(form.sourceType)} Source
              </h4>
              <button
                className="source-request-close"
                type="button"
                onClick={closeRequestModal}
                aria-label="Close source request"
              >
                x
              </button>
            </div>

            <div className="source-request-modal-body">
              {error ? <p className="workspace-error inline-error">{error}</p> : null}

              <fieldset className="source-type-picker">
                <legend>Source type</legend>
                <div className="source-type-card-grid">
                  {sourceTypeCards.map((option) => (
                    <button
                      className={form.sourceType === option.value ? "active" : ""}
                      key={option.value}
                      type="button"
                      onClick={() => updateForm({ sourceType: option.value })}
                      aria-pressed={form.sourceType === option.value}
                    >
                      <span data-source-type={option.value}>{option.shortLabel}</span>
                      <strong>{option.label}</strong>
                    </button>
                  ))}
                </div>
              </fieldset>

              {form.sourceType === "slack_channel" ? (
                <>
                  <div className="form-field source-request-field">
                    <label htmlFor="connected-source-channel-name">Channel Name</label>
                    <input
                      id="connected-source-channel-name"
                      value={form.channelName}
                      onChange={(event) => updateForm({ channelName: event.target.value })}
                      placeholder="e.g. Red Hat Slack workspace"
                      required
                    />
                  </div>
                  <div className="form-field source-request-field">
                    <label htmlFor="connected-source-channel-id">Channel ID</label>
                    <input
                      id="connected-source-channel-id"
                      value={form.channelId}
                      onChange={(event) => updateForm({ channelId: event.target.value })}
                      placeholder="e.g. C0123456789"
                      required
                    />
                  </div>
                  <label className="checkbox-row source-request-confirmation">
                    <input
                      type="checkbox"
                      checked={form.botInvitedConfirmed}
                      onChange={(event) =>
                        updateForm({ botInvitedConfirmed: event.target.checked })
                      }
                      required
                    />
                    <span>Bot/app has been invited to this channel</span>
                  </label>
                </>
              ) : (
                <>
                  <div className="form-field source-request-field">
                    <label htmlFor="connected-source-name">Name</label>
                    <input
                      id="connected-source-name"
                      value={form.displayName}
                      onChange={(event) => updateForm({ displayName: event.target.value })}
                      placeholder={namePlaceholderForType(form.sourceType)}
                    />
                  </div>
                  <div className="form-field source-request-field">
                    <label htmlFor="connected-source-url">{urlLabelForType(form.sourceType)}</label>
                    <input
                      id="connected-source-url"
                      value={form.sourceUrl}
                      onChange={(event) => updateForm({ sourceUrl: event.target.value })}
                      placeholder={placeholderForType(form.sourceType)}
                      required
                    />
                  </div>
                </>
              )}
            </div>

            <div className="source-request-modal-footer">
              <button className="ghost-action" type="button" onClick={closeRequestModal}>
                Cancel
              </button>
              <button className="primary-action compact-action" type="submit" disabled={saving}>
                {saving ? "Saving" : "Submit request"}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </section>
  );
}

function ConnectedSourceTable({
  sources,
  loading,
  onEdit,
  onAction,
}: {
  sources: ConnectedSource[];
  loading: boolean;
  onEdit: (source: ConnectedSource) => void;
  onAction: (source: ConnectedSource, action: "archive" | "pause" | "resume") => void;
}) {
  return (
    <div className="contributor-table-wrap connected-source-table-wrap">
      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>Type</th>
            <th>Status</th>
            <th>Identifier</th>
            <th>Requested</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={6}>Loading connected sources</td>
            </tr>
          ) : null}

          {!loading && sources.length === 0 ? (
            <tr>
              <td colSpan={6}>No connected sources</td>
            </tr>
          ) : null}

          {!loading
            ? sources.map((source) => (
                <tr key={source.connected_source_id}>
                  <td>
                    <strong>{source.display_name}</strong>
                    {source.source_url ? (
                      <a href={source.source_url} target="_blank" rel="noreferrer">
                        Open source
                      </a>
                    ) : null}
                  </td>
                  <td>{labelForType(source.source_type)}</td>
                  <td>
                    <span className={`status-pill ${source.contributor_status}`}>
                      {labelForContributorStatus(source.contributor_status)}
                    </span>
                  </td>
                  <td>{identifierForSource(source)}</td>
                  <td>{formatDate(source.created_at)}</td>
                  <td>
                    <div className="table-actions">
                      {source.status === "pending" || source.status === "rejected" ? (
                        <button type="button" onClick={() => onEdit(source)}>
                          {source.status === "rejected" ? "Resubmit" : "Edit"}
                        </button>
                      ) : null}
                      {source.status === "active" ? (
                        <button type="button" onClick={() => onAction(source, "pause")}>
                          Pause
                        </button>
                      ) : null}
                      {source.status === "disabled" ? (
                        <button type="button" onClick={() => onAction(source, "resume")}>
                          Resume
                        </button>
                      ) : null}
                      <button type="button" onClick={() => onAction(source, "archive")}>
                        Archive
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            : null}
        </tbody>
      </table>
    </div>
  );
}

function formToPayload(form: SourceFormState): ConnectedSourceRequestPayload {
  return {
    source_type: form.sourceType,
    display_name: form.displayName || undefined,
    source_url: form.sourceType === "slack_channel" ? undefined : form.sourceUrl,
    channel_name: form.sourceType === "slack_channel" ? form.channelName : undefined,
    channel_id: form.sourceType === "slack_channel" ? form.channelId : undefined,
    bot_invited_confirmed:
      form.sourceType === "slack_channel" ? form.botInvitedConfirmed : undefined,
  };
}

function sourceToForm(source: ConnectedSource): SourceFormState {
  return {
    sourceType: source.source_type,
    displayName: source.display_name,
    sourceUrl: source.source_url ?? "",
    channelName: source.details.channel_name ?? "",
    channelId: source.details.channel_id ?? "",
    botInvitedConfirmed: source.details.bot_invited_confirmed ?? false,
  };
}

function upsertSource(sources: ConnectedSource[], savedSource: ConnectedSource): ConnectedSource[] {
  const exists = sources.some(
    (source) => source.connected_source_id === savedSource.connected_source_id,
  );
  if (!exists) {
    return [savedSource, ...sources];
  }
  return sources.map((source) =>
    source.connected_source_id === savedSource.connected_source_id ? savedSource : source,
  );
}

function placeholderForType(sourceType: ConnectedSourceType): string {
  return {
    jira_issue: "https://yourorg.atlassian.net/...",
    sharepoint_file: "https://yourorg.sharepoint.com/...",
    confluence_page: "https://yourorg.atlassian.net/wiki/...",
    github_repository: "https://github.com/org/repo",
    github_issue: "https://github.com/org/repo/issues/123",
    github_pull_request: "https://github.com/org/repo/pull/123",
    slack_channel: "",
  }[sourceType];
}

function namePlaceholderForType(sourceType: ConnectedSourceType): string {
  return {
    jira_issue: "e.g. Red Hat Jira project",
    sharepoint_file: "e.g. Partner Documents",
    confluence_page: "e.g. Partner Wiki",
    github_repository: "e.g. Ecosystem Repo",
    github_issue: "e.g. Ecosystem Issue",
    github_pull_request: "e.g. Ecosystem Pull Request",
    slack_channel: "",
  }[sourceType];
}

function urlLabelForType(sourceType: ConnectedSourceType): string {
  return {
    jira_issue: "Jira URL",
    sharepoint_file: "Document URL",
    confluence_page: "Confluence Page URL",
    github_repository: "GitHub URL",
    github_issue: "GitHub URL",
    github_pull_request: "GitHub URL",
    slack_channel: "URL",
  }[sourceType];
}

function modalSourceLabel(sourceType: ConnectedSourceType): string {
  if (sourceType === "slack_channel") {
    return "Slack";
  }
  if (sourceType === "jira_issue") {
    return "Jira";
  }
  if (sourceType === "sharepoint_file") {
    return "SharePoint";
  }
  if (sourceType === "confluence_page") {
    return "Confluence";
  }
  return "GitHub";
}

function labelForType(sourceType: ConnectedSourceType): string {
  return sourceTypeOptions.find((option) => option.value === sourceType)?.label ?? sourceType;
}

function labelForContributorStatus(status: string): string {
  return {
    pending: "Pending",
    active: "Active",
    rejected: "Rejected",
    disabled: "Paused",
    archived: "Archived",
  }[status] ?? "Pending";
}

function identifierForSource(source: ConnectedSource): string {
  if (source.source_type === "slack_channel") {
    return source.details.channel_id ?? source.external_identifier ?? "";
  }
  if (source.source_type === "jira_issue") {
    return source.details.issue_key ?? source.external_identifier ?? "";
  }
  if (source.source_type === "github_repository") {
    return source.details.github_repository ?? source.external_identifier ?? "";
  }
  if (source.source_type === "github_issue" || source.source_type === "github_pull_request") {
    return `${source.details.github_repository ?? ""} #${source.details.github_number ?? ""}`;
  }
  return source.external_identifier ?? "";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}
