"use client";

import { useEffect, useMemo, useState } from "react";

import { listAdminConnectedSources } from "@/features/admin/admin-connected-sources-api";
import { listAdminIntegrations } from "@/features/admin/admin-integrations-api";
import { listAdminPartners } from "@/features/admin/admin-partners-api";
import {
  listAccountAccessRequests,
  listAdminUsers,
} from "@/features/admin/admin-users-api";
import { adminSectionDisplayLabels } from "@/features/shell/navigation";

type AdminControlPlanePanelProps = {
  onSelectModule: (moduleId: string) => void;
};

type AdminConsoleStats = {
  partners: number | null;
  users: number | null;
  pendingAccessRequests: number | null;
  enabledIntegrations: number | null;
  integrations: number | null;
  pendingSourceApprovals: number | null;
};

const emptyStats: AdminConsoleStats = {
  partners: null,
  users: null,
  pendingAccessRequests: null,
  enabledIntegrations: null,
  integrations: null,
  pendingSourceApprovals: null,
};

export function AdminControlPlanePanel({ onSelectModule }: AdminControlPlanePanelProps) {
  const [stats, setStats] = useState<AdminConsoleStats>(emptyStats);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    Promise.allSettled([
      listAdminPartners(),
      listAdminUsers(),
      listAccountAccessRequests(),
      listAdminIntegrations(),
      listAdminConnectedSources(),
    ])
      .then(([partners, users, accessRequests, integrations, connectedSources]) => {
        if (!mounted) {
          return;
        }

        setStats({
          partners: partners.status === "fulfilled" ? partners.value.length : null,
          users: users.status === "fulfilled" ? users.value.length : null,
          pendingAccessRequests:
            accessRequests.status === "fulfilled"
              ? accessRequests.value.filter((request) => request.status === "pending").length
              : null,
          enabledIntegrations:
            integrations.status === "fulfilled"
              ? integrations.value.filter((integration) => integration.status === "enabled").length
              : null,
          integrations: integrations.status === "fulfilled" ? integrations.value.length : null,
          pendingSourceApprovals:
            connectedSources.status === "fulfilled"
              ? connectedSources.value.filter((source) => source.review_bucket === "needs_review")
                  .length
              : null,
        });
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

  const cards = useMemo(
    () => [
      {
        id: "Partners",
        title: adminSectionDisplayLabels.Partners,
        description: "Add, edit, or archive partners",
        metric:
          stats.partners === null
            ? "Open partners"
            : `${stats.partners} ${stats.partners === 1 ? "partner" : "partners"}`,
        tone: "teal",
        iconLabel: "P",
      },
      {
        id: "Team",
        title: adminSectionDisplayLabels.Team,
        description: "Add members, set partner access, and manage roles",
        metric:
          stats.users === null
            ? "Open team"
            : `${stats.users} ${stats.users === 1 ? "member" : "members"}`,
        auxiliaryMetric:
          stats.pendingAccessRequests && stats.pendingAccessRequests > 0
            ? `${stats.pendingAccessRequests} pending access`
            : null,
        tone: "green",
        iconLabel: "T",
      },
      {
        id: "Global Integrations",
        title: adminSectionDisplayLabels["Global Integrations"],
        description: "Configure app integrations, webhooks, and sync health",
        metric:
          stats.enabledIntegrations === null || stats.integrations === null
            ? "Configure"
            : `${stats.enabledIntegrations} enabled of ${stats.integrations}`,
        tone: "green",
        iconLabel: "I",
      },
      {
        id: "Source Approvals",
        title: adminSectionDisplayLabels["Source Approvals"],
        description: "Review contributor connected-source requests",
        metric:
          stats.pendingSourceApprovals === null
            ? "Review queue"
            : `${stats.pendingSourceApprovals} ${
                stats.pendingSourceApprovals === 1 ? "request" : "requests"
              }`,
        tone: "blue",
        iconLabel: "S",
      },
      {
        id: "Knowledge Upload",
        title: adminSectionDisplayLabels["Knowledge Upload"],
        description: "Upload historical reports and supporting files",
        metric: "Open upload",
        tone: "purple",
        iconLabel: "K",
      },
    ],
    [stats],
  );

  return (
    <div className="admin-control-plane">
      <div className="admin-control-plane-copy">
        <p>
          Manage users, partners, knowledge, global integrations, and connected-source approvals
          from one workspace.
        </p>
      </div>

      <div className="admin-module-grid" aria-busy={loading}>
        {cards.map((card) => (
          <button
            key={card.id}
            className="admin-module-card"
            type="button"
            onClick={() => onSelectModule(card.id)}
          >
            <span className={`admin-module-icon ${card.tone}`} aria-hidden="true">
              {card.iconLabel}
            </span>
            <span className="admin-module-title">{card.title}</span>
            <span className="admin-module-description">{card.description}</span>
            <span className="admin-module-meta">
              {card.metric}
              <span aria-hidden="true">→</span>
            </span>
            {card.auxiliaryMetric ? (
              <span className="admin-module-auxiliary">{card.auxiliaryMetric}</span>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}
