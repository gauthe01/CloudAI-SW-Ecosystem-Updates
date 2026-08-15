const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type PartnerUpdateStatus = "pending" | "approved" | "rejected";

export type PartnerUpdateSourceType =
  | "manual"
  | "slack"
  | "jira"
  | "sharepoint"
  | "confluence"
  | "github"
  | "file"
  | "email";

export type PartnerUpdate = {
  update_id: string;
  partner_id: string;
  cycle: string;
  title: string;
  summary: string;
  source_type: PartnerUpdateSourceType;
  source_label: string | null;
  source_url: string | null;
  status: PartnerUpdateStatus;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  approved_by: string | null;
  rejected_at: string | null;
  rejected_by: string | null;
};

export type PartnerUpdateEditPayload = {
  title: string;
  summary: string;
};

export type ManualUpdateCreatePayload = {
  title: string;
  summary: string;
};

export type FileUpdateCreatePayload = {
  title: string;
  summary: string;
  source_label?: string;
};

export async function listContributorPartnerUpdates({
  partnerId,
  cycle,
  status,
  search,
}: {
  partnerId: string;
  cycle: string;
  status: Extract<PartnerUpdateStatus, "pending" | "approved">;
  search: string;
}): Promise<PartnerUpdate[]> {
  const params = new URLSearchParams({ cycle, status });
  const cleanedSearch = search.trim();
  if (cleanedSearch) {
    params.set("search", cleanedSearch);
  }

  const response = await fetch(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/updates?${params.toString()}`,
    {
      credentials: "include",
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error("Unable to load updates.");
  }

  const payload = (await response.json()) as { updates: PartnerUpdate[] };
  return payload.updates;
}

export async function createContributorManualUpdate(
  partnerId: string,
  cycle: string,
  payload: ManualUpdateCreatePayload,
): Promise<PartnerUpdate> {
  const response = await fetch(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/updates?cycle=${cycle}`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to add manual update."));
  }

  return response.json();
}

export async function createContributorFileUpdate(
  partnerId: string,
  cycle: string,
  payload: FileUpdateCreatePayload,
): Promise<PartnerUpdate> {
  const response = await fetch(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/updates/file?cycle=${cycle}`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to add file update."));
  }

  return response.json();
}

export async function editContributorPartnerUpdate(
  partnerId: string,
  updateId: string,
  payload: PartnerUpdateEditPayload,
): Promise<PartnerUpdate> {
  const response = await fetch(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/updates/${updateId}`,
    {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to edit update."));
  }

  return response.json();
}

export async function approveContributorPartnerUpdate(
  partnerId: string,
  updateId: string,
): Promise<PartnerUpdate> {
  return runUpdateAction(partnerId, updateId, "approve", "Unable to approve update.");
}

export async function dismissContributorPartnerUpdate(
  partnerId: string,
  updateId: string,
): Promise<PartnerUpdate> {
  return runUpdateAction(partnerId, updateId, "dismiss", "Unable to dismiss update.");
}

async function runUpdateAction(
  partnerId: string,
  updateId: string,
  action: "approve" | "dismiss",
  fallbackMessage: string,
): Promise<PartnerUpdate> {
  const response = await fetch(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/updates/${updateId}/${action}`,
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
    const payload = (await response.json()) as { detail?: unknown };
    return formatErrorDetail(payload.detail, fallbackMessage);
  } catch {
    return fallbackMessage;
  }
}

function formatErrorDetail(detail: unknown, fallbackMessage: string): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!isApiValidationError(item)) {
          return "";
        }
        const location = item.loc?.map(String).join(".");
        return location ? `${location}: ${item.msg}` : item.msg;
      })
      .filter(Boolean);
    return messages.join(" ") || fallbackMessage;
  }
  if (isApiValidationError(detail)) {
    return detail.msg;
  }
  return fallbackMessage;
}

function isApiValidationError(value: unknown): value is { loc?: unknown[]; msg: string } {
  return (
    typeof value === "object" &&
    value !== null &&
    "msg" in value &&
    typeof (value as { msg?: unknown }).msg === "string"
  );
}
