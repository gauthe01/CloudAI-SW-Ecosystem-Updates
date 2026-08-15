const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ContributorPartner = {
  partner_id: string;
  name: string;
  description: string | null;
  updates_count: number;
  connected_sources_count: number;
  last_activity_at: string | null;
};

export type ContributorDashboardTabCounts = {
  pending_updates: number;
  approved_updates: number;
  connected_sources: number;
};

export type ContributorDashboardContext = {
  partner: ContributorPartner;
  active_cycle: string;
  active_cycle_label: string;
  default_tab: "pending_updates";
  tab_counts: ContributorDashboardTabCounts;
};

export async function listContributorPartners(): Promise<ContributorPartner[]> {
  const response = await fetch(`${apiBaseUrl}/api/contributor/partners`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load assigned partners.");
  }

  const payload = (await response.json()) as { partners: ContributorPartner[] };
  return payload.partners;
}

export async function getContributorDashboardContext(
  partnerId: string,
  cycle?: string,
): Promise<ContributorDashboardContext> {
  const params = new URLSearchParams();
  if (cycle) {
    params.set("cycle", cycle);
  }
  const query = params.toString();
  const response = await fetch(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/dashboard-context${query ? `?${query}` : ""}`,
    {
      credentials: "include",
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error("Unable to load contributor dashboard.");
  }

  return response.json();
}
