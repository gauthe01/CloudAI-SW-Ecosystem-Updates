const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type AdminConnectedSourceType =
  | "jira_issue"
  | "slack_channel"
  | "sharepoint_file"
  | "confluence_page"
  | "github_repository"
  | "github_issue"
  | "github_pull_request";

export type AdminConnectedSourceStatus =
  | "pending"
  | "needs_access_setup"
  | "active"
  | "rejected"
  | "disabled"
  | "archived"
  | "failed";

export type AdminConnectedSourceReviewBucket =
  | "needs_review"
  | "active"
  | "rejected"
  | "attention"
  | "all";

export type AdminConnectedSource = {
  connected_source_id: string;
  partner: {
    partner_id: string;
    name: string;
  };
  source_type: AdminConnectedSourceType;
  status: AdminConnectedSourceStatus;
  review_bucket: AdminConnectedSourceReviewBucket;
  display_name: string;
  source_url: string | null;
  external_identifier: string | null;
  details: {
    channel_name: string | null;
    channel_id: string | null;
    bot_invited_confirmed: boolean | null;
    issue_key: string | null;
    file_name: string | null;
    page_title: string | null;
    github_target_kind: string | null;
    github_repository: string | null;
    github_number: number | null;
  };
  requested_by: {
    user_id: string;
    email: string;
    display_name: string;
  };
  approved_by: {
    user_id: string;
    email: string;
    display_name: string;
  } | null;
  required_integration_type: "slack" | "jira" | "sharepoint" | "confluence" | "github";
  integration_status: "not_configured" | "configured" | "enabled" | "disabled" | "error" | null;
  integration_available: boolean;
  exact_duplicate_count: number;
  access_test_summary: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  disabled_at: string | null;
  archived_at: string | null;
  last_tested_at: string | null;
  created_at: string;
  updated_at: string;
};

export async function listAdminConnectedSources(): Promise<AdminConnectedSource[]> {
  const response = await fetch(`${apiBaseUrl}/api/admin/connected-sources`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load source approvals.");
  }

  const payload = (await response.json()) as { connected_sources: AdminConnectedSource[] };
  return payload.connected_sources;
}

export async function testAdminConnectedSourceAccess(
  connectedSourceId: string,
): Promise<AdminConnectedSource> {
  return runAction(connectedSourceId, "test-access", {}, "Unable to test source access.");
}

export async function approveAdminConnectedSource(
  connectedSourceId: string,
): Promise<AdminConnectedSource> {
  return runAction(connectedSourceId, "approve", {}, "Unable to approve source.");
}

export async function rejectAdminConnectedSource(
  connectedSourceId: string,
  note: string,
): Promise<AdminConnectedSource> {
  return runAction(connectedSourceId, "reject", { note }, "Unable to reject source.");
}

export async function markAdminConnectedSourceNeedsAccess(
  connectedSourceId: string,
  note: string,
): Promise<AdminConnectedSource> {
  return runAction(
    connectedSourceId,
    "needs-access-setup",
    { note },
    "Unable to mark source as needing access setup.",
  );
}

export async function disableAdminConnectedSource(
  connectedSourceId: string,
  note: string,
): Promise<AdminConnectedSource> {
  return runAction(connectedSourceId, "disable", { note }, "Unable to disable source.");
}

async function runAction(
  connectedSourceId: string,
  action: "test-access" | "approve" | "reject" | "needs-access-setup" | "disable",
  payload: { note?: string },
  fallbackMessage: string,
): Promise<AdminConnectedSource> {
  const response = await fetch(
    `${apiBaseUrl}/api/admin/connected-sources/${connectedSourceId}/${action}`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, fallbackMessage));
  }

  return response.json();
}

async function readError(response: Response, fallbackMessage: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? fallbackMessage;
  } catch {
    return fallbackMessage;
  }
}
