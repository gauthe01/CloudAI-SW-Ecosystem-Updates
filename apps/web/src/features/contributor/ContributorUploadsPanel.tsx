"use client";

import { FormEvent, useEffect, useState } from "react";

import { KnowledgeUploadTable } from "@/features/uploads/KnowledgeUploadTable";
import {
  KnowledgeUpload,
  createContributorPartnerUpload,
  listContributorPartnerUploads,
} from "@/features/uploads/uploads-api";

type ContributorUploadsPanelProps = {
  partnerId: string;
};

export function ContributorUploadsPanel({ partnerId }: ContributorUploadsPanelProps) {
  const [uploads, setUploads] = useState<KnowledgeUpload[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    setNotice(null);

    listContributorPartnerUploads(partnerId)
      .then((nextUploads) => {
        if (mounted) {
          setUploads(nextUploads);
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load partner files.");
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
  }, [partnerId]);

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
      const upload = await createContributorPartnerUpload(partnerId, {
        file,
        title,
        description,
      });
      setUploads((current) => [upload, ...current]);
      setTitle("");
      setDescription("");
      setFile(null);
      event.currentTarget.reset();
      setNotice("Partner file uploaded.");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to upload file.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="connected-source-subsection" aria-label="Partner Files">
      <form className="manual-update-form upload-form" onSubmit={handleSubmit}>
        <div className="manual-update-heading">
          <div>
            <p className="eyebrow">Partner Files</p>
            <h4>File Upload</h4>
          </div>
        </div>

        {error ? <p className="workspace-error inline-error">{error}</p> : null}
        {notice ? <p className="metadata-save-notice">{notice}</p> : null}

        <div className="form-field">
          <label htmlFor="contributor-upload-file">File</label>
          <input
            id="contributor-upload-file"
            type="file"
            accept=".txt,.md,.csv,.json,.log,.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            required
          />
        </div>

        <div className="form-field">
          <label htmlFor="contributor-upload-title">Title</label>
          <input
            id="contributor-upload-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Defaults to filename"
          />
        </div>

        <div className="form-field">
          <label htmlFor="contributor-upload-description">Description</label>
          <textarea
            id="contributor-upload-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Optional context for this partner file"
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
        emptyLabel="No partner files uploaded"
      />
    </div>
  );
}
