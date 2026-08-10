"use client";

import { useEffect, useMemo, useState } from "react";

import {
  AdminConnectedSource,
  AdminConnectedSourceReviewBucket,
  approveAdminConnectedSource,
  disableAdminConnectedSource,
  listAdminConnectedSources,
  markAdminConnectedSourceNeedsAccess,
  rejectAdminConnectedSource,
  testAdminConnectedSourceAccess,
} from "@/features/admin/admin-connected-sources-api";

type QueueTab = AdminConnectedSourceReviewBucket;
type PendingAction = "test" | "approve" | "reject" | "needs_access" | "disable";

const queueTabs: Array<{ value: QueueTab; label: string }> = [
  { value: "needs_review", label: "Needs Review" },
  { value: "attention", label: "Attention" },
  { value: "active", label: "Active" },
  { value: "rejected", label: "Rejected" },
  { value: "all", label: "All" },
];

export function AdminSourceApprovalsPanel() {
  const [sources, setSources] = useState<AdminConnectedSource[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [activeQueue, setActiveQueue] = useState<QueueTab>("needs_review");
  const [reviewNote, setReviewNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    listAdminConnectedSources()
      .then((nextSources) => {
        if (mounted) {
          setSources(nextSources);
          setSelectedSourceId(null);
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load source approvals.");
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
  }, []);

  function changeQueue(queue: QueueTab) {
    setActiveQueue(queue);
    setSelectedSourceId(null);
    setReviewNote("");
    setError(null);
    setNotice(null);
  }

  const queueCounts = useMemo(() => {
    return queueTabs.reduce<Record<QueueTab, number>>(
      (counts, tab) => {
        counts[tab.value] =
          tab.value === "all"
            ? sources.length
            : sources.filter((source) => source.review_bucket === tab.value).length;
        return counts;
      },
      { needs_review: 0, attention: 0, active: 0, rejected: 0, all: 0 },
    );
  }, [sources]);

  const filteredSources = useMemo(() => {
    if (activeQueue === "all") {
      return sources;
    }
    return sources.filter((source) => source.review_bucket === activeQueue);
  }, [activeQueue, sources]);

  const selectedSource = useMemo(() => {
    return sources.find((source) => source.connected_source_id === selectedSourceId) ?? null;
  }, [selectedSourceId, sources]);

  function selectSource(source: AdminConnectedSource) {
    setSelectedSourceId(source.connected_source_id);
    setReviewNote("");
    setError(null);
    setNotice(null);
  }

  async function runSourceAction(
    action: PendingAction,
    callback: () => Promise<AdminConnectedSource>,
    successMessage: string,
  ) {
    setPendingAction(action);
    setError(null);
    setNotice(null);
    try {
      const savedSource = await callback();
      setSources((current) => upsertSource(current, savedSource));
      setSelectedSourceId(savedSource.connected_source_id);
      setReviewNote("");
      setNotice(successMessage);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to update source approval.");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="admin-team-panel admin-source-approvals-panel">
      <div className="source-approval-tabs" role="tablist" aria-label="Source approval queues">
        {queueTabs.map((tab) => (
          <button
            key={tab.value}
            className={activeQueue === tab.value ? "active" : ""}
            type="button"
            onClick={() => changeQueue(tab.value)}
          >
            <span>{tab.label}</span>
            <strong>{queueCounts[tab.value]}</strong>
          </button>
        ))}
      </div>

      {error ? <p className="workspace-error inline-error">{error}</p> : null}
      {notice ? <p className="metadata-save-notice">{notice}</p> : null}

      <div
        className={
          selectedSource ? "source-approval-layout has-review-panel" : "source-approval-layout"
        }
      >
        <div className="team-table-wrap source-approval-table-wrap">
          <table className="team-table source-approval-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Partner</th>
                <th>Type</th>
                <th>Status</th>
                <th>Integration</th>
                <th>Requested</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6}>Loading source approvals</td>
                </tr>
              ) : null}

              {!loading && filteredSources.length === 0 ? (
                <tr>
                  <td colSpan={6}>No sources in this queue</td>
                </tr>
              ) : null}

              {!loading
                ? filteredSources.map((source) => (
                    <tr
                      className={
                        selectedSourceId === source.connected_source_id ? "selected-row" : ""
                      }
                      key={source.connected_source_id}
                      onClick={() => selectSource(source)}
                    >
                      <td>
                        <strong>{source.display_name}</strong>
                        <span>{source.external_identifier ?? "No external ID"}</span>
                      </td>
                      <td>{source.partner.name}</td>
                      <td>{labelForSourceType(source.source_type)}</td>
                      <td>
                        <span className={`status-pill ${statusClass(source.status)}`}>
                          {labelForStatus(source.status)}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`status-pill ${
                            source.integration_available ? "active" : "pending"
                          }`}
                        >
                          {source.integration_available ? "Enabled" : "Unavailable"}
                        </span>
                      </td>
                      <td>{formatDate(source.created_at)}</td>
                    </tr>
                  ))
                : null}
            </tbody>
          </table>
        </div>

        {selectedSource ? (
          <aside className="source-review-panel" aria-label="Source review details">
            <>
              <div className="source-review-header">
                <p className="eyebrow">Review Detail</p>
                <h3>{selectedSource.display_name}</h3>
                <span className={`status-pill ${statusClass(selectedSource.status)}`}>
                  {labelForStatus(selectedSource.status)}
                </span>
              </div>

              <dl className="source-review-facts">
                <div>
                  <dt>Partner</dt>
                  <dd>{selectedSource.partner.name}</dd>
                </div>
                <div>
                  <dt>Requested By</dt>
                  <dd>
                    {selectedSource.requested_by.display_name}
                    <span>{selectedSource.requested_by.email}</span>
                  </dd>
                </div>
                <div>
                  <dt>Source Type</dt>
                  <dd>{labelForSourceType(selectedSource.source_type)}</dd>
                </div>
                <div>
                  <dt>Required Integration</dt>
                  <dd>
                    {labelForIntegration(selectedSource.required_integration_type)}
                    <span>
                      {selectedSource.integration_available
                        ? "Global integration enabled"
                        : `Global integration ${selectedSource.integration_status ?? "missing"}`}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>Identifier</dt>
                  <dd>{selectedSource.external_identifier ?? identifierForSource(selectedSource)}</dd>
                </div>
                <div>
                  <dt>Access Test</dt>
                  <dd>
                    {selectedSource.last_tested_at
                      ? formatDate(selectedSource.last_tested_at)
                      : "Not tested"}
                    {selectedSource.access_test_summary ? (
                      <span>{selectedSource.access_test_summary}</span>
                    ) : null}
                  </dd>
                </div>
              </dl>

              {selectedSource.exact_duplicate_count > 0 ? (
                <p className="source-approval-warning">
                  Exact duplicate found for this partner and source type.
                </p>
              ) : null}

              {selectedSource.source_url ? (
                <a
                  className="source-review-link"
                  href={selectedSource.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open source
                </a>
              ) : null}

              <div className="form-field">
                <label htmlFor="source-review-note">Review note</label>
                <textarea
                  id="source-review-note"
                  value={reviewNote}
                  onChange={(event) => setReviewNote(event.target.value)}
                  placeholder="Optional reason or access setup note"
                  rows={4}
                />
              </div>

              <div className="source-review-actions">
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() =>
                    runSourceAction(
                      "test",
                      () =>
                        testAdminConnectedSourceAccess(selectedSource.connected_source_id),
                      "Access readiness checked.",
                    )
                  }
                  disabled={pendingAction === "test"}
                >
                  {pendingAction === "test" ? "Testing" : "Test access"}
                </button>
                <button
                  className="primary-action compact-action"
                  type="button"
                  onClick={() =>
                    runSourceAction(
                      "approve",
                      () => approveAdminConnectedSource(selectedSource.connected_source_id),
                      "Source approved and activated.",
                    )
                  }
                  disabled={pendingAction === "approve" || selectedSource.status !== "pending"}
                >
                  {pendingAction === "approve" ? "Approving" : "Approve"}
                </button>
                <button
                  className="ghost-action"
                  type="button"
                  onClick={() =>
                    runSourceAction(
                      "needs_access",
                      () =>
                        markAdminConnectedSourceNeedsAccess(
                          selectedSource.connected_source_id,
                          reviewNote,
                        ),
                      "Source marked as needing access setup.",
                    )
                  }
                  disabled={pendingAction === "needs_access"}
                >
                  Needs access
                </button>
                <button
                  className="ghost-action"
                  type="button"
                  onClick={() =>
                    runSourceAction(
                      "reject",
                      () =>
                        rejectAdminConnectedSource(
                          selectedSource.connected_source_id,
                          reviewNote,
                        ),
                      "Source rejected.",
                    )
                  }
                  disabled={pendingAction === "reject"}
                >
                  Reject
                </button>
                {selectedSource.status === "active" ? (
                  <button
                    className="ghost-action"
                    type="button"
                    onClick={() =>
                      runSourceAction(
                        "disable",
                        () =>
                          disableAdminConnectedSource(
                            selectedSource.connected_source_id,
                            reviewNote,
                          ),
                        "Source disabled.",
                      )
                    }
                    disabled={pendingAction === "disable"}
                  >
                    Disable
                  </button>
                ) : null}
              </div>
            </>
          </aside>
        ) : null}
      </div>
    </div>
  );
}

function upsertSource(
  sources: AdminConnectedSource[],
  savedSource: AdminConnectedSource,
): AdminConnectedSource[] {
  return sources.map((source) =>
    source.connected_source_id === savedSource.connected_source_id ? savedSource : source,
  );
}

function statusClass(status: AdminConnectedSource["status"]): string {
  if (status === "active") {
    return "active";
  }
  if (status === "rejected" || status === "failed") {
    return "rejected";
  }
  if (status === "disabled" || status === "archived") {
    return "archived";
  }
  return "pending";
}

function labelForStatus(status: AdminConnectedSource["status"]): string {
  const labels: Record<AdminConnectedSource["status"], string> = {
    pending: "Pending",
    needs_access_setup: "Needs access",
    active: "Active",
    rejected: "Rejected",
    disabled: "Disabled",
    archived: "Archived",
    failed: "Failed",
  };
  return labels[status];
}

function labelForSourceType(sourceType: AdminConnectedSource["source_type"]): string {
  const labels: Record<AdminConnectedSource["source_type"], string> = {
    jira_issue: "Jira Issue",
    slack_channel: "Slack Channel",
    sharepoint_file: "SharePoint File",
    confluence_page: "Confluence Page",
    github_repository: "GitHub Repository",
    github_issue: "GitHub Issue",
    github_pull_request: "GitHub Pull Request",
  };
  return labels[sourceType];
}

function labelForIntegration(integrationType: AdminConnectedSource["required_integration_type"]) {
  const labels: Record<AdminConnectedSource["required_integration_type"], string> = {
    slack: "Slack",
    jira: "Jira",
    sharepoint: "SharePoint / Microsoft Graph",
    confluence: "Confluence",
    github: "GitHub",
  };
  return labels[integrationType];
}

function identifierForSource(source: AdminConnectedSource): string {
  if (source.details.channel_id) {
    return source.details.channel_id;
  }
  if (source.details.issue_key) {
    return source.details.issue_key;
  }
  if (source.details.github_repository) {
    return source.details.github_number
      ? `${source.details.github_repository} #${source.details.github_number}`
      : source.details.github_repository;
  }
  return source.source_url ?? "No identifier";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
