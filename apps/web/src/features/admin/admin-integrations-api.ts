const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type IntegrationType = "slack" | "jira" | "sharepoint" | "confluence" | "github";

export type IntegrationStatus =
  | "not_configured"
  | "configured"
  | "enabled"
  | "disabled"
  | "error";

export type IntegrationTestStatus = "succeeded" | "failed";

export type IntegrationField = {
  name: string;
  label: string;
  input_type: string;
  required: boolean;
  configured: boolean;
  last_updated_at: string | null;
};

export type IntegrationTestRun = {
  test_run_id: string;
  status: IntegrationTestStatus;
  started_at: string;
  finished_at: string | null;
  result_summary: string | null;
};

export type AdminIntegration = {
  integration_id: string;
  integration_type: IntegrationType;
  display_name: string;
  description: string;
  status: IntegrationStatus;
  required_configured_count: number;
  required_field_count: number;
  webhook_url: string | null;
  fields: IntegrationField[];
  last_tested_at: string | null;
  last_test_status: IntegrationTestStatus | null;
  last_error_summary: string | null;
  enabled_at: string | null;
  disabled_at: string | null;
  recent_test_runs: IntegrationTestRun[];
  created_at: string;
  updated_at: string;
};

export async function listAdminIntegrations(): Promise<AdminIntegration[]> {
  const response = await fetch(`${apiBaseUrl}/api/admin/integrations`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to load global integrations.");
  }

  const payload = (await response.json()) as { integrations: AdminIntegration[] };
  return payload.integrations;
}

export async function updateAdminIntegrationCredentials(
  integrationType: IntegrationType,
  secrets: Record<string, string>,
): Promise<AdminIntegration> {
  const response = await fetch(
    `${apiBaseUrl}/api/admin/integrations/${integrationType}/credentials`,
    {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ secrets }),
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response, "Unable to save integration credentials."));
  }

  return response.json();
}

export async function testAdminIntegration(
  integrationType: IntegrationType,
): Promise<AdminIntegration> {
  return runIntegrationAction(integrationType, "test", "Unable to test integration.");
}

export async function enableAdminIntegration(
  integrationType: IntegrationType,
): Promise<AdminIntegration> {
  return runIntegrationAction(integrationType, "enable", "Unable to enable integration.");
}

export async function disableAdminIntegration(
  integrationType: IntegrationType,
): Promise<AdminIntegration> {
  return runIntegrationAction(integrationType, "disable", "Unable to disable integration.");
}

async function runIntegrationAction(
  integrationType: IntegrationType,
  action: "test" | "enable" | "disable",
  fallbackMessage: string,
): Promise<AdminIntegration> {
  const response = await fetch(`${apiBaseUrl}/api/admin/integrations/${integrationType}/${action}`, {
    method: "POST",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(await readError(response, fallbackMessage));
  }

  const payload = (await response.json()) as { integration: AdminIntegration };
  return payload.integration;
}

async function readError(response: Response, fallbackMessage: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? fallbackMessage;
  } catch {
    return fallbackMessage;
  }
}
