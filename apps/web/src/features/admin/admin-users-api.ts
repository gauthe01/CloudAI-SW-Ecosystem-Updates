import { AccountView } from "@/features/auth/auth-api";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type AdminUserStatus = "active" | "deactivated";

export type AdminUser = {
  user_id: string;
  email: string;
  display_name: string;
  status: AdminUserStatus;
  roles: AccountView[];
  created_at: string;
  updated_at: string;
  deactivated_at: string | null;
};

export type AdminUserPayload = {
  email: string;
  display_name: string;
  roles: AccountView[];
};

export type AccountAccessRequestStatus = "pending" | "approved" | "rejected";

export type AccountAccessRequest = {
  request_id: string;
  email: string;
  display_name: string;
  status: AccountAccessRequestStatus;
  requested_at: string;
  reviewed_at: string | null;
  reviewed_by: string | null;
  created_user_id: string | null;
};

export type AccountAccessRequestReview = {
  request: AccountAccessRequest;
  created_user: AdminUser | null;
};

export async function listAdminUsers(): Promise<AdminUser[]> {
  const response = await fetch(`${apiBaseUrl}/api/admin/users`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load team members.");
  }

  const payload = (await response.json()) as { users: AdminUser[] };
  return payload.users;
}

export async function createAdminUser(payload: AdminUserPayload): Promise<AdminUser> {
  const response = await fetch(`${apiBaseUrl}/api/admin/users`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to create team member."));
  }

  return response.json();
}

export async function updateAdminUser(
  userId: string,
  payload: AdminUserPayload,
): Promise<AdminUser> {
  const response = await fetch(`${apiBaseUrl}/api/admin/users/${userId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to update team member."));
  }

  return response.json();
}

export async function deactivateAdminUser(userId: string): Promise<AdminUser> {
  return setUserStatus(userId, "deactivate", "Unable to deactivate team member.");
}

export async function reactivateAdminUser(userId: string): Promise<AdminUser> {
  return setUserStatus(userId, "reactivate", "Unable to reactivate team member.");
}

export async function listAccountAccessRequests(): Promise<AccountAccessRequest[]> {
  const response = await fetch(`${apiBaseUrl}/api/admin/access-requests`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load access requests.");
  }

  const payload = (await response.json()) as { requests: AccountAccessRequest[] };
  return payload.requests;
}

export async function approveAccountAccessRequest(
  requestId: string,
  roles: AccountView[],
): Promise<AccountAccessRequestReview> {
  const response = await fetch(`${apiBaseUrl}/api/admin/access-requests/${requestId}/approve`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ roles }),
  });

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to approve access request."));
  }

  return response.json();
}

export async function rejectAccountAccessRequest(
  requestId: string,
): Promise<AccountAccessRequestReview> {
  return reviewAccountAccessRequest(requestId, "reject", "Unable to reject access request.");
}

async function setUserStatus(
  userId: string,
  action: "deactivate" | "reactivate",
  fallbackMessage: string,
): Promise<AdminUser> {
  const response = await fetch(`${apiBaseUrl}/api/admin/users/${userId}/${action}`, {
    method: "POST",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(await readError(response, fallbackMessage));
  }

  return response.json();
}

async function reviewAccountAccessRequest(
  requestId: string,
  action: "approve" | "reject",
  fallbackMessage: string,
): Promise<AccountAccessRequestReview> {
  const response = await fetch(`${apiBaseUrl}/api/admin/access-requests/${requestId}/${action}`, {
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
