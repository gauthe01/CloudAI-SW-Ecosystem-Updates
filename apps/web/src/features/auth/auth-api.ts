const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type AccountView = "contributor" | "presenter" | "admin";

export type AuthUser = {
  user_id: string;
  email: string;
  display_name: string;
  roles: AccountView[];
};

export type AuthContext = {
  user: AuthUser;
  available_views: AccountView[];
  active_view: AccountView;
};

export type LoginResponse = AuthContext & {
  expires_at: string;
};

export type LoginPayload = {
  email: string;
  password: string;
  keepSignedIn: boolean;
};

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  const response = await fetch(`${apiBaseUrl}/api/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: payload.email,
      password: payload.password,
      keep_signed_in: payload.keepSignedIn,
    }),
  });

  if (!response.ok) {
    throw new Error("Invalid email or password.");
  }

  return response.json();
}

export async function getCurrentAuthContext(): Promise<AuthContext> {
  const response = await fetch(`${apiBaseUrl}/api/auth/me`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Authentication required.");
  }

  return response.json();
}

export async function switchActiveView(activeView: AccountView): Promise<AuthContext> {
  const response = await fetch(`${apiBaseUrl}/api/auth/active-view`, {
    method: "PATCH",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ active_view: activeView }),
  });

  if (!response.ok) {
    throw new Error("Unable to switch account view.");
  }

  return response.json();
}

export async function logout(): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Unable to sign out.");
  }
}
