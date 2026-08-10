import { AdminUser } from "@/features/admin/admin-users-api";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type PartnerStatus = "active" | "archived";

export type AssignedContributor = Pick<AdminUser, "user_id" | "email" | "display_name">;

export type AdminPartner = {
  partner_id: string;
  name: string;
  description: string | null;
  status: PartnerStatus;
  assigned_contributors: AssignedContributor[];
  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

export type AdminPartnerPayload = {
  name: string;
  description: string | null;
  assigned_contributor_user_ids: string[];
};

export async function listAdminPartners(): Promise<AdminPartner[]> {
  const response = await fetch(`${apiBaseUrl}/api/admin/partners`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load partners.");
  }

  const payload = (await response.json()) as { partners: AdminPartner[] };
  return payload.partners;
}

export async function createAdminPartner(payload: AdminPartnerPayload): Promise<AdminPartner> {
  const response = await fetch(`${apiBaseUrl}/api/admin/partners`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to create partner."));
  }

  return response.json();
}

export async function updateAdminPartner(
  partnerId: string,
  payload: AdminPartnerPayload,
): Promise<AdminPartner> {
  const response = await fetch(`${apiBaseUrl}/api/admin/partners/${partnerId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to update partner."));
  }

  return response.json();
}

export async function archiveAdminPartner(partnerId: string): Promise<AdminPartner> {
  return setPartnerStatus(partnerId, "archive", "Unable to archive partner.");
}

export async function restoreAdminPartner(partnerId: string): Promise<AdminPartner> {
  return setPartnerStatus(partnerId, "restore", "Unable to restore partner.");
}

async function setPartnerStatus(
  partnerId: string,
  action: "archive" | "restore",
  fallbackMessage: string,
): Promise<AdminPartner> {
  const response = await fetch(`${apiBaseUrl}/api/admin/partners/${partnerId}/${action}`, {
    method: "POST",
    credentials: "include",
  });

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
