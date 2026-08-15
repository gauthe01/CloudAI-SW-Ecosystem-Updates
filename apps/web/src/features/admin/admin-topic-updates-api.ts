const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type AdminTopicUpdate = {
  topic_update_id: string;
  topic_label: string;
  cycle: string;
  title: string;
  summary: string;
  source_type: string;
  source_label: string | null;
  source_url: string | null;
  status: string;
  approved_at: string | null;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
};

export type AdminTopicUpdateList = {
  topics: AdminTopicUpdate[];
  total_count: number;
  topic_count: number;
};

export async function listAdminTopicUpdates({
  cycle,
  search,
}: {
  cycle?: string | null;
  search?: string;
} = {}): Promise<AdminTopicUpdateList> {
  const params = new URLSearchParams();
  if (cycle) {
    params.set("cycle", cycle);
  }
  if (search?.trim()) {
    params.set("search", search.trim());
  }

  const response = await fetch(
    `${apiBaseUrl}/api/admin/topic-updates${params.size ? `?${params.toString()}` : ""}`,
    {
      credentials: "include",
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error("Unable to load Events/Topics updates.");
  }

  return (await response.json()) as AdminTopicUpdateList;
}
