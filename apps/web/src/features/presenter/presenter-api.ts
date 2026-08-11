const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type PresenterPartner = {
  partner_id: string;
  name: string;
  description: string | null;
  approved_updates_count: number;
  last_activity_at: string | null;
};

export type PresenterUpdate = {
  update_id: string;
  partner_id: string;
  partner_name: string;
  cycle: string;
  title: string;
  summary: string;
  source_type:
    | "manual"
    | "slack"
    | "jira"
    | "sharepoint"
    | "confluence"
    | "github"
    | "file"
    | "email";
  source_label: string | null;
  source_url: string | null;
  approved_at: string | null;
  approved_by: string | null;
};

export type PresenterMetadata = {
  partner_id: string;
  partner_name: string;
  cycle: string;
  status: "green" | "amber" | "red" | null;
  why_this_partner: string | null;
  business_priority: string | null;
  highlights_status: string | null;
  goals: string | null;
  execution_timeline: string | null;
  risks: Array<{
    description: string;
    green_action: string | null;
    severity: string | null;
    assigned_to: string | null;
    due_date: string | null;
    ramification: string | null;
  }>;
  resources: Array<{
    resource_link_id: string;
    title: string;
    url: string;
    description: string | null;
    source_kind: "manual" | "connected_source";
    disabled: boolean;
  }>;
  saved_at: string | null;
};

export type PresenterAnalysis = {
  cycle: string;
  partner_id: string | null;
  partner_ids: string[];
  executive_summary: string;
  decision_board: Array<{
    partner_id: string;
    partner_name: string;
    signal: string;
    rationale: string;
    severity: string;
  }>;
  update_count: number;
  partner_count: number;
  source_mix: Record<string, number>;
};

export type DraftEmail = {
  cycle: string;
  partner_id: string | null;
  partner_ids: string[];
  subject: string;
  body: string;
  update_count: number;
};

export type PresenterAskAnswer = {
  answer: string;
  grounded: boolean;
  model: string | null;
};

export type PresenterExecutiveSummary = {
  cycle: string;
  partner_id: string | null;
  partner_ids: string[];
  bullets: string[];
  source_note: string | null;
  update_count: number;
  grounded: boolean;
  model: string | null;
};

export type PresenterDecisionBoardSignal = {
  partner_id: string | null;
  partner_name: string | null;
  priority: string | null;
  title: string;
  action: string;
  rationale: string;
  owner: string | null;
  due_date: string | null;
  severity: string | null;
  source_label: string | null;
  source_url: string | null;
};

export type PresenterDecisionBoard = {
  cycle: string;
  partner_id: string | null;
  partner_ids: string[];
  signals: PresenterDecisionBoardSignal[];
  source_note: string | null;
  update_count: number;
  grounded: boolean;
  model: string | null;
};

export type PresenterPeriodQuery = {
  cycle: string;
  dateStart?: string | null;
  dateEnd?: string | null;
};

export async function listPresenterPartners(period: PresenterPeriodQuery): Promise<PresenterPartner[]> {
  const params = presenterPeriodParams(period);
  const response = await fetch(`${apiBaseUrl}/api/presenter/partners?${params.toString()}`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load presenter partners.");
  }

  const payload = (await response.json()) as { partners: PresenterPartner[] };
  return payload.partners;
}

export async function listPresenterUpdates({
  cycle,
  dateStart,
  dateEnd,
  partnerId,
  partnerIds,
  search,
}: {
  cycle: string;
  dateStart?: string | null;
  dateEnd?: string | null;
  partnerId?: string | null;
  partnerIds?: string[];
  search: string;
}): Promise<PresenterUpdate[]> {
  const params = presenterPeriodParams({ cycle, dateStart, dateEnd });
  if (partnerId) {
    params.set("partner_id", partnerId);
  }
  appendPartnerIds(params, partnerIds);
  const cleanedSearch = search.trim();
  if (cleanedSearch) {
    params.set("search", cleanedSearch);
  }

  const response = await fetch(`${apiBaseUrl}/api/presenter/updates?${params.toString()}`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load presenter updates.");
  }

  const payload = (await response.json()) as { updates: PresenterUpdate[] };
  return payload.updates;
}

export async function getPresenterMetadata(
  partnerId: string,
  cycle: string,
): Promise<PresenterMetadata> {
  const response = await fetch(
    `${apiBaseUrl}/api/presenter/partners/${partnerId}/metadata?cycle=${cycle}`,
    {
      credentials: "include",
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error("Unable to load presenter metadata.");
  }

  return response.json();
}

export async function getPresenterAnalysis({
  cycle,
  dateStart,
  dateEnd,
  partnerId,
  partnerIds,
}: {
  cycle: string;
  dateStart?: string | null;
  dateEnd?: string | null;
  partnerId?: string | null;
  partnerIds?: string[];
}): Promise<PresenterAnalysis> {
  const params = presenterPeriodParams({ cycle, dateStart, dateEnd });
  if (partnerId) {
    params.set("partner_id", partnerId);
  }
  appendPartnerIds(params, partnerIds);

  const response = await fetch(`${apiBaseUrl}/api/presenter/analysis?${params.toString()}`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load presenter analysis.");
  }

  return response.json();
}

export async function draftPresenterEmail({
  cycle,
  dateStart,
  dateEnd,
  partnerId,
  partnerIds,
}: {
  cycle: string;
  dateStart?: string | null;
  dateEnd?: string | null;
  partnerId?: string | null;
  partnerIds?: string[];
}): Promise<DraftEmail> {
  const response = await fetch(`${apiBaseUrl}/api/presenter/draft-email`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cycle,
      date_start: dateStart || null,
      date_end: dateEnd || null,
      partner_id: partnerId,
      partner_ids: partnerIds ?? [],
    }),
  });

  if (!response.ok) {
    throw new Error("Unable to draft presenter email.");
  }

  return response.json();
}

export async function askPresenterAi({
  cycle,
  dateStart,
  dateEnd,
  partnerId,
  partnerIds,
  question,
}: {
  cycle: string;
  dateStart?: string | null;
  dateEnd?: string | null;
  partnerId?: string | null;
  partnerIds?: string[];
  question: string;
}): Promise<PresenterAskAnswer> {
  const response = await fetch(`${apiBaseUrl}/api/presenter/ask`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cycle,
      date_start: dateStart || null,
      date_end: dateEnd || null,
      partner_id: partnerId,
      partner_ids: partnerIds ?? [],
      question,
    }),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "Unable to ask AI assistant.");
  }

  return response.json();
}

export async function generatePresenterExecutiveSummary({
  cycle,
  dateStart,
  dateEnd,
  partnerId,
  partnerIds,
}: {
  cycle: string;
  dateStart?: string | null;
  dateEnd?: string | null;
  partnerId?: string | null;
  partnerIds?: string[];
}): Promise<PresenterExecutiveSummary> {
  const response = await fetch(`${apiBaseUrl}/api/presenter/executive-summary`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cycle,
      date_start: dateStart || null,
      date_end: dateEnd || null,
      partner_id: partnerId,
      partner_ids: partnerIds ?? [],
    }),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "Unable to generate executive summary.");
  }

  return response.json();
}

export async function generatePresenterDecisionBoard({
  cycle,
  dateStart,
  dateEnd,
  partnerId,
  partnerIds,
}: {
  cycle: string;
  dateStart?: string | null;
  dateEnd?: string | null;
  partnerId?: string | null;
  partnerIds?: string[];
}): Promise<PresenterDecisionBoard> {
  const response = await fetch(`${apiBaseUrl}/api/presenter/decision-board`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cycle,
      date_start: dateStart || null,
      date_end: dateEnd || null,
      partner_id: partnerId,
      partner_ids: partnerIds ?? [],
    }),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "Unable to generate decision board.");
  }

  return response.json();
}

function presenterPeriodParams({ cycle, dateStart, dateEnd }: PresenterPeriodQuery) {
  const params = new URLSearchParams({ cycle });
  if (dateStart && dateEnd) {
    params.set("date_start", dateStart);
    params.set("date_end", dateEnd);
  }
  return params;
}

function appendPartnerIds(params: URLSearchParams, partnerIds: string[] | undefined) {
  for (const partnerId of partnerIds ?? []) {
    params.append("partner_ids", partnerId);
  }
}
