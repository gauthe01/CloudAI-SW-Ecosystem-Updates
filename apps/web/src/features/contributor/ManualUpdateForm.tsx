"use client";

import { FormEvent, useState } from "react";

import {
  PartnerUpdate,
  createContributorManualUpdate,
} from "@/features/contributor/contributor-updates-api";

type ManualUpdateFormProps = {
  partnerId: string;
  cycle: string;
  cycleLabel: string;
  onCancel: () => void;
  onCreated: (update: PartnerUpdate) => void;
};

export function ManualUpdateForm({
  partnerId,
  cycle,
  cycleLabel,
  onCancel,
  onCreated,
}: ManualUpdateFormProps) {
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const update = await createContributorManualUpdate(partnerId, cycle, {
        title,
        summary,
      });
      setTitle("");
      setSummary("");
      onCreated(update);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to add manual update.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="manual-update-form" onSubmit={handleSubmit}>
      <div className="manual-update-heading">
        <div>
          <p className="eyebrow">{cycleLabel}</p>
          <h4>Manual Update</h4>
        </div>
        <button className="ghost-action" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>

      {error ? <p className="workspace-error inline-error">{error}</p> : null}

      <div className="form-field">
        <label htmlFor="manual-update-title">Title</label>
        <input
          id="manual-update-title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Short update title"
          required
        />
      </div>

      <div className="form-field">
        <label htmlFor="manual-update-summary">Summary</label>
        <textarea
          id="manual-update-summary"
          value={summary}
          onChange={(event) => setSummary(event.target.value)}
          placeholder="Write the update that should go into Pending Updates"
          rows={5}
          required
        />
      </div>

      <div className="form-actions">
        <button className="primary-action compact-action" type="submit" disabled={saving}>
          {saving ? "Adding" : "Add to Pending"}
        </button>
      </div>
    </form>
  );
}
