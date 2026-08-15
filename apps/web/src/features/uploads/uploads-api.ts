const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type KnowledgeUploadScope = "admin_knowledge" | "contributor_partner_file";
export type KnowledgeUploadProcessingStatus = "parsed" | "stored" | "unsupported";
export type KnowledgeUploadCandidateStatus =
  | "pending"
  | "approved"
  | "dismissed"
  | "staged"
  | "committed"
  | "skipped";
export type KnowledgeUploadCandidateReviewStatus =
  | "ready"
  | "needs_mapping"
  | "topic_pending"
  | "likely_noise"
  | "duplicate";
export type KnowledgeUploadSessionStatus = "analyzing" | "ready_for_review" | "committed";

export type KnowledgeUpload = {
  upload_id: string;
  session_id: string | null;
  partner_id: string | null;
  partner_name: string | null;
  scope: KnowledgeUploadScope;
  title: string;
  description: string | null;
  original_filename: string;
  content_type: string | null;
  file_size_bytes: number;
  checksum_sha256: string;
  storage_backend: string;
  processing_status: KnowledgeUploadProcessingStatus;
  text_preview: string | null;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
};

export type KnowledgeUploadCandidate = {
  candidate_id: string;
  session_id: string | null;
  upload_id: string;
  partner_id: string | null;
  partner_name: string | null;
  cycle_month: string | null;
  raw_label: string | null;
  summary: string;
  evidence_snippet: string | null;
  section_label: string | null;
  source_filename: string | null;
  source_location: string | null;
  source_url: string | null;
  confidence: string;
  review_status: KnowledgeUploadCandidateReviewStatus;
  status: KnowledgeUploadCandidateStatus;
  parser_notes: string | null;
  committed_update_id: string | null;
  committed_topic_update_id: string | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeUploadDetail = {
  upload: KnowledgeUpload;
  candidates: KnowledgeUploadCandidate[];
};

export type KnowledgeUploadCandidateUpdatePayload = {
  partner_id?: string | null;
  cycle_month?: string | null;
  summary?: string;
  status?: KnowledgeUploadCandidateStatus;
};

export type KnowledgeUploadStageResponse = {
  staged_count: number;
  skipped_count: number;
  created_update_ids: string[];
};

export type KnowledgeUploadSession = {
  session_id: string;
  status: KnowledgeUploadSessionStatus;
  document_type: string | null;
  inferred_cycle: string | null;
  cycle_confidence: string | null;
  summary: string | null;
  partner_count: number;
  update_count: number;
  unknown_name_count: number;
  warnings: string[];
  rulebook_name: string;
  rulebook_version: string;
  agent_run_id: string | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeUploadSessionDetail = {
  session: KnowledgeUploadSession;
  uploads: KnowledgeUpload[];
  candidates: KnowledgeUploadCandidate[];
  unknown_labels: string[];
};

export type KnowledgeUploadMappingDecision = {
  raw_label: string;
  action: "existing_partner" | "skip" | "noise" | "new_topic";
  partner_id?: string | null;
};

export type KnowledgeUploadCommitResponse = {
  session: KnowledgeUploadSession;
  committed_count: number;
  skipped_count: number;
  partner_summaries: Array<{
    partner_id: string;
    partner_name: string;
    updates_approved: number;
    status: string;
  }>;
  topic_summaries: Array<{
    topic_label: string;
    updates_approved: number;
    status: string;
  }>;
  created_update_ids: string[];
  created_topic_update_ids: string[];
};

export type UploadFormPayload = {
  file: File;
  title?: string;
  description?: string;
  partnerId?: string;
};

export async function listAdminKnowledgeUploads(): Promise<KnowledgeUpload[]> {
  const response = await fetch(`${apiBaseUrl}/api/admin/knowledge-uploads`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load knowledge uploads.");
  }

  const payload = (await response.json()) as { uploads: KnowledgeUpload[] };
  return payload.uploads;
}

export async function createAdminKnowledgeUpload(
  payload: UploadFormPayload,
): Promise<KnowledgeUpload> {
  const body = uploadPayloadToFormData(payload);
  if (payload.partnerId) {
    body.set("partner_id", payload.partnerId);
  }
  return createUpload(`${apiBaseUrl}/api/admin/knowledge-uploads`, body);
}

export async function createAdminKnowledgeUploadSession(
  files: File[],
): Promise<KnowledgeUploadSessionDetail> {
  const body = new FormData();
  for (const file of files) {
    body.append("files", file);
  }

  const response = await fetch(`${apiBaseUrl}/api/admin/knowledge-uploads/sessions`, {
    method: "POST",
    credentials: "include",
    body,
  });

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to analyze knowledge files."));
  }

  return response.json();
}

export async function getAdminKnowledgeUploadSession(
  sessionId: string,
): Promise<KnowledgeUploadSessionDetail> {
  const response = await fetch(`${apiBaseUrl}/api/admin/knowledge-uploads/sessions/${sessionId}`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to load knowledge upload session."));
  }

  return response.json();
}

export async function applyAdminKnowledgeUploadMappings(
  sessionId: string,
  mappings: KnowledgeUploadMappingDecision[],
): Promise<KnowledgeUploadSessionDetail> {
  const response = await fetch(
    `${apiBaseUrl}/api/admin/knowledge-uploads/sessions/${sessionId}/mappings`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mappings }),
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to resolve partner mappings."));
  }

  return response.json();
}

export async function updateAdminKnowledgeUploadSessionCandidate(
  sessionId: string,
  candidateId: string,
  payload: KnowledgeUploadCandidateUpdatePayload,
): Promise<KnowledgeUploadCandidate> {
  const response = await fetch(
    `${apiBaseUrl}/api/admin/knowledge-uploads/sessions/${sessionId}/candidates/${candidateId}`,
    {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to update candidate."));
  }

  return response.json();
}

export async function dismissAdminKnowledgeUploadSessionCandidate(
  sessionId: string,
  candidateId: string,
): Promise<KnowledgeUploadCandidate> {
  const response = await fetch(
    `${apiBaseUrl}/api/admin/knowledge-uploads/sessions/${sessionId}/candidates/${candidateId}/dismiss`,
    {
      method: "POST",
      credentials: "include",
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to dismiss candidate."));
  }

  return response.json();
}

export async function commitAdminKnowledgeUploadSession(
  sessionId: string,
  candidateIds: string[],
): Promise<KnowledgeUploadCommitResponse> {
  const response = await fetch(
    `${apiBaseUrl}/api/admin/knowledge-uploads/sessions/${sessionId}/commit`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_ids: candidateIds }),
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to commit approved knowledge."));
  }

  return response.json();
}

export async function getAdminKnowledgeUploadDetail(
  uploadId: string,
): Promise<KnowledgeUploadDetail> {
  const response = await fetch(`${apiBaseUrl}/api/admin/knowledge-uploads/${uploadId}`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load knowledge upload review.");
  }

  return response.json();
}

export async function updateAdminKnowledgeUploadCandidate(
  uploadId: string,
  candidateId: string,
  payload: KnowledgeUploadCandidateUpdatePayload,
): Promise<KnowledgeUploadCandidate> {
  const response = await fetch(
    `${apiBaseUrl}/api/admin/knowledge-uploads/${uploadId}/candidates/${candidateId}`,
    {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to update candidate."));
  }

  return response.json();
}

export async function dismissAdminKnowledgeUploadCandidate(
  uploadId: string,
  candidateId: string,
): Promise<KnowledgeUploadCandidate> {
  const response = await fetch(
    `${apiBaseUrl}/api/admin/knowledge-uploads/${uploadId}/candidates/${candidateId}/dismiss`,
    {
      method: "POST",
      credentials: "include",
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to dismiss candidate."));
  }

  return response.json();
}

export async function stageAdminKnowledgeUploadCandidates(
  uploadId: string,
  candidateIds: string[],
): Promise<KnowledgeUploadStageResponse> {
  const response = await fetch(`${apiBaseUrl}/api/admin/knowledge-uploads/${uploadId}/stage`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_ids: candidateIds }),
  });

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to stage candidates."));
  }

  return response.json();
}

export async function listContributorPartnerUploads(
  partnerId: string,
): Promise<KnowledgeUpload[]> {
  const response = await fetch(`${apiBaseUrl}/api/contributor/partners/${partnerId}/uploads`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load partner files.");
  }

  const payload = (await response.json()) as { uploads: KnowledgeUpload[] };
  return payload.uploads;
}

export async function createContributorPartnerUpload(
  partnerId: string,
  payload: UploadFormPayload,
): Promise<KnowledgeUpload> {
  return createUpload(
    `${apiBaseUrl}/api/contributor/partners/${partnerId}/uploads`,
    uploadPayloadToFormData(payload),
  );
}

async function createUpload(url: string, body: FormData): Promise<KnowledgeUpload> {
  const response = await fetch(url, {
    method: "POST",
    credentials: "include",
    body,
  });

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to upload file."));
  }

  return response.json();
}

function uploadPayloadToFormData(payload: UploadFormPayload): FormData {
  const body = new FormData();
  body.set("file", payload.file);
  if (payload.title?.trim()) {
    body.set("title", payload.title.trim());
  }
  if (payload.description?.trim()) {
    body.set("description", payload.description.trim());
  }
  return body;
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
