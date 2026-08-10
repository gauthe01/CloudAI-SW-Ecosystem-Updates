const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ConnectedSourceType =
  | "jira_issue"
  | "slack_channel"
  | "sharepoint_file"
  | "confluence_page"
  | "github_repository"
  | "github_issue"
  | "github_pull_request";

export type ConnectedSourceStatus =
  | "pending"
  | "needs_access_setup"
  | "active"
  | "rejected"
  | "disabled"
  | "archived"
  | "failed";

export type ConnectedSourceRequestPayload = {
  source_type: ConnectedSourceType;
  display_name?: string;
  source_url?: string;
  channel_name?: string;
  channel_id?: string;
  bot_invited_confirmed?: boolean;
};

export type ConnectedSource = {
  connected_source_id: string;
  partner_id: string;
  source_type: ConnectedSourceType;
  status: ConnectedSourceStatus;
  contributor_status: string;
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
  created_by: string;
  approved_at: string | null;
  rejected_at: string | null;
  disabled_at: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export async function listContributorConnectedSources(
  partnerId: string,
): Promise<ConnectedSource[]> {
  const response = await fetch(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/connected-sources`,
    {
      credentials: "include",
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error("Unable to load connected sources.");
  }

  const payload = (await response.json()) as { connected_sources: ConnectedSource[] };
  return payload.connected_sources;
}

export async function createContributorConnectedSource(
  partnerId: string,
  payload: ConnectedSourceRequestPayload,
): Promise<ConnectedSource> {
  return writeConnectedSource(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/connected-sources`,
    "POST",
    payload,
    "Unable to request connected source.",
  );
}

export async function updateContributorConnectedSource(
  partnerId: string,
  connectedSourceId: string,
  payload: ConnectedSourceRequestPayload,
): Promise<ConnectedSource> {
  return writeConnectedSource(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/connected-sources/${connectedSourceId}`,
    "PATCH",
    payload,
    "Unable to update connected source.",
  );
}

export async function archiveContributorConnectedSource(
  partnerId: string,
  connectedSourceId: string,
): Promise<ConnectedSource> {
  return runConnectedSourceAction(partnerId, connectedSourceId, "archive", "Unable to archive.");
}

export async function pauseContributorConnectedSource(
  partnerId: string,
  connectedSourceId: string,
): Promise<ConnectedSource> {
  return runConnectedSourceAction(partnerId, connectedSourceId, "pause", "Unable to pause.");
}

export async function resumeContributorConnectedSource(
  partnerId: string,
  connectedSourceId: string,
): Promise<ConnectedSource> {
  return runConnectedSourceAction(partnerId, connectedSourceId, "resume", "Unable to resume.");
}

async function writeConnectedSource(
  url: string,
  method: "POST" | "PATCH",
  payload: ConnectedSourceRequestPayload,
  fallbackMessage: string,
): Promise<ConnectedSource> {
  const response = await fetch(url, {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readError(response, fallbackMessage));
  }

  return response.json();
}

async function runConnectedSourceAction(
  partnerId: string,
  connectedSourceId: string,
  action: "archive" | "pause" | "resume",
  fallbackMessage: string,
): Promise<ConnectedSource> {
  const response = await fetch(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/connected-sources/${connectedSourceId}/${action}`,
    {
      method: "POST",
      credentials: "include",
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
