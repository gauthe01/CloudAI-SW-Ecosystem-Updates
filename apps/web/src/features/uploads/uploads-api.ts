const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type KnowledgeUploadScope = "admin_knowledge" | "contributor_partner_file";
export type KnowledgeUploadProcessingStatus = "parsed" | "stored" | "unsupported";

export type KnowledgeUpload = {
  upload_id: string;
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
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? fallbackMessage;
  } catch {
    return fallbackMessage;
  }
}
