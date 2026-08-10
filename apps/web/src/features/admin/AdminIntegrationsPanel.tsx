"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  AdminIntegration,
  IntegrationType,
  disableAdminIntegration,
  enableAdminIntegration,
  listAdminIntegrations,
  testAdminIntegration,
  updateAdminIntegrationCredentials,
} from "@/features/admin/admin-integrations-api";

type FormState = Record<string, Record<string, string>>;
type PendingAction = `${IntegrationType}:${"save" | "test" | "enable" | "disable"}`;

export function AdminIntegrationsPanel() {
  const [integrations, setIntegrations] = useState<AdminIntegration[]>([]);
  const [activeIntegrationType, setActiveIntegrationType] = useState<IntegrationType | null>(null);
  const [formState, setFormState] = useState<FormState>({});
  const [loading, setLoading] = useState(true);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    listAdminIntegrations()
      .then((nextIntegrations) => {
        if (mounted) {
          setIntegrations(nextIntegrations);
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load integrations.");
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  const sortedIntegrations = useMemo(
    () => [...integrations].sort(sortIntegrations),
    [integrations],
  );

  const activeIntegration = useMemo(
    () =>
      sortedIntegrations.find(
        (integration) => integration.integration_type === activeIntegrationType,
      ) ?? sortedIntegrations[0],
    [activeIntegrationType, sortedIntegrations],
  );

  useEffect(() => {
    if (!sortedIntegrations.length) {
      setActiveIntegrationType(null);
      return;
    }

    if (
      !activeIntegrationType ||
      !sortedIntegrations.some(
        (integration) => integration.integration_type === activeIntegrationType,
      )
    ) {
      setActiveIntegrationType(sortedIntegrations[0].integration_type);
    }
  }, [activeIntegrationType, sortedIntegrations]);

  function updateField(integrationType: IntegrationType, fieldName: string, value: string) {
    setFormState((current) => ({
      ...current,
      [integrationType]: {
        ...(current[integrationType] ?? {}),
        [fieldName]: value,
      },
    }));
  }

  async function handleSave(
    event: FormEvent<HTMLFormElement>,
    integration: AdminIntegration,
  ) {
    event.preventDefault();
    const secrets = formState[integration.integration_type] ?? {};
    const nonEmptySecrets = Object.fromEntries(
      Object.entries(secrets).filter(([, value]) => value.trim().length > 0),
    );

    if (Object.keys(nonEmptySecrets).length === 0) {
      setError("Enter at least one credential value to save or rotate.");
      setNotice(null);
      return;
    }

    await runAction(integration.integration_type, "save", async () => {
      const savedIntegration = await updateAdminIntegrationCredentials(
        integration.integration_type,
        nonEmptySecrets,
      );
      setIntegrations((current) => upsertIntegration(current, savedIntegration));
      setFormState((current) => ({ ...current, [integration.integration_type]: {} }));
      setNotice(`${integration.display_name} credentials saved. Run readiness test before use.`);
    });
  }

  async function handleTest(integration: AdminIntegration) {
    await runAction(integration.integration_type, "test", async () => {
      const testedIntegration = await testAdminIntegration(integration.integration_type);
      setIntegrations((current) => upsertIntegration(current, testedIntegration));
      setNotice(`${integration.display_name} readiness test completed.`);
    });
  }

  async function handleEnable(integration: AdminIntegration) {
    await runAction(integration.integration_type, "enable", async () => {
      const enabledIntegration = await enableAdminIntegration(integration.integration_type);
      setIntegrations((current) => upsertIntegration(current, enabledIntegration));
      setNotice(`${integration.display_name} enabled.`);
    });
  }

  async function handleDisable(integration: AdminIntegration) {
    await runAction(integration.integration_type, "disable", async () => {
      const disabledIntegration = await disableAdminIntegration(integration.integration_type);
      setIntegrations((current) => upsertIntegration(current, disabledIntegration));
      setNotice(`${integration.display_name} disabled.`);
    });
  }

  async function runAction(
    integrationType: IntegrationType,
    action: "save" | "test" | "enable" | "disable",
    callback: () => Promise<void>,
  ) {
    setPendingAction(`${integrationType}:${action}`);
    setError(null);
    setNotice(null);
    try {
      await callback();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to update integration.");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="admin-team-panel admin-integrations-panel">
      {error ? <p className="workspace-error inline-error">{error}</p> : null}
      {notice ? <p className="metadata-save-notice">{notice}</p> : null}

      {loading ? <p className="muted-copy">Loading global integrations.</p> : null}

      {sortedIntegrations.length ? (
        <div className="integration-tabs" role="tablist" aria-label="Global integrations">
          {sortedIntegrations.map((integration) => (
            <button
              key={integration.integration_id}
              className={
                activeIntegration?.integration_type === integration.integration_type ? "active" : ""
              }
              type="button"
              role="tab"
              aria-selected={activeIntegration?.integration_type === integration.integration_type}
              onClick={() => setActiveIntegrationType(integration.integration_type)}
            >
              <span>{integration.display_name}</span>
              <strong className={`status-dot ${statusClass(integration.status)}`} aria-hidden="true" />
            </button>
          ))}
        </div>
      ) : null}

      <div className="integration-grid single-integration-grid">
        {activeIntegration ? (
          <form
            className="integration-card"
            key={activeIntegration.integration_id}
            onSubmit={(event) => handleSave(event, activeIntegration)}
          >
            <div className="integration-card-header">
              <div>
                <h3>{activeIntegration.display_name}</h3>
                <p>{activeIntegration.description}</p>
              </div>
              <span className={`status-pill ${statusClass(activeIntegration.status)}`}>
                {statusLabel(activeIntegration.status)}
              </span>
            </div>

            <div className="integration-health-row">
              <span>
                Required fields: {activeIntegration.required_configured_count}/
                {activeIntegration.required_field_count}
              </span>
              <span>Last test: {lastTestLabel(activeIntegration)}</span>
            </div>

            {activeIntegration.webhook_url ? (
              <div className="integration-webhook">
                <span>Webhook URL</span>
                <code>{activeIntegration.webhook_url}</code>
              </div>
            ) : null}

            <div className="integration-fields">
              {activeIntegration.fields.map((field) => (
                <div className="form-field" key={field.name}>
                  <label htmlFor={`${activeIntegration.integration_type}-${field.name}`}>
                    {field.label}
                  </label>
                  <input
                    id={`${activeIntegration.integration_type}-${field.name}`}
                    type={field.input_type === "text" ? "text" : "password"}
                    value={formState[activeIntegration.integration_type]?.[field.name] ?? ""}
                    onChange={(event) =>
                      updateField(activeIntegration.integration_type, field.name, event.target.value)
                    }
                    placeholder={
                      field.configured ? "Configured. Enter a new value to rotate." : "Required"
                    }
                    autoComplete="off"
                  />
                  <span className={field.configured ? "field-state configured" : "field-state"}>
                    {field.configured
                      ? `Configured${field.last_updated_at ? ` ${formatDate(field.last_updated_at)}` : ""}`
                      : "Not configured"}
                  </span>
                </div>
              ))}
            </div>

            {activeIntegration.last_error_summary ? (
              <p className="integration-error-note">{activeIntegration.last_error_summary}</p>
            ) : null}

            {activeIntegration.recent_test_runs.length > 0 ? (
              <div className="integration-recent-tests">
                <span>Recent health</span>
                <strong>{activeIntegration.recent_test_runs[0].result_summary}</strong>
              </div>
            ) : null}

            <div className="form-actions integration-actions">
              <button
                className="primary-action compact-action"
                type="submit"
                disabled={pendingAction === `${activeIntegration.integration_type}:save`}
              >
                {pendingAction === `${activeIntegration.integration_type}:save` ? "Saving" : "Save"}
              </button>
              <button
                className="secondary-action"
                type="button"
                onClick={() => handleTest(activeIntegration)}
                disabled={pendingAction === `${activeIntegration.integration_type}:test`}
              >
                {pendingAction === `${activeIntegration.integration_type}:test`
                  ? "Testing"
                  : "Test readiness"}
              </button>
              {activeIntegration.status === "enabled" ? (
                <button
                  className="ghost-action"
                  type="button"
                  onClick={() => handleDisable(activeIntegration)}
                  disabled={pendingAction === `${activeIntegration.integration_type}:disable`}
                >
                  Disable
                </button>
              ) : (
                <button
                  className="ghost-action"
                  type="button"
                  onClick={() => handleEnable(activeIntegration)}
                  disabled={pendingAction === `${activeIntegration.integration_type}:enable`}
                >
                  Enable
                </button>
              )}
            </div>
          </form>
        ) : null}
      </div>
    </div>
  );
}

function upsertIntegration(
  integrations: AdminIntegration[],
  savedIntegration: AdminIntegration,
): AdminIntegration[] {
  return integrations.map((integration) =>
    integration.integration_id === savedIntegration.integration_id ? savedIntegration : integration,
  );
}

function sortIntegrations(a: AdminIntegration, b: AdminIntegration): number {
  const aConfigured = isConfiguredIntegration(a);
  const bConfigured = isConfiguredIntegration(b);

  if (aConfigured !== bConfigured) {
    return aConfigured ? -1 : 1;
  }

  return a.display_name.localeCompare(b.display_name);
}

function isConfiguredIntegration(integration: AdminIntegration): boolean {
  return integration.status !== "not_configured";
}

function statusClass(status: AdminIntegration["status"]): string {
  if (status === "enabled") {
    return "active";
  }
  if (status === "error") {
    return "rejected";
  }
  if (status === "configured") {
    return "approved";
  }
  if (status === "disabled") {
    return "archived";
  }
  return "pending";
}

function statusLabel(status: AdminIntegration["status"]): string {
  const labels: Record<AdminIntegration["status"], string> = {
    not_configured: "Not configured",
    configured: "Configured",
    enabled: "Enabled",
    disabled: "Disabled",
    error: "Error",
  };
  return labels[status];
}

function lastTestLabel(integration: AdminIntegration): string {
  if (!integration.last_tested_at) {
    return "Not tested";
  }
  return `${integration.last_test_status === "succeeded" ? "Passed" : "Failed"} ${formatDate(
    integration.last_tested_at,
  )}`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
