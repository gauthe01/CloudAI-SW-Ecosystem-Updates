"use client";

import { Dispatch, ReactNode, SetStateAction, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { GlobalLoader } from "@/components/foundation/GlobalLoader";
import { AccountMenu } from "@/components/navigation/AccountMenu";
import { AppTopNav } from "@/components/navigation/AppTopNav";
import { PartnerNavSelect } from "@/components/navigation/PartnerNavSelect";
import { PresenterPartnerNavSelect } from "@/components/navigation/PresenterPartnerNavSelect";
import { SectionTabs } from "@/components/navigation/SectionTabs";
import { AdminControlPlanePanel } from "@/features/admin/AdminControlPlanePanel";
import { AdminIntegrationsPanel } from "@/features/admin/AdminIntegrationsPanel";
import { AdminPartnersPanel } from "@/features/admin/AdminPartnersPanel";
import { AdminKnowledgeUploadPanel } from "@/features/admin/AdminKnowledgeUploadPanel";
import { AdminSourceApprovalsPanel } from "@/features/admin/AdminSourceApprovalsPanel";
import { AdminTeamPanel } from "@/features/admin/AdminTeamPanel";
import {
  AccountView,
  AuthContext,
  getCurrentAuthContext,
  logout,
  switchActiveView,
} from "@/features/auth/auth-api";
import { ContributorPartnerSelectionPanel } from "@/features/contributor/ContributorPartnerSelectionPanel";
import {
  ContributorPartner,
  listContributorPartners,
} from "@/features/contributor/contributor-partners-api";
import { PresenterWorkspacePanel } from "@/features/presenter/PresenterWorkspacePanel";
import {
  PresenterPartner,
  PresenterPeriodQuery,
  listPresenterPartners,
} from "@/features/presenter/presenter-api";
import {
  adminSectionDisplayLabels,
  sectionLabels,
  viewLabels,
  viewOrder,
} from "@/features/shell/navigation";
import { productName } from "@/lib/product";
import { routes } from "@/lib/routes";

export function AccountViewShell() {
  const router = useRouter();
  const [authContext, setAuthContext] = useState<AuthContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [switchingView, setSwitchingView] = useState<AccountView | null>(null);
  const [activeSection, setActiveSection] = useState("Partner Metadata");
  const [error, setError] = useState<string | null>(null);
  const [contributorPartners, setContributorPartners] = useState<ContributorPartner[]>([]);
  const [selectedContributorPartnerId, setSelectedContributorPartnerId] = useState<string | null>(
    null,
  );
  const [contributorPartnersLoading, setContributorPartnersLoading] = useState(false);
  const [contributorPartnersError, setContributorPartnersError] = useState<string | null>(null);
  const [presenterPeriod, setPresenterPeriod] = useState<PresenterPeriodQuery>({
    cycle: currentCycle(),
    dateStart: null,
    dateEnd: null,
  });
  const [presenterPartners, setPresenterPartners] = useState<PresenterPartner[]>([]);
  const [selectedPresenterPartnerIds, setSelectedPresenterPartnerIds] = useState<string[]>([]);
  const [presenterPartnersLoading, setPresenterPartnersLoading] = useState(false);
  const [presenterAskAiOpen, setPresenterAskAiOpen] = useState(false);
  const [presenterEmailRequestKey, setPresenterEmailRequestKey] = useState(0);
  const [adminHeaderAction, setAdminHeaderAction] = useState<ReactNode | null>(null);

  useEffect(() => {
    let mounted = true;

    getCurrentAuthContext()
      .then((context) => {
        if (mounted) {
          setAuthContext(context);
        }
      })
      .catch(() => {
        router.replace(routes.login);
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [router]);

  const orderedViews = useMemo(() => {
    if (!authContext) {
      return [];
    }
    return viewOrder.filter((view) => authContext.available_views.includes(view));
  }, [authContext]);

  useEffect(() => {
    if (authContext?.active_view !== "contributor") {
      return;
    }

    let mounted = true;
    setContributorPartnersLoading(true);
    setContributorPartnersError(null);

    listContributorPartners()
      .then((partners) => {
        if (!mounted) {
          return;
        }
        setContributorPartners(partners);
        setSelectedContributorPartnerId((currentPartnerId) => {
          if (currentPartnerId && partners.some((partner) => partner.partner_id === currentPartnerId)) {
            return currentPartnerId;
          }
          return partners.length === 1 ? partners[0].partner_id : null;
        });
      })
      .catch((error) => {
        if (mounted) {
          setContributorPartnersError(
            error instanceof Error ? error.message : "Unable to load assigned partners.",
          );
          setContributorPartners([]);
          setSelectedContributorPartnerId(null);
        }
      })
      .finally(() => {
        if (mounted) {
          setContributorPartnersLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [authContext?.active_view]);

  useEffect(() => {
    if (authContext?.active_view !== "presenter") {
      return;
    }

    let mounted = true;
    setPresenterPartnersLoading(true);

    listPresenterPartners(presenterPeriod)
      .then((partners) => {
        if (!mounted) {
          return;
        }
        setPresenterPartners(partners);
        setSelectedPresenterPartnerIds((currentPartnerIds) =>
          currentPartnerIds.filter((partnerId) =>
            partners.some((partner) => partner.partner_id === partnerId),
          ),
        );
      })
      .catch(() => {
        if (mounted) {
          setPresenterPartners([]);
          setSelectedPresenterPartnerIds([]);
        }
      })
      .finally(() => {
        if (mounted) {
          setPresenterPartnersLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [authContext?.active_view, presenterPeriod]);

  async function handleSwitchView(view: AccountView) {
    if (!authContext || view === authContext.active_view) {
      return;
    }

    setError(null);
    setSwitchingView(view);
    try {
      const nextContext = await switchActiveView(view);
      setAuthContext(nextContext);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to switch account view.");
    } finally {
      setSwitchingView(null);
    }
  }

  async function handleLogout() {
    setError(null);
    try {
      await logout();
    } finally {
      router.replace(routes.login);
    }
  }

  if (loading) {
    return (
      <main className="workspace-shell loading-shell">
        <GlobalLoader
          label="Loading workspace"
          detail="Preparing your Cloud AI ecosystem view."
        />
      </main>
    );
  }

  if (!authContext) {
    return null;
  }

  const activeView = authContext.active_view;
  const activeSections = sectionLabels[activeView];
  const selectedSection = activeSections.includes(activeSection)
    ? activeSection
    : activeView === "presenter"
      ? "Partner Updates"
      : activeSections[0];
  const selectedSectionLabel =
    activeView === "admin"
      ? adminSectionDisplayLabels[selectedSection] ?? selectedSection
      : selectedSection;
  const isContributorView = activeView === "contributor";
  const isPresenterView = activeView === "presenter";
  const isAdminConsoleHome = activeView === "admin" && selectedSection === "Admin Console";
  const isContributorPartnerSelection =
    isContributorView && contributorPartners.length > 1 && !selectedContributorPartnerId;
  const contributorNavPartners = contributorPartners.map((partner) => ({
    id: partner.partner_id,
    name: partner.name,
    description: partner.description,
    updatesCount: partner.updates_count,
  }));
  const presenterNavPartners = presenterPartners.map((partner) => ({
    id: partner.partner_id,
    name: partner.name,
    description: partner.description,
    updatesCount: partner.approved_updates_count,
  }));

  return (
    <main
      className={
        isContributorPartnerSelection
          ? "workspace-shell contributor-view-shell contributor-selection-shell"
          : isContributorView
            ? "workspace-shell contributor-view-shell"
            : isPresenterView
              ? "workspace-shell presenter-view-shell"
              : "workspace-shell"
      }
    >
      <AppTopNav
        eyebrow={productName}
        context={
          isContributorView && selectedContributorPartnerId && contributorPartners.length ? (
            <PartnerNavSelect
              disabled={contributorPartnersLoading}
              partners={contributorNavPartners}
              selectedPartnerId={selectedContributorPartnerId}
              onSelect={setSelectedContributorPartnerId}
            />
          ) : isPresenterView && presenterPartners.length ? (
            <PresenterPartnerNavSelect
              disabled={presenterPartnersLoading}
              partners={presenterNavPartners}
              selectedPartnerIds={selectedPresenterPartnerIds}
              onApply={setSelectedPresenterPartnerIds}
            />
          ) : null
        }
        actions={
          <AccountMenu
            activeViewId={activeView}
            email={authContext.user.email}
            name={authContext.user.display_name}
            onSignOut={handleLogout}
            onSwitchView={handleSwitchView}
            switchingViewId={switchingView}
            views={orderedViews.map((view) => ({ id: view, label: viewLabels[view] }))}
          />
        }
      />

      {error ? <p className="workspace-error">{error}</p> : null}

      {isPresenterView ? (
        <PresenterSectionTabs
          activeSection={selectedSection}
          askAiOpen={presenterAskAiOpen}
          onEmailOpen={() => setPresenterEmailRequestKey((current) => current + 1)}
          onAskAiToggle={() => setPresenterAskAiOpen((current) => !current)}
          onChange={setActiveSection}
        />
      ) : !isContributorView && activeView !== "admin" ? (
        <SectionTabs
          activeTabId={selectedSection}
          ariaLabel={`${viewLabels[activeView]} sections`}
          onChange={setActiveSection}
          tabs={activeSections.map((section) => ({ id: section, label: section }))}
        />
      ) : null}

      <section
        className={
          isContributorPartnerSelection
            ? "workspace-content contributor-workspace-content contributor-selection-content"
            : isContributorView
            ? "workspace-content contributor-workspace-content"
            : isAdminConsoleHome
              ? "workspace-content admin-console-content"
              : "workspace-content"
        }
        aria-labelledby="workspace-content-title"
      >
        {isContributorView ? (
          <>
            <h2 id="workspace-content-title" className="visually-hidden">
              Contributor Dashboard
            </h2>
            <ContributorPartnerSelectionPanel
              error={contributorPartnersError}
              loading={contributorPartnersLoading}
              onSelectPartner={setSelectedContributorPartnerId}
              partners={contributorPartners}
              selectedPartnerId={selectedContributorPartnerId}
              userName={authContext.user.display_name}
            />
          </>
        ) : (
          <>
            {activeView === "admin" && !isAdminConsoleHome ? (
              <div className="admin-module-actions-row">
                <button
                  className="ghost-action"
                  type="button"
                  onClick={() => setActiveSection("Admin Console")}
                >
                  Back to Admin Console
                </button>
                {adminHeaderAction}
              </div>
            ) : null}
            {isPresenterView ? (
              <h2 id="workspace-content-title" className="visually-hidden">
                {selectedSectionLabel}
              </h2>
            ) : (
              <div className="workspace-heading-row">
                <div>
                  <p className="eyebrow">Current Workspace</p>
                  <h2 id="workspace-content-title">
                    {activeView === "admin" && !isAdminConsoleHome
                      ? `Admin Console - ${selectedSectionLabel}`
                      : selectedSectionLabel}
                  </h2>
                </div>
              </div>
            )}
            {isAdminConsoleHome ? (
              <AdminControlPlanePanel onSelectModule={setActiveSection} />
            ) : isPresenterView ? (
              <PresenterWorkspacePanel
                askAiOpen={presenterAskAiOpen}
                emailRequestKey={presenterEmailRequestKey}
                onAskAiClose={() => setPresenterAskAiOpen(false)}
                onPartnerSelectionChange={setSelectedPresenterPartnerIds}
                onPeriodChange={setPresenterPeriod}
                partners={presenterPartners}
                period={presenterPeriod}
                section={selectedSection}
                selectedPartnerIds={selectedPresenterPartnerIds}
              />
            ) : (
              renderWorkspaceContent(activeView, selectedSection, setAdminHeaderAction)
            )}
          </>
        )}
      </section>
    </main>
  );
}

const presenterMainTabs = ["Partner Updates", "Executive Summary", "Decision Board", "Event Calendar"];

function PresenterSectionTabs({
  activeSection,
  askAiOpen,
  onEmailOpen,
  onAskAiToggle,
  onChange,
}: {
  activeSection: string;
  askAiOpen: boolean;
  onEmailOpen: () => void;
  onAskAiToggle: () => void;
  onChange: (section: string) => void;
}) {
  return (
    <nav className="presenter-dashboard-tabs" aria-label="Presenter dashboard tabs">
      {presenterMainTabs.map((tab) => (
        <button
          key={tab}
          type="button"
          className={activeSection === tab ? "active" : ""}
          onClick={() => onChange(tab)}
        >
          <span>{tab}</span>
        </button>
      ))}
      <button
        type="button"
        className="presenter-email-tab-action"
        aria-label="Draft Email"
        title="Draft Email"
        onClick={onEmailOpen}
      >
        <svg className="presenter-email-icon" aria-hidden="true" viewBox="0 0 24 18">
          <path d="M2.75 2.25h18.5v13.5H2.75z" />
          <path d="m3.5 3 8.5 6.5L20.5 3" />
          <path d="m3.75 15 6.1-5.35" />
          <path d="m20.25 15-6.1-5.35" />
        </svg>
      </button>
      <button
        type="button"
        className={askAiOpen ? "presenter-tab-ask-ai active" : "presenter-tab-ask-ai"}
        onClick={onAskAiToggle}
      >
        <span className="presenter-ai-spark" aria-hidden="true" />
        <span>Ask AI</span>
      </button>
    </nav>
  );
}

function renderWorkspaceContent(
  activeView: AccountView,
  selectedSection: string,
  setAdminHeaderAction: Dispatch<SetStateAction<ReactNode | null>>,
) {
  if (activeView === "admin" && selectedSection === "Team") {
    return <AdminTeamPanel onHeaderActionChange={setAdminHeaderAction} />;
  }

  if (activeView === "admin" && selectedSection === "Partners") {
    return <AdminPartnersPanel onHeaderActionChange={setAdminHeaderAction} />;
  }

  if (activeView === "admin" && selectedSection === "Knowledge Upload") {
    return <AdminKnowledgeUploadPanel />;
  }

  if (activeView === "admin" && selectedSection === "Global Integrations") {
    return <AdminIntegrationsPanel />;
  }

  if (activeView === "admin" && selectedSection === "Source Approvals") {
    return <AdminSourceApprovalsPanel />;
  }

  return (
    <div className="workspace-empty-state">
      <span>{viewLabels[activeView]}</span>
      <strong>{selectedSection}</strong>
    </div>
  );
}

function currentCycle(): string {
  return new Date().toISOString().slice(0, 7);
}
