"use client";

import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import {
  AdminPartner,
  AdminPartnerPayload,
  archiveAdminPartner,
  createAdminPartner,
  listAdminPartners,
  restoreAdminPartner,
  updateAdminPartner,
} from "@/features/admin/admin-partners-api";
import { AdminUser, listAdminUsers } from "@/features/admin/admin-users-api";

type PartnerFormState = {
  name: string;
  description: string;
  assignedContributorUserId: string;
};

const emptyForm: PartnerFormState = {
  name: "",
  description: "",
  assignedContributorUserId: "",
};

type AdminPartnersPanelProps = {
  onHeaderActionChange?: (action: ReactNode | null) => void;
};

export function AdminPartnersPanel({ onHeaderActionChange }: AdminPartnersPanelProps) {
  const [partners, setPartners] = useState<AdminPartner[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editingPartner, setEditingPartner] = useState<AdminPartner | null>(null);
  const [form, setForm] = useState<PartnerFormState>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    Promise.all([listAdminPartners(), listAdminUsers()])
      .then(([nextPartners, nextUsers]) => {
        if (mounted) {
          setPartners([...nextPartners].sort(sortPartners));
          setUsers(nextUsers);
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load partners.");
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

  const activeCount = useMemo(
    () => partners.filter((partner) => partner.status === "active").length,
    [partners],
  );

  const activeContributors = useMemo(
    () =>
      users.filter(
        (user) => user.status === "active" && user.roles.includes("contributor"),
      ),
    [users],
  );

  const openCreateForm = useCallback(() => {
    setEditingPartner(null);
    setForm(emptyForm);
    setFormOpen(true);
    setError(null);
  }, []);

  useEffect(() => {
    if (!onHeaderActionChange) {
      return;
    }

    onHeaderActionChange(
      <button className="admin-header-primary-action" type="button" onClick={openCreateForm}>
        Add Partner +
      </button>,
    );

    return () => onHeaderActionChange(null);
  }, [onHeaderActionChange, openCreateForm]);

  function openEditForm(partner: AdminPartner) {
    setEditingPartner(partner);
    setForm({
      name: partner.name,
      description: partner.description ?? "",
      assignedContributorUserId: partner.assigned_contributors[0]?.user_id ?? "",
    });
    setFormOpen(true);
    setError(null);
  }

  function closeForm() {
    setFormOpen(false);
    setEditingPartner(null);
    setForm(emptyForm);
    setError(null);
  }

  function selectContributor(userId: string) {
    setForm((current) => ({
      ...current,
      assignedContributorUserId: userId,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    const payload: AdminPartnerPayload = {
      name: form.name,
      description: form.description || null,
      assigned_contributor_user_ids: form.assignedContributorUserId
        ? [form.assignedContributorUserId]
        : [],
    };

    try {
      const savedPartner = editingPartner
        ? await updateAdminPartner(editingPartner.partner_id, payload)
        : await createAdminPartner(payload);
      setPartners((current) => upsertPartner(current, savedPartner));
      closeForm();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to save partner.");
    } finally {
      setSaving(false);
    }
  }

  async function handleStatusChange(partner: AdminPartner) {
    setError(null);
    try {
      const updatedPartner =
        partner.status === "active"
          ? await archiveAdminPartner(partner.partner_id)
          : await restoreAdminPartner(partner.partner_id);
      setPartners((current) => upsertPartner(current, updatedPartner));
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to update partner status.");
    }
  }

  return (
    <div className="admin-team-panel">
      <div className="team-summary">
        <span>{partners.length} total partners</span>
        <span>{activeCount} active</span>
      </div>

      {error ? <p className="workspace-error inline-error">{error}</p> : null}

      {formOpen ? (
        <form className="team-form partner-form" onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="partner-name">Partner Name</label>
            <input
              id="partner-name"
              type="text"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="Enter Partner Name"
              required
            />
          </div>

          <div className="form-field">
            <label htmlFor="partner-description">Description</label>
            <input
              id="partner-description"
              type="text"
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              placeholder="Optional context"
            />
          </div>

          <fieldset className="role-options">
            <legend>Assigned Contributors</legend>
            {activeContributors.length ? (
              activeContributors.map((user) => (
                <label key={user.user_id}>
                  <input
                    type="radio"
                    name="assigned-contributor"
                    checked={form.assignedContributorUserId === user.user_id}
                    onChange={() => selectContributor(user.user_id)}
                  />
                  <span>{user.display_name}</span>
                </label>
              ))
            ) : (
              <span className="empty-inline">No active contributors available</span>
            )}
          </fieldset>

          <div className="form-actions">
            <button className="primary-action compact-action" type="submit" disabled={saving}>
              {saving ? "Saving" : editingPartner ? "Save changes" : "Create partner"}
            </button>
            <button className="ghost-action" type="button" onClick={closeForm}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      <div className="team-table-wrap">
        <table className="team-table">
          <thead>
            <tr>
              <th>Partner</th>
              <th>Description</th>
              <th>Assigned Contributors</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5}>Loading partners</td>
              </tr>
            ) : null}

            {!loading && partners.length === 0 ? (
              <tr>
                <td colSpan={5}>No partners yet</td>
              </tr>
            ) : null}

            {!loading
              ? partners.map((partner) => (
                  <tr key={partner.partner_id}>
                    <td>{partner.name}</td>
                    <td>{partnerDescription(partner)}</td>
                    <td>
                      <div className="role-pills">
                        {partner.assigned_contributors.length ? (
                          partner.assigned_contributors.map((user) => (
                            <span key={user.user_id}>{user.display_name}</span>
                          ))
                        ) : (
                          <span>Unassigned</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className={`status-pill ${partner.status}`}>
                        {statusLabel(partner.status)}
                      </span>
                    </td>
                    <td>
                      <div className="table-actions">
                        <button type="button" onClick={() => openEditForm(partner)}>
                          Edit
                        </button>
                        <button type="button" onClick={() => handleStatusChange(partner)}>
                          {partner.status === "active" ? "Archive" : "Restore"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function upsertPartner(partners: AdminPartner[], savedPartner: AdminPartner): AdminPartner[] {
  const exists = partners.some((partner) => partner.partner_id === savedPartner.partner_id);
  if (!exists) {
    return [...partners, savedPartner].sort(sortPartners);
  }
  return partners
    .map((partner) => (partner.partner_id === savedPartner.partner_id ? savedPartner : partner))
    .sort(sortPartners);
}

function sortPartners(a: AdminPartner, b: AdminPartner): number {
  if (a.status !== b.status) {
    return a.status === "active" ? -1 : 1;
  }

  return a.name.localeCompare(b.name);
}

function partnerDescription(partner: AdminPartner): string {
  return partner.description?.trim() || `${partner.name} partner workspace`;
}

function statusLabel(status: AdminPartner["status"]): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}
