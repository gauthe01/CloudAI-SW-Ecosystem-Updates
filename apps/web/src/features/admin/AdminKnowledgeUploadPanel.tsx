"use client";

import {
  type ClipboardEvent,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
  type MutableRefObject,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  AdminPartner,
  createAdminPartner,
  listAdminPartners,
} from "@/features/admin/admin-partners-api";
import { AdminUser, listAdminUsers } from "@/features/admin/admin-users-api";
import {
  KnowledgeUploadCandidate,
  KnowledgeUploadCommitResponse,
  KnowledgeUploadMappingDecision,
  KnowledgeUploadSessionDetail,
  applyAdminKnowledgeUploadMappings,
  commitAdminKnowledgeUploadSession,
  createAdminKnowledgeUploadSession,
  getAdminKnowledgeUploadSession,
  updateAdminKnowledgeUploadSessionCandidate,
} from "@/features/uploads/uploads-api";

type WizardStep = "upload" | "confirm" | "resolve" | "approve" | "commit" | "success";
type ResolveChoice = {
  action: KnowledgeUploadMappingDecision["action"] | "create_partner";
  partnerId: string;
  contributorUserId?: string;
  newPartnerName?: string;
};

type ToolbarCommand = "bold" | "italic" | "underline" | "insertOrderedList" | "insertUnorderedList";

type ActiveToolbarState = {
  bold: boolean;
  italic: boolean;
  underline: boolean;
  orderedList: boolean;
  unorderedList: boolean;
};

type LinkDialogState = {
  text: string;
  url: string;
  error: string | null;
};

const WIZARD_STEPS: Array<{ key: Exclude<WizardStep, "success">; label: string }> = [
  { key: "upload", label: "Upload" },
  { key: "confirm", label: "Confirm" },
  { key: "resolve", label: "Resolve" },
  { key: "approve", label: "Approve" },
  { key: "commit", label: "Commit" },
];

export function AdminKnowledgeUploadPanel() {
  const [partners, setPartners] = useState<AdminPartner[]>([]);
  const [contributors, setContributors] = useState<AdminUser[]>([]);
  const [sessionDetail, setSessionDetail] = useState<KnowledgeUploadSessionDetail | null>(null);
  const [commitResult, setCommitResult] = useState<KnowledgeUploadCommitResponse | null>(null);
  const [step, setStep] = useState<WizardStep>("upload");
  const [files, setFiles] = useState<File[]>([]);
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<Set<string>>(new Set());
  const [currentPartnerIndex, setCurrentPartnerIndex] = useState(0);
  const [resolveChoices, setResolveChoices] = useState<Record<string, ResolveChoice>>({});
  const [dragging, setDragging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reviewSaving, setReviewSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let mounted = true;

    Promise.all([listAdminPartners(), listAdminUsers()])
      .then(([nextPartners, nextUsers]) => {
        if (mounted) {
          setPartners(nextPartners.filter((partner) => partner.status === "active"));
          setContributors(
            nextUsers.filter(
              (user) => user.status === "active" && user.roles.includes("contributor"),
            ),
          );
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load knowledge upload data.");
        }
      })

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!sessionDetail?.unknown_labels.length || !partners.length) {
      return;
    }
    setResolveChoices((current) => {
      const next = { ...current };
      let changed = false;
      for (const label of sessionDetail.unknown_labels) {
        const existingPartner = findPartnerByLabel(label, partners);
        const choice = next[label];
        if (existingPartner && (!choice || (choice.action === "existing_partner" && !choice.partnerId))) {
          next[label] = {
            ...(choice ?? { action: "existing_partner", newPartnerName: label }),
            action: "existing_partner",
            partnerId: existingPartner.partner_id,
          };
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [partners, sessionDetail?.unknown_labels]);

  const activeCandidates = useMemo(
    () =>
      sessionDetail?.candidates.filter(
        (candidate) =>
          candidate.status !== "dismissed" &&
          candidate.status !== "skipped" &&
          candidate.review_status !== "likely_noise" &&
          candidate.review_status !== "duplicate",
      ) ?? [],
    [sessionDetail],
  );

  const approvableCandidates = useMemo(
    () =>
      activeCandidates.filter(
        (candidate) =>
          candidate.cycle_month &&
          (candidate.review_status === "ready" ||
            candidate.review_status === "topic_pending") &&
          (candidate.review_status === "topic_pending" || candidate.partner_id) &&
          (candidate.status === "pending" || candidate.status === "approved"),
      ),
    [activeCandidates],
  );

  const partnerGroups = useMemo(
    () => groupCandidatesByPartner(approvableCandidates),
    [approvableCandidates],
  );

  const approvedCandidates = useMemo(
    () =>
      approvableCandidates.filter((candidate) =>
        selectedCandidateIds.has(candidate.candidate_id),
      ),
    [approvableCandidates, selectedCandidateIds],
  );

  const currentGroup = partnerGroups[currentPartnerIndex] ?? null;

  async function handleAnalyze() {
    if (!files.length) {
      setError("Choose at least one DOCX, PPTX, or XLSX file.");
      return;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    setCommitResult(null);
    try {
      const detail = await createAdminKnowledgeUploadSession(files);
      setSessionDetail(detail);
      setSelectedCandidateIds(new Set());
      setCurrentPartnerIndex(0);
      setResolveChoices(defaultResolveChoices(detail.unknown_labels, partners));
      setNotice(`${detail.session.update_count} candidate update(s) extracted for review.`);
      setStep("confirm");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to analyze knowledge files.");
    } finally {
      setSaving(false);
    }
  }

  async function refreshSession(sessionId = sessionDetail?.session.session_id) {
    if (!sessionId) {
      return null;
    }
    const nextDetail = await getAdminKnowledgeUploadSession(sessionId);
    setSessionDetail(nextDetail);
    setSelectedCandidateIds((current) => {
      const eligibleIds = new Set(
        nextDetail.candidates
          .filter(
            (candidate) =>
              candidate.cycle_month &&
              (candidate.review_status === "ready" ||
                candidate.review_status === "topic_pending") &&
              (candidate.review_status === "topic_pending" || candidate.partner_id) &&
              (candidate.status === "pending" || candidate.status === "approved"),
          )
          .map((candidate) => candidate.candidate_id),
      );
      return new Set([...current].filter((candidateId) => eligibleIds.has(candidateId)));
    });
    return nextDetail;
  }

  async function handleResolveMappings() {
    if (!sessionDetail) {
      return;
    }
    const missingContributorLabel = sessionDetail.unknown_labels.find((label) => {
      const choice = resolveChoices[label];
      const requestedName = choice?.newPartnerName?.trim() || label;
      const existingPartner =
        findPartnerByLabel(requestedName, partners) ?? findPartnerByLabel(label, partners);
      return choice?.action === "create_partner" && !existingPartner && !choice.contributorUserId;
    });
    if (missingContributorLabel) {
      setError(`Choose an assigned contributor before creating ${missingContributorLabel}.`);
      return;
    }

    setReviewSaving(true);
    setError(null);
    try {
      const createdPartners: AdminPartner[] = [];
      const mappings: KnowledgeUploadMappingDecision[] = [];
      for (const label of sessionDetail.unknown_labels) {
        const choice = resolveChoices[label] ?? { action: "skip", partnerId: "" };
        if (choice.action === "create_partner") {
          const requestedName = choice.newPartnerName?.trim() || label;
          const existingPartner =
            findPartnerByLabel(requestedName, partners) ?? findPartnerByLabel(label, partners);
          if (existingPartner) {
            mappings.push({
              raw_label: label,
              action: "existing_partner",
              partner_id: existingPartner.partner_id,
            });
            continue;
          }
          const partner = await createAdminPartner({
            name: requestedName,
            description: null,
            assigned_contributor_user_ids: choice.contributorUserId
              ? [choice.contributorUserId]
              : [],
          });
          createdPartners.push(partner);
          mappings.push({
            raw_label: label,
            action: "existing_partner",
            partner_id: partner.partner_id,
          });
          continue;
        }
        mappings.push({
          raw_label: label,
          action: choice.action,
          partner_id: choice.action === "existing_partner" ? choice.partnerId || null : null,
        });
      }
      const nextDetail = await applyAdminKnowledgeUploadMappings(
        sessionDetail.session.session_id,
        mappings,
      );
      if (createdPartners.length) {
        setPartners((current) =>
          [...createdPartners, ...current].sort((left, right) =>
            left.name.localeCompare(right.name),
          ),
        );
      }
      setSessionDetail(nextDetail);
      setCurrentPartnerIndex(0);
      setStep("approve");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to resolve mappings.");
    } finally {
      setReviewSaving(false);
    }
  }

  async function handleCandidateChange(
    candidate: KnowledgeUploadCandidate,
    payload: {
      partner_id?: string | null;
      cycle_month?: string | null;
      summary?: string;
      status?: "pending" | "approved" | "dismissed";
    },
  ) {
    if (!sessionDetail) {
      return;
    }
    setReviewSaving(true);
    setError(null);
    try {
      const updated = await updateAdminKnowledgeUploadSessionCandidate(
        sessionDetail.session.session_id,
        candidate.candidate_id,
        {
          partner_id: payload.partner_id ?? candidate.partner_id,
          cycle_month: payload.cycle_month ?? candidate.cycle_month,
          summary: payload.summary ?? candidate.summary,
          status: payload.status,
        },
      );
      replaceCandidate(updated);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to update candidate.");
    } finally {
      setReviewSaving(false);
    }
  }

  async function handleToggleApproval(candidate: KnowledgeUploadCandidate) {
    const willApprove = !selectedCandidateIds.has(candidate.candidate_id);
    setSelectedCandidateIds((current) => {
      const next = new Set(current);
      if (willApprove) {
        next.add(candidate.candidate_id);
      } else {
        next.delete(candidate.candidate_id);
      }
      return next;
    });
    await handleCandidateChange(candidate, { status: willApprove ? "approved" : "pending" });
  }

  async function handleSkipCurrentPartner() {
    if (!currentGroup) {
      return;
    }
    const selectedInGroup = currentGroup.candidates.filter((candidate) =>
      selectedCandidateIds.has(candidate.candidate_id),
    );
    setSelectedCandidateIds((current) => {
      const next = new Set(current);
      for (const candidate of currentGroup.candidates) {
        next.delete(candidate.candidate_id);
      }
      return next;
    });
    await Promise.all(
      selectedInGroup.map((candidate) => handleCandidateChange(candidate, { status: "pending" })),
    );
    moveToNextPartnerOrCommit();
  }

  async function handleCommit() {
    if (!sessionDetail) {
      return;
    }
    const candidateIds = approvedCandidates.map((candidate) => candidate.candidate_id);
    if (!candidateIds.length) {
      setError("Approve at least one update before commit.");
      return;
    }
    setReviewSaving(true);
    setError(null);
    try {
      const response = await commitAdminKnowledgeUploadSession(
        sessionDetail.session.session_id,
        candidateIds,
      );
      setCommitResult(response);
      await refreshSession(sessionDetail.session.session_id);
      setNotice("Knowledge committed to approved updates and memory.");
      setStep("success");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to commit approved knowledge.");
    } finally {
      setReviewSaving(false);
    }
  }

  function replaceCandidate(updated: KnowledgeUploadCandidate) {
    setSessionDetail((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        candidates: current.candidates.map((candidate) =>
          candidate.candidate_id === updated.candidate_id ? updated : candidate,
        ),
      };
    });
  }

  function handleFilesChange(nextFiles: File[]) {
    const accepted = nextFiles.filter((file) => isSupportedKnowledgeFile(file));
    if (accepted.length !== nextFiles.length) {
      setError("Knowledge Upload supports DOCX, PPTX, and XLSX files.");
    } else {
      setError(null);
    }
    setFiles(accepted.slice(0, 7));
  }

  function moveToNextPartnerOrCommit() {
    if (currentPartnerIndex < partnerGroups.length - 1) {
      setCurrentPartnerIndex((index) => index + 1);
      return;
    }
    setStep("commit");
  }

  function resetWizard() {
    setSessionDetail(null);
    setCommitResult(null);
    setFiles([]);
    setSelectedCandidateIds(new Set());
    setCurrentPartnerIndex(0);
    setResolveChoices({});
    setNotice(null);
    setError(null);
    setStep("upload");
    fileInputRef.current?.form?.reset();
  }

  return (
    <div className="admin-team-panel knowledge-upload-workspace">
      {error ? <p className="workspace-error inline-error">{error}</p> : null}
      {notice ? <p className="metadata-save-notice">{notice}</p> : null}

      <div className="knowledge-upload-shell gold-wizard">
        <aside className="knowledge-upload-rail gold-stepper">
          {WIZARD_STEPS.map((item, index) => (
            <WizardStepItem
              active={step === item.key || (step === "success" && item.key === "commit")}
              complete={isStepComplete(item.key, step)}
              index={index + 1}
              key={item.key}
              label={item.label}
            />
          ))}
        </aside>

        <section className="knowledge-upload-main">
          {step === "upload" ? (
            <UploadStep
              dragging={dragging}
              fileInputRef={fileInputRef}
              files={files}
              loading={saving}
              onAnalyze={handleAnalyze}
              onDragStateChange={setDragging}
              onFilesChange={handleFilesChange}
              onRemoveFile={(fileName) =>
                setFiles((current) => current.filter((file) => file.name !== fileName))
              }
            />
          ) : null}

          {step === "confirm" && sessionDetail ? (
            <ConfirmStep
              detail={sessionDetail}
              onBack={() => setStep("upload")}
              onContinue={() => setStep(sessionDetail.unknown_labels.length ? "resolve" : "approve")}
            />
          ) : null}

          {step === "resolve" && sessionDetail ? (
            <ResolveStep
              choices={resolveChoices}
              contributors={contributors}
              detail={sessionDetail}
              disabled={reviewSaving}
              partners={partners}
              onBack={() => setStep("confirm")}
              onChoiceChange={(label, choice) =>
                setResolveChoices((current) => ({
                  ...current,
                  [label]: choice,
                }))
              }
              onResolve={handleResolveMappings}
            />
          ) : null}

          {step === "approve" && sessionDetail ? (
            <ApproveStep
              currentGroup={currentGroup}
              disabled={reviewSaving}
              groupIndex={currentPartnerIndex}
              groups={partnerGroups}
              partners={partners}
              selectedCandidateIds={selectedCandidateIds}
              onBack={() =>
                setStep(sessionDetail.unknown_labels.length ? "resolve" : "confirm")
              }
              onCandidateChange={handleCandidateChange}
              onContinue={moveToNextPartnerOrCommit}
              onSkipAll={handleSkipCurrentPartner}
              onToggleApproval={handleToggleApproval}
            />
          ) : null}

          {step === "commit" && sessionDetail ? (
            <CommitStep
              approvedCandidates={approvedCandidates}
              disabled={reviewSaving}
              detail={sessionDetail}
              onBack={() => setStep("approve")}
              onCommit={handleCommit}
            />
          ) : null}

          {step === "success" && commitResult ? (
            <SuccessStep
              result={commitResult}
              onAdminConsole={() => resetWizard()}
              onUploadAnother={resetWizard}
            />
          ) : null}
        </section>
      </div>
    </div>
  );
}

function WizardStepItem({
  active,
  complete,
  index,
  label,
}: {
  active: boolean;
  complete: boolean;
  index: number;
  label: string;
}) {
  return (
    <div className={`knowledge-step ${active ? "active" : ""} ${complete ? "complete" : ""}`}>
      <span>{complete ? "✓" : index}</span>
      <strong>{label}</strong>
    </div>
  );
}

function UploadStep({
  dragging,
  fileInputRef,
  files,
  loading,
  onAnalyze,
  onDragStateChange,
  onFilesChange,
  onRemoveFile,
}: {
  dragging: boolean;
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
  files: File[];
  loading: boolean;
  onAnalyze: () => void;
  onDragStateChange: (dragging: boolean) => void;
  onFilesChange: (files: File[]) => void;
  onRemoveFile: (fileName: string) => void;
}) {
  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    onFilesChange(Array.from(event.target.files ?? []));
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    onDragStateChange(false);
    onFilesChange(Array.from(event.dataTransfer.files));
  }

  return (
    <div className="knowledge-upload-card">
      <div className="knowledge-card-heading">
        <h3>Upload knowledge</h3>
        <p>Upload DOCX, PPTX, or XLSX files, then review every extracted update before committing.</p>
      </div>

      {loading ? (
        <div className="knowledge-analyzing-card">
          <div className="knowledge-document-icon">AI</div>
          <strong>Analyzing your files</strong>
          <span>Finding partner mentions...</span>
          <div className="knowledge-progress-bar">
            <span />
          </div>
        </div>
      ) : (
        <label
          className={`knowledge-dropzone ${dragging ? "dragging" : ""}`}
          htmlFor="admin-upload-files"
          onDragEnter={(event) => {
            event.preventDefault();
            onDragStateChange(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => onDragStateChange(false)}
          onDrop={handleDrop}
        >
          <span className="knowledge-drop-icon">↑</span>
          <strong>Drop DOCX, PPTX, or XLSX files here, or click to browse</strong>
          <span>The file type is detected automatically before review.</span>
          <input
            accept=".docx,.pptx,.xlsx"
            id="admin-upload-files"
            multiple
            ref={fileInputRef}
            type="file"
            onChange={handleInputChange}
          />
        </label>
      )}

      {files.length ? (
        <div className="knowledge-file-list">
          {files.map((file) => (
            <div className="knowledge-file-row" key={`${file.name}-${file.size}`}>
              <span className="knowledge-file-icon" />
              <div>
                <strong>{file.name}</strong>
                <span>{formatFileSize(file.size)} · Ready</span>
              </div>
              <button type="button" onClick={() => onRemoveFile(file.name)}>
                ×
              </button>
            </div>
          ))}
        </div>
      ) : null}

      <div className="knowledge-actions">
        <button
          className="metadata-save-action"
          disabled={!files.length || loading}
          type="button"
          onClick={onAnalyze}
        >
          {loading ? "Analyzing..." : "Analyze files →"}
        </button>
      </div>
    </div>
  );
}

function ConfirmStep({
  detail,
  onBack,
  onContinue,
}: {
  detail: KnowledgeUploadSessionDetail;
  onBack: () => void;
  onContinue: () => void;
}) {
  const session = detail.session;
  return (
    <div className="knowledge-upload-card">
      <div className="knowledge-card-heading">
        <h3>Confirm analysis</h3>
        <p>Check that everything looks right before continuing.</p>
      </div>

      <div className="knowledge-agent-message">
        <span>AI</span>
        <p>{session.summary ?? "I found candidate knowledge updates for review."}</p>
      </div>

      <div className="knowledge-fact-grid">
        <FactCard label="Document type" value={session.document_type ?? "Historical report"} />
        <FactCard label="Reporting period" value={displayMonth(session.inferred_cycle)} />
        <FactCard label="Updates found" value={String(session.update_count)} hint="updates ready for review" />
        <FactCard
          label="Partners"
          value={String(session.partner_count)}
          hint={`${session.unknown_name_count} unknown name${session.unknown_name_count === 1 ? "" : "s"}`}
        />
      </div>

      {session.warnings.length ? (
        <div className="knowledge-warning-box">
          {session.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}

      <div className="knowledge-footer-actions">
        <button className="ghost-action" type="button" onClick={onBack}>
          ← Back
        </button>
        <button className="metadata-save-action" type="button" onClick={onContinue}>
          Continue →
        </button>
      </div>
    </div>
  );
}

function ResolveStep({
  choices,
  contributors,
  detail,
  disabled,
  partners,
  onBack,
  onChoiceChange,
  onResolve,
}: {
  choices: Record<string, ResolveChoice>;
  contributors: AdminUser[];
  detail: KnowledgeUploadSessionDetail;
  disabled: boolean;
  partners: AdminPartner[];
  onBack: () => void;
  onChoiceChange: (label: string, choice: ResolveChoice) => void;
  onResolve: () => void;
}) {
  return (
    <div className="knowledge-upload-card">
      <div className="knowledge-card-heading">
        <h3>Resolve unknown names</h3>
        <p>Map unknown labels to configured partners or skip names that are not partner updates.</p>
      </div>

      <div className="knowledge-candidate-list">
        {detail.unknown_labels.map((label) => {
          const choice = choices[label] ?? { action: "existing_partner", partnerId: "" };
          return (
            <article className="knowledge-resolve-row" key={label}>
              <div>
                <strong>{label}</strong>
                <span>Found in extracted source evidence</span>
              </div>
              <select
                disabled={disabled}
                value={choice.action}
                onChange={(event) =>
                  onChoiceChange(label, {
                    ...choice,
                    action: event.target.value as ResolveChoice["action"],
                  })
                }
              >
                <option value="existing_partner">Map to existing partner</option>
                <option value="create_partner">Create partner</option>
                <option value="new_topic">Store in Events/Topics</option>
                <option value="skip">Skip as noise</option>
              </select>
              {choice.action === "create_partner" ? (
                <div className="knowledge-resolve-create-fields">
                  <input
                    disabled={disabled}
                    value={choice.newPartnerName ?? label}
                    onChange={(event) =>
                      onChoiceChange(label, {
                        ...choice,
                        newPartnerName: event.target.value,
                      })
                    }
                  />
                  <select
                    disabled={disabled}
                    value={choice.contributorUserId ?? ""}
                    onChange={(event) =>
                      onChoiceChange(label, {
                        ...choice,
                        contributorUserId: event.target.value,
                      })
                    }
                  >
                    <option value="">Assign contributor</option>
                    {contributors.map((contributor) => (
                      <option key={contributor.user_id} value={contributor.user_id}>
                        {contributor.display_name}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <select
                  disabled={disabled || choice.action !== "existing_partner"}
                  value={choice.partnerId}
                  onChange={(event) =>
                    onChoiceChange(label, {
                      ...choice,
                      partnerId: event.target.value,
                    })
                  }
                >
                  <option value="">Choose partner</option>
                  {partners.map((partner) => (
                    <option key={partner.partner_id} value={partner.partner_id}>
                      {partner.name}
                    </option>
                  ))}
                </select>
              )}
            </article>
          );
        })}
      </div>

      <div className="knowledge-footer-actions">
        <button className="ghost-action" disabled={disabled} type="button" onClick={onBack}>
          ← Back
        </button>
        <button className="metadata-save-action" disabled={disabled} type="button" onClick={onResolve}>
          Resolve and continue →
        </button>
      </div>
    </div>
  );
}

function ApproveStep({
  currentGroup,
  disabled,
  groupIndex,
  groups,
  partners,
  selectedCandidateIds,
  onBack,
  onCandidateChange,
  onContinue,
  onSkipAll,
  onToggleApproval,
}: {
  currentGroup: CandidatePartnerGroup | null;
  disabled: boolean;
  groupIndex: number;
  groups: CandidatePartnerGroup[];
  partners: AdminPartner[];
  selectedCandidateIds: Set<string>;
  onBack: () => void;
  onCandidateChange: (
    candidate: KnowledgeUploadCandidate,
    payload: { partner_id?: string | null; cycle_month?: string | null; summary?: string },
  ) => void;
  onContinue: () => void;
  onSkipAll: () => void;
  onToggleApproval: (candidate: KnowledgeUploadCandidate) => void;
}) {
  const approvedCount = groups.flatMap((group) => group.candidates).filter((candidate) =>
    selectedCandidateIds.has(candidate.candidate_id),
  ).length;

  return (
    <div className="knowledge-upload-card">
      <div className="knowledge-card-heading horizontal">
        <div>
          <h3>Approve updates</h3>
          <p>Select the updates to include. Nothing is added to the knowledge base until final commit.</p>
        </div>
        <span className="knowledge-approved-pill">{approvedCount} approved</span>
      </div>

      {!currentGroup ? (
        <div className="knowledge-empty">
          <strong>No ready updates</strong>
          <span>Resolve partner and reporting period mappings before approval.</span>
        </div>
      ) : (
        <section className="knowledge-candidate-group approval-group">
          <div className="knowledge-candidate-group-heading">
            <div>
              <strong>{currentGroup.partnerName}</strong>
              <span>
                {currentGroup.isTopic ? "Global group" : "Partner"} {groupIndex + 1} of {groups.length}
              </span>
            </div>
            <span>{currentGroup.candidates.length} update{currentGroup.candidates.length === 1 ? "" : "s"}</span>
          </div>

          {currentGroup.candidates.map((candidate) => (
            <CandidateReviewCard
              candidate={candidate}
              disabled={disabled}
              key={candidate.candidate_id}
              partners={partners}
              selected={selectedCandidateIds.has(candidate.candidate_id)}
              onCandidateChange={onCandidateChange}
              onToggleApproval={onToggleApproval}
            />
          ))}
        </section>
      )}

      <div className="knowledge-footer-actions">
        <button className="ghost-action" disabled={disabled} type="button" onClick={onBack}>
          ← Back
        </button>
        {currentGroup ? (
          <button className="ghost-action" disabled={disabled} type="button" onClick={onSkipAll}>
            Skip all →
          </button>
        ) : null}
        <button
          className="metadata-save-action"
          disabled={disabled || !currentGroup}
          type="button"
          onClick={onContinue}
        >
          {groupIndex < groups.length - 1 ? "Continue →" : "Ready to commit →"}
        </button>
      </div>
    </div>
  );
}

function CandidateReviewCard({
  candidate,
  disabled,
  partners,
  selected,
  onCandidateChange,
  onToggleApproval,
}: {
  candidate: KnowledgeUploadCandidate;
  disabled: boolean;
  partners: AdminPartner[];
  selected: boolean;
  onCandidateChange: (
    candidate: KnowledgeUploadCandidate,
    payload: { partner_id?: string | null; cycle_month?: string | null; summary?: string },
  ) => void;
  onToggleApproval: (candidate: KnowledgeUploadCandidate) => void;
}) {
  const isTopicCandidate = candidate.review_status === "topic_pending";
  return (
    <article className={`knowledge-candidate ${selected ? "approved" : ""}`}>
      <label className="knowledge-candidate-check">
        <input
          checked={selected}
          disabled={
            disabled ||
            !(
              candidate.review_status === "ready" ||
              candidate.review_status === "topic_pending"
            )
          }
          type="checkbox"
          onChange={() => onToggleApproval(candidate)}
        />
      </label>

      <div className="knowledge-candidate-body">
        <div className="knowledge-candidate-topline">
          <div className="knowledge-candidate-meta">
            <span className={`status-pill ${selected ? "approved" : candidate.status}`}>
              {displayCandidateStatus(selected ? "approved" : candidate.status)}
            </span>
          </div>
        </div>

        <CandidateSummaryEditor
          candidate={candidate}
          disabled={disabled}
          onChange={(summary) => onCandidateChange(candidate, { summary })}
        />

        <div className="knowledge-candidate-controls">
          {isTopicCandidate ? (
            <label>
              <span>Store under</span>
              <input disabled readOnly value={topicCandidateLabel(candidate)} />
            </label>
          ) : (
            <label>
              <span>Partner</span>
              <select
                disabled={disabled}
                value={candidate.partner_id ?? ""}
                onChange={(event) =>
                  onCandidateChange(candidate, {
                    partner_id: event.target.value || null,
                  })
                }
              >
                <option value="">Map partner</option>
                {partners.map((partner) => (
                  <option key={partner.partner_id} value={partner.partner_id}>
                    {partner.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label>
            <span>Cycle</span>
            <input
              disabled={disabled}
              type="month"
              value={toMonthInput(candidate.cycle_month)}
              onChange={(event) =>
                onCandidateChange(candidate, {
                  cycle_month: fromMonthInput(event.target.value),
                })
              }
            />
          </label>
        </div>

        {candidate.parser_notes ? <p className="knowledge-parser-note">{candidate.parser_notes}</p> : null}

      </div>
    </article>
  );
}

function CandidateSummaryEditor({
  candidate,
  disabled,
  onChange,
}: {
  candidate: KnowledgeUploadCandidate;
  disabled: boolean;
  onChange: (summary: string) => void;
}) {
  const editorRef = useRef<HTMLDivElement | null>(null);
  const selectedRangeRef = useRef<Range | null>(null);
  const [activeToolbar, setActiveToolbar] = useState<ActiveToolbarState>({
    bold: false,
    italic: false,
    underline: false,
    orderedList: false,
    unorderedList: false,
  });
  const [linkDialog, setLinkDialog] = useState<LinkDialogState | null>(null);

  useEffect(() => {
    if (!editorRef.current) {
      return;
    }
    editorRef.current.innerHTML = summaryToEditorHtml(candidate.summary, candidate.source_url);
    updateActiveToolbar();
  }, [candidate.candidate_id, candidate.updated_at, candidate.summary, candidate.source_url]);

  function syncEditorState() {
    rememberSelectedRange();
    updateActiveToolbar();
  }

  function rememberSelectedRange() {
    const range = getSelectedEditorRange();
    if (range) {
      selectedRangeRef.current = range;
    }
  }

  function updateActiveToolbar() {
    setActiveToolbar({
      bold: document.queryCommandState("bold"),
      italic: document.queryCommandState("italic"),
      underline: document.queryCommandState("underline"),
      orderedList: document.queryCommandState("insertOrderedList"),
      unorderedList: document.queryCommandState("insertUnorderedList"),
    });
  }

  function applyCommand(command: ToolbarCommand) {
    const selectedRange = getSelectedEditorRange() ?? selectedRangeRef.current;
    const isListCommand = command === "insertOrderedList" || command === "insertUnorderedList";
    if (isListCommand) {
      if (selectedRange && !selectedRange.collapsed) {
        restoreEditorRange(selectedRange);
      } else {
        editorRef.current?.focus();
      }
      document.execCommand(command, false);
      commitEditorChange();
      return;
    }

    if (!selectedRange || selectedRange.collapsed) {
      editorRef.current?.focus();
      return;
    }

    restoreEditorRange(selectedRange);
    document.execCommand(command, false);
    commitEditorChange();
  }

  function openLinkDialog() {
    const selectedRange = getSelectedEditorRange() ?? selectedRangeRef.current;
    if (!selectedRange || selectedRange.collapsed) {
      editorRef.current?.focus();
      return;
    }

    selectedRangeRef.current = selectedRange;
    setLinkDialog({
      text: selectedRange.toString(),
      url: "",
      error: null,
    });
  }

  function applyLinkDialog() {
    if (!linkDialog || !selectedRangeRef.current) {
      return;
    }
    const href = normalizeHref(linkDialog.url);
    const text = linkDialog.text.trim();
    if (!text || !href) {
      setLinkDialog({
        ...linkDialog,
        error: !text ? "Link text cannot be empty." : "Enter a valid URL or file path.",
      });
      return;
    }

    restoreEditorRange(selectedRangeRef.current);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    anchor.textContent = text;
    selectedRangeRef.current.deleteContents();
    selectedRangeRef.current.insertNode(anchor);
    selectedRangeRef.current.setStartAfter(anchor);
    selectedRangeRef.current.collapse(true);
    restoreEditorRange(selectedRangeRef.current);
    setLinkDialog(null);
    commitEditorChange();
  }

  function commitEditorChange() {
    const editor = editorRef.current;
    if (!editor) {
      return;
    }
    syncEditorState();
    const nextSummary = editor.innerHTML.trim();
    if (nextSummary && nextSummary !== summaryToEditorHtml(candidate.summary, candidate.source_url)) {
      onChange(nextSummary);
    }
  }

  function getSelectedEditorRange(): Range | null {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection || selection.rangeCount === 0 || selection.isCollapsed) {
      return null;
    }
    const range = selection.getRangeAt(0);
    const anchorNode = selection.anchorNode;
    const focusNode = selection.focusNode;
    if (
      !anchorNode ||
      !focusNode ||
      (!editor.contains(anchorNode) && anchorNode !== editor) ||
      (!editor.contains(focusNode) && focusNode !== editor)
    ) {
      return null;
    }
    return range.cloneRange();
  }

  function restoreEditorRange(range: Range) {
    const selection = window.getSelection();
    if (!selection) {
      return;
    }
    editorRef.current?.focus();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function insertAnchorAtSelection(label: string, href: string) {
    const selectedRange = getSelectedEditorRange();
    const editor = editorRef.current;
    if (!editor) {
      return;
    }

    if (selectedRange) {
      restoreEditorRange(selectedRange);
    } else {
      editor.focus();
    }
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    anchor.textContent = label;
    const selection = window.getSelection();
    const range = selection?.rangeCount ? selection.getRangeAt(0) : document.createRange();
    if (!selection?.rangeCount) {
      range.selectNodeContents(editor);
      range.collapse(false);
    }
    range.deleteContents();
    range.insertNode(anchor);
    range.setStartAfter(anchor);
    range.collapse(true);
    restoreEditorRange(range);
  }

  function handlePaste(event: ClipboardEvent<HTMLDivElement>) {
    const pastedText = event.clipboardData.getData("text/plain").trim();
    const href = normalizeHref(pastedText);
    if (!href) {
      return;
    }
    event.preventDefault();
    insertAnchorAtSelection(linkLabelFromHref(href), href);
    commitEditorChange();
  }

  function handleLinkDialogKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    applyLinkDialog();
  }

  return (
    <div className={`knowledge-rich-editor${linkDialog ? " link-open" : ""}`}>
      <div className="add-update-rte-toolbar knowledge-rte-toolbar" aria-label="Text formatting toolbar">
        <button
          className={activeToolbar.bold ? "active" : ""}
          disabled={disabled}
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => applyCommand("bold")}
          aria-label="Bold"
          title="Bold"
        >
          B
        </button>
        <button
          className={`italic${activeToolbar.italic ? " active" : ""}`}
          disabled={disabled}
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => applyCommand("italic")}
          aria-label="Italic"
          title="Italic"
        >
          I
        </button>
        <button
          className={`underline${activeToolbar.underline ? " active" : ""}`}
          disabled={disabled}
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => applyCommand("underline")}
          aria-label="Underline"
          title="Underline"
        >
          U
        </button>
        <span className="add-update-toolbar-separator" aria-hidden="true" />
        <button
          className={activeToolbar.orderedList ? "active" : ""}
          disabled={disabled}
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => applyCommand("insertOrderedList")}
          aria-label="Numbered list"
          title="Numbered list"
        >
          1.
        </button>
        <button
          className={activeToolbar.unorderedList ? "active" : ""}
          disabled={disabled}
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => applyCommand("insertUnorderedList")}
          aria-label="Bulleted list"
          title="Bulleted list"
        >
          <BulletListIcon />
        </button>
        <button
          className={linkDialog ? "active" : ""}
          disabled={disabled}
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={openLinkDialog}
          aria-label="Attach link"
          title="Attach link"
        >
          <LinkIcon />
        </button>
      </div>
      <div
        ref={editorRef}
        className="add-update-summary-editor knowledge-summary-editor"
        contentEditable={!disabled}
        role="textbox"
        aria-multiline="true"
        aria-label="Extracted update"
        onInput={syncEditorState}
        onBlur={commitEditorChange}
        onKeyUp={syncEditorState}
        onMouseUp={syncEditorState}
        onPaste={handlePaste}
        suppressContentEditableWarning
      />
      {linkDialog ? (
        <div className="add-update-link-popover knowledge-link-popover" role="dialog" aria-label="Add hyperlink">
          <div className="add-update-link-title">Add hyperlink</div>
          <label>
            <span>Link text</span>
            <input
              value={linkDialog.text}
              onChange={(event) =>
                setLinkDialog({ ...linkDialog, text: event.target.value, error: null })
              }
              onKeyDown={handleLinkDialogKeyDown}
              maxLength={200}
            />
          </label>
          <label>
            <span>URL or file path</span>
            <input
              value={linkDialog.url}
              onChange={(event) =>
                setLinkDialog({ ...linkDialog, url: event.target.value, error: null })
              }
              onKeyDown={handleLinkDialogKeyDown}
              maxLength={2000}
              placeholder="https:// or paste a file URL..."
              autoFocus
            />
          </label>
          {linkDialog.error ? <p>{linkDialog.error}</p> : null}
          <div className="add-update-link-actions">
            <button type="button" onClick={() => setLinkDialog(null)}>
              Cancel
            </button>
            <button className="primary" type="button" onClick={applyLinkDialog}>
              Apply link
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function CommitStep({
  approvedCandidates,
  detail,
  disabled,
  onBack,
  onCommit,
}: {
  approvedCandidates: KnowledgeUploadCandidate[];
  detail: KnowledgeUploadSessionDetail;
  disabled: boolean;
  onBack: () => void;
  onCommit: () => void;
}) {
  const rows = groupApprovedSummary(approvedCandidates);
  return (
    <div className="knowledge-upload-card">
      <div className="knowledge-card-heading">
        <h3>Ready to commit</h3>
        <p>Review the summary below, then commit to add these updates to the knowledge base.</p>
      </div>

      <div className="knowledge-summary-table">
        <div className="knowledge-summary-row header">
          <span>Partner</span>
          <span>Updates approved</span>
          <span>Status</span>
        </div>
        {rows.length ? (
          rows.map((row) => (
            <div className="knowledge-summary-row" key={row.partnerId}>
              <span>{row.partnerName}</span>
              <span>
                {row.count} update{row.count === 1 ? "" : "s"}
              </span>
              <span className="knowledge-ready-pill">Ready</span>
            </div>
          ))
        ) : (
          <div className="knowledge-empty-row">No approved updates selected.</div>
        )}
      </div>

      <div className="knowledge-rulebook-note">
        Rulebook trace: {detail.session.rulebook_name} · {detail.session.rulebook_version}
      </div>

      <div className="knowledge-footer-actions">
        <button className="ghost-action" disabled={disabled} type="button" onClick={onBack}>
          ← Back
        </button>
        <button
          className="metadata-save-action"
          disabled={disabled || !rows.length}
          type="button"
          onClick={onCommit}
        >
          {disabled ? "Committing..." : "Commit knowledge →"}
        </button>
      </div>
    </div>
  );
}

function SuccessStep({
  result,
  onAdminConsole,
  onUploadAnother,
}: {
  result: KnowledgeUploadCommitResponse;
  onAdminConsole: () => void;
  onUploadAnother: () => void;
}) {
  const partnersCovered = result.partner_summaries.length;
  return (
    <div className="knowledge-upload-card knowledge-success-card">
      <div className="knowledge-success-icon">✓</div>
      <h3>Knowledge committed</h3>
      <p>
        Knowledge from {partnersCovered} partner{partnersCovered === 1 ? "" : "s"}
        {result.topic_summaries.length ? " plus Events/Topics" : ""} has been added to the knowledge base and is now searchable in the presenter assistant.
      </p>
      <div className="knowledge-success-metrics">
        <FactCard label="Updates added" value={String(result.committed_count)} />
        <FactCard label="Partners covered" value={String(partnersCovered)} />
        {result.topic_summaries.length ? (
          <FactCard
            label="Events/Topics"
            value={String(result.topic_summaries.reduce((sum, row) => sum + row.updates_approved, 0))}
          />
        ) : null}
        <FactCard label="Reporting period" value={displayMonth(result.session.inferred_cycle)} />
      </div>
      <div className="knowledge-footer-actions">
        <button className="ghost-action" type="button" onClick={onUploadAnother}>
          Upload another file
        </button>
        <button className="metadata-save-action" type="button" onClick={onAdminConsole}>
          Go to Admin console →
        </button>
      </div>
    </div>
  );
}

function FactCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="knowledge-fact-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <em>{hint}</em> : null}
    </div>
  );
}

type CandidatePartnerGroup = {
  partnerId: string;
  partnerName: string;
  isTopic?: boolean;
  candidates: KnowledgeUploadCandidate[];
};

function groupCandidatesByPartner(candidates: KnowledgeUploadCandidate[]): CandidatePartnerGroup[] {
  const groups = new Map<string, CandidatePartnerGroup>();
  for (const candidate of candidates) {
    const isTopic = candidate.review_status === "topic_pending";
    const topicLabel = topicCandidateLabel(candidate);
    const partnerId = isTopic ? `topic:${topicLabel}` : candidate.partner_id ?? "unknown";
    const partnerName = isTopic
      ? topicLabel
      : candidate.partner_name ?? candidate.raw_label ?? "Needs partner mapping";
    const group = groups.get(partnerId) ?? {
      partnerId,
      partnerName,
      isTopic,
      candidates: [],
    };
    group.candidates.push(candidate);
    groups.set(partnerId, group);
  }
  return [...groups.values()].sort((left, right) => left.partnerName.localeCompare(right.partnerName));
}

function groupApprovedSummary(candidates: KnowledgeUploadCandidate[]) {
  const groups = new Map<string, { partnerId: string; partnerName: string; count: number }>();
  for (const candidate of candidates) {
    const isTopic = candidate.review_status === "topic_pending";
    const topicLabel = topicCandidateLabel(candidate);
    const partnerId = isTopic ? `topic:${topicLabel}` : candidate.partner_id;
    const partnerName = isTopic ? topicLabel : candidate.partner_name;
    if (!partnerId || !partnerName) {
      continue;
    }
    const group = groups.get(partnerId) ?? {
      partnerId,
      partnerName,
      count: 0,
    };
    group.count += 1;
    groups.set(partnerId, group);
  }
  return [...groups.values()].sort((left, right) => left.partnerName.localeCompare(right.partnerName));
}

function topicCandidateLabel(candidate: KnowledgeUploadCandidate) {
  return candidate.raw_label?.trim() || "Events/Topics";
}

function defaultResolveChoices(
  labels: string[],
  partners: AdminPartner[],
): Record<string, ResolveChoice> {
  return Object.fromEntries(
    labels.map((label) => {
      const existingPartner = findPartnerByLabel(label, partners);
      return [
        label,
        {
          action: "existing_partner",
          partnerId: existingPartner?.partner_id ?? "",
          newPartnerName: label,
        },
      ];
    }),
  );
}

function findPartnerByLabel(label: string, partners: AdminPartner[]) {
  const normalizedLabel = normalizePartnerLabel(label);
  if (!normalizedLabel) {
    return null;
  }
  return (
    partners.find((partner) => normalizePartnerLabel(partner.name) === normalizedLabel) ?? null
  );
}

function normalizePartnerLabel(label: string) {
  return label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function isStepComplete(step: Exclude<WizardStep, "success">, current: WizardStep) {
  const currentIndex =
    current === "success"
      ? WIZARD_STEPS.length
      : WIZARD_STEPS.findIndex((item) => item.key === current);
  const stepIndex = WIZARD_STEPS.findIndex((item) => item.key === step);
  return stepIndex >= 0 && currentIndex > stepIndex;
}

function isSupportedKnowledgeFile(file: File) {
  return /\.(docx|pptx|xlsx)$/i.test(file.name);
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function displayMonth(value: string | null) {
  if (!value) {
    return "Unknown";
  }
  const [year, month] = value.slice(0, 7).split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return new Intl.DateTimeFormat("en", { month: "short", year: "numeric" }).format(date);
}

function toMonthInput(value: string | null) {
  return value ? value.slice(0, 7) : "";
}

function fromMonthInput(value: string) {
  return value ? `${value}-01` : null;
}

function displayCandidateStatus(status: string) {
  return status
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function summaryToEditorHtml(summary: string, sourceUrl?: string | null) {
  const trimmed = summary.trim();
  if (!trimmed) {
    return "";
  }
  if (looksLikeHtml(trimmed)) {
    return trimmed;
  }
  const html = plainTextToDocumentHtml(trimmed);
  if (!sourceUrl || /<a[\s>]/i.test(html)) {
    return html;
  }
  const words = trimmed.replace(/\s+/g, " ").split(" ");
  if (words.length <= 5 || /\b(tracker|readout|deck|link)\b/i.test(trimmed)) {
    return `<p><a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(trimmed)}</a></p>`;
  }
  return html;
}

function looksLikeHtml(value: string) {
  return /<\/?[a-z][\s\S]*>/i.test(value);
}

function plainTextToDocumentHtml(value: string) {
  const lines = value.split("\n").map((line) => line.trimEnd()).filter(Boolean);
  let html = "";
  let listOpen = false;
  for (const line of lines) {
    const bullet = line.match(/^\s*[-•]\s+(.+)$/);
    if (bullet) {
      if (!listOpen) {
        html += "<ul>";
        listOpen = true;
      }
      html += `<li>${escapeHtml(bullet[1])}</li>`;
      continue;
    }
    if (listOpen) {
      html += "</ul>";
      listOpen = false;
    }
    html += `<p>${escapeHtml(line)}</p>`;
  }
  if (listOpen) {
    html += "</ul>";
  }
  return html;
}

function normalizeHref(value: string): string {
  const cleaned = value.trim();
  if (!cleaned) {
    return "";
  }
  if (/^(https?:\/\/|mailto:|\/|#)/i.test(cleaned)) {
    return cleaned;
  }
  if (/^[^\s@]+\.[^\s@]+/.test(cleaned)) {
    return `https://${cleaned}`;
  }
  return "";
}

function linkLabelFromHref(href: string): string {
  const clean = href.split("?")[0].split("#")[0];
  const fallback = href.startsWith("#") ? href.slice(1) : href;
  const lastPart = clean.split("/").filter(Boolean).pop() ?? fallback;
  try {
    return decodeURIComponent(lastPart) || href;
  } catch {
    return lastPart || href;
  }
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character] ?? character;
  });
}

function LinkIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path
        d="M10.6 13.4a2 2 0 0 0 2.8 0L17 9.9a3 3 0 0 0-4.2-4.3l-1.5 1.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M13.4 10.6a2 2 0 0 0-2.8 0L7 14.1a3 3 0 0 0 4.2 4.3l1.5-1.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function BulletListIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path
        d="M8 7h11M8 12h11M8 17h11"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M4.5 7h.01M4.5 12h.01M4.5 17h.01"
        stroke="currentColor"
        strokeWidth="3.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
