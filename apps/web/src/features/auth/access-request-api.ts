const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type AccessRequestPayload = {
  displayName: string;
  email: string;
  password: string;
  confirmPassword: string;
};

export type AccessRequestResponse = {
  status: "pending";
  message: string;
};

export async function requestAccountAccess(
  payload: AccessRequestPayload,
): Promise<AccessRequestResponse> {
  const response = await fetch(`${apiBaseUrl}/api/access-requests`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      display_name: payload.displayName,
      email: payload.email,
      password: payload.password,
      confirm_password: payload.confirmPassword,
    }),
  });

  if (!response.ok) {
    throw new Error(await readError(response, "Something went wrong. Please try again later."));
  }

  return response.json();
}

async function readError(response: Response, fallbackMessage: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string | Array<{ msg?: string }> };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (Array.isArray(payload.detail) && payload.detail[0]?.msg) {
      return normalizeValidationMessage(payload.detail[0].msg);
    }
    return fallbackMessage;
  } catch {
    return fallbackMessage;
  }
}

function normalizeValidationMessage(message: string): string {
  if (message.includes("Use your ARM email address")) {
    return "Use your ARM email address.";
  }
  if (message.includes("Create a stronger password")) {
    return "Create a stronger password.";
  }
  if (message.includes("Passwords don't match")) {
    return "Passwords don't match.";
  }
  return "Something went wrong. Please try again later.";
}
