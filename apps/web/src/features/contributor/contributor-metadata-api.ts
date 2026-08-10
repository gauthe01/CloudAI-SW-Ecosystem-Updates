const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type PartnerHealthStatus = "green" | "amber" | "red";

export type PartnerMetadataRisk = {
  risk_id?: string | null;
  description: string;
  green_action: string | null;
  severity: string | null;
  assigned_to: string | null;
  due_date: string | null;
  ramification: string | null;
};

export type PartnerResourceLink = {
  resource_link_id?: string;
  title: string;
  url: string;
  description: string | null;
  source_kind?: "manual" | "connected_source";
  disabled?: boolean;
  archived_at?: string | null;
};

export type PartnerMetadata = {
  metadata_id: string | null;
  partner_id: string;
  cycle: string;
  status: PartnerHealthStatus | null;
  why_this_partner: string | null;
  business_priority: string | null;
  highlights_status: string | null;
  goals: string | null;
  execution_timeline: string | null;
  risks: PartnerMetadataRisk[];
  resources: PartnerResourceLink[];
  saved_at: string | null;
  saved_by: string | null;
};

export type PartnerMetadataPayload = Omit<
  PartnerMetadata,
  "metadata_id" | "partner_id" | "cycle" | "saved_at" | "saved_by"
>;

export async function getContributorPartnerMetadata(
  partnerId: string,
  cycle: string,
): Promise<PartnerMetadata> {
  const response = await fetch(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/metadata?cycle=${cycle}`,
    {
      credentials: "include",
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error("Unable to load partner metadata.");
  }

  return response.json();
}

export async function saveContributorPartnerMetadata(
  partnerId: string,
  cycle: string,
  payload: PartnerMetadataPayload,
): Promise<PartnerMetadata> {
  const response = await fetch(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/metadata?cycle=${cycle}`,
    {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to save partner metadata."));
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
