"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminPartner, listAdminPartners } from "@/features/admin/admin-partners-api";
import { KnowledgeUploadTable } from "@/features/uploads/KnowledgeUploadTable";
import {
  KnowledgeUpload,
  createAdminKnowledgeUpload,
  listAdminKnowledgeUploads,
} from "@/features/uploads/uploads-api";

export function AdminKnowledgeUploadPanel() {
  const [uploads, setUploads] = useState<KnowledgeUpload[]>([]);
  const [partners, setPartners] = useState<AdminPartner[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [partnerId, setPartnerId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    Promise.all([listAdminKnowledgeUploads(), listAdminPartners()])
      .then(([nextUploads, nextPartners]) => {
        if (mounted) {
          setUploads(nextUploads);
          setPartners(nextPartners.filter((partner) => partner.status === "active"));
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load knowledge uploads.");
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Choose a file to upload.");
      return;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const upload = await createAdminKnowledgeUpload({
        file,
        title,
        description,
        partnerId: partnerId || undefined,
      });
      setUploads((current) => [upload, ...current]);
      setTitle("");
      setDescription("");
      setPartnerId("");
      setFile(null);
      event.currentTarget.reset();
      setNotice("Knowledge file uploaded.");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to upload file.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="admin-team-panel">
      <div className="admin-panel-heading">
        <div>
          <p className="eyebrow">Admin Console</p>
          <h2>Knowledge Upload</h2>
        </div>
      </div>

      {error ? <p className="workspace-error inline-error">{error}</p> : null}
      {notice ? <p className="metadata-save-notice">{notice}</p> : null}

      <form className="team-form upload-form" onSubmit={handleSubmit}>
        <div className="form-field">
          <label htmlFor="admin-upload-file">File</label>
          <input
            id="admin-upload-file"
            type="file"
            accept=".txt,.md,.csv,.json,.log,.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            required
          />
        </div>

        <div className="form-field">
          <label htmlFor="admin-upload-title">Title</label>
          <input
            id="admin-upload-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Defaults to filename"
          />
        </div>

        <div className="form-field">
          <label htmlFor="admin-upload-partner">Partner</label>
          <select
            id="admin-upload-partner"
            value={partnerId}
            onChange={(event) => setPartnerId(event.target.value)}
          >
            <option value="">Global knowledge</option>
            {partners.map((partner) => (
              <option key={partner.partner_id} value={partner.partner_id}>
                {partner.name}
              </option>
            ))}
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="admin-upload-description">Description</label>
          <textarea
            id="admin-upload-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Optional context for future rulebook-driven processing"
            rows={3}
          />
        </div>

        <div className="form-actions">
          <button className="primary-action compact-action" type="submit" disabled={saving}>
            {saving ? "Uploading" : "Upload file"}
          </button>
        </div>
      </form>

      <KnowledgeUploadTable
        uploads={uploads}
        loading={loading}
        emptyLabel="No knowledge uploads yet"
        showPartner
      />
    </div>
  );
}
