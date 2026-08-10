"use client";

import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { AccountView } from "@/features/auth/auth-api";
import {
  AccountAccessRequest,
  AdminUser,
  AdminUserPayload,
  approveAccountAccessRequest,
  createAdminUser,
  deactivateAdminUser,
  listAccountAccessRequests,
  listAdminUsers,
  reactivateAdminUser,
  rejectAccountAccessRequest,
  updateAdminUser,
} from "@/features/admin/admin-users-api";

type TeamFormState = {
  email: string;
  displayName: string;
  roles: AccountView[];
};

const roleOptions: Array<{ value: AccountView; label: string }> = [
  { value: "contributor", label: "Contributor" },
  { value: "presenter", label: "Presenter" },
  { value: "admin", label: "Admin" },
];

const emptyForm: TeamFormState = {
  email: "",
  displayName: "",
  roles: ["contributor"],
};

type AdminTeamPanelProps = {
  onHeaderActionChange?: (action: ReactNode | null) => void;
};

export function AdminTeamPanel({ onHeaderActionChange }: AdminTeamPanelProps) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [accessRequests, setAccessRequests] = useState<AccountAccessRequest[]>([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [form, setForm] = useState<TeamFormState>(emptyForm);
  const [approvalRolesByRequestId, setApprovalRolesByRequestId] = useState<
    Record<string, AccountView[]>
  >({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reviewingRequestId, setReviewingRequestId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    Promise.all([listAdminUsers(), listAccountAccessRequests()])
      .then(([nextUsers, nextAccessRequests]) => {
        if (mounted) {
          setUsers([...nextUsers].sort(sortUsers));
          setAccessRequests(nextAccessRequests);
        }
      })
      .catch((error) => {
        if (mounted) {
          setError(error instanceof Error ? error.message : "Unable to load team members.");
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
    () => users.filter((user) => user.status === "active").length,
    [users],
  );
  const pendingAccessRequestCount = useMemo(
    () => accessRequests.filter((request) => request.status === "pending").length,
    [accessRequests],
  );

  const openCreateForm = useCallback(() => {
    setEditingUser(null);
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
        Add Member +
      </button>,
    );

    return () => onHeaderActionChange(null);
  }, [onHeaderActionChange, openCreateForm]);

  function openEditForm(user: AdminUser) {
    setEditingUser(user);
    setForm({
      email: user.email,
      displayName: user.display_name,
      roles: user.roles.length ? user.roles : ["contributor"],
    });
    setFormOpen(true);
    setError(null);
  }

  function closeForm() {
    setFormOpen(false);
    setEditingUser(null);
    setForm(emptyForm);
    setError(null);
  }

  function toggleRole(role: AccountView) {
    setForm((current) => {
      const hasRole = current.roles.includes(role);
      const nextRoles = hasRole
        ? current.roles.filter((currentRole) => currentRole !== role)
        : [...current.roles, role];
      return {
        ...current,
        roles: nextRoles.length ? nextRoles : current.roles,
      };
    });
  }

  function toggleApprovalRole(requestId: string, role: AccountView) {
    setApprovalRolesByRequestId((current) => {
      const currentRoles = current[requestId] ?? [];
      const nextRoles = currentRoles.includes(role)
        ? currentRoles.filter((currentRole) => currentRole !== role)
        : [...currentRoles, role];
      return { ...current, [requestId]: nextRoles };
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    const payload: AdminUserPayload = {
      email: form.email,
      display_name: form.displayName,
      roles: form.roles,
    };

    try {
      const savedUser = editingUser
        ? await updateAdminUser(editingUser.user_id, payload)
        : await createAdminUser(payload);
      setUsers((current) => {
        const exists = current.some((user) => user.user_id === savedUser.user_id);
        if (!exists) {
          return [...current, savedUser].sort(sortUsers);
        }
        return current
          .map((user) => (user.user_id === savedUser.user_id ? savedUser : user))
          .sort(sortUsers);
      });
      closeForm();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to save team member.");
    } finally {
      setSaving(false);
    }
  }

  async function handleStatusChange(user: AdminUser) {
    setError(null);
    try {
      const updatedUser =
        user.status === "active"
          ? await deactivateAdminUser(user.user_id)
          : await reactivateAdminUser(user.user_id);
      setUsers((current) => upsertUser(current, updatedUser));
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to update team member status.");
    }
  }

  async function handleAccessRequestReview(
    request: AccountAccessRequest,
    action: "approve" | "reject",
  ) {
    setError(null);
    setReviewingRequestId(request.request_id);

    try {
      const result =
        action === "approve"
          ? await approveAccountAccessRequest(
              request.request_id,
              approvalRolesByRequestId[request.request_id] ?? [],
            )
          : await rejectAccountAccessRequest(request.request_id);
      setAccessRequests((current) =>
        current.map((currentRequest) =>
          currentRequest.request_id === result.request.request_id
            ? result.request
            : currentRequest,
        ),
      );
      if (result.created_user) {
        setUsers((current) => upsertUser(current, result.created_user as AdminUser));
      }
      setApprovalRolesByRequestId((current) => {
        const next = { ...current };
        delete next[request.request_id];
        return next;
      });
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to review access request.");
    } finally {
      setReviewingRequestId(null);
    }
  }

  return (
    <div className="admin-team-panel">
      <div className="team-summary">
        <span>{users.length} total members</span>
        <span>{activeCount} active</span>
        <span>{pendingAccessRequestCount} pending requests</span>
      </div>

      {error ? <p className="workspace-error inline-error">{error}</p> : null}

      {formOpen ? (
        <form className="team-form" onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="team-display-name">Name</label>
            <input
              id="team-display-name"
              type="text"
              value={form.displayName}
              onChange={(event) => setForm({ ...form, displayName: event.target.value })}
              placeholder="Full name"
              required
            />
          </div>

          <div className="form-field">
            <label htmlFor="team-email">Email ID</label>
            <input
              id="team-email"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
              placeholder="name@arm.com"
              required
            />
          </div>

          <fieldset className="role-checkboxes">
            <legend>Roles</legend>
            {roleOptions.map((role) => (
              <label key={role.value}>
                <input
                  type="checkbox"
                  checked={form.roles.includes(role.value)}
                  onChange={() => toggleRole(role.value)}
                />
                <span>{role.label}</span>
              </label>
            ))}
          </fieldset>

          <div className="form-actions">
            <button className="primary-action compact-action" type="submit" disabled={saving}>
              {saving ? "Saving" : editingUser ? "Save changes" : "Create member"}
            </button>
            <button className="ghost-action" type="button" onClick={closeForm}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      <section className="access-requests-panel" aria-label="Access requests">
        <div className="admin-subsection-heading">
          <div>
            <h3>Access Requests</h3>
            <p>Select at least one role before approving access.</p>
          </div>
        </div>

        <div className="team-table-wrap">
          <table className="team-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email ID</th>
                <th>Roles</th>
                <th>Status</th>
                <th>Requested</th>
                <th>Reviewed</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6}>Loading access requests</td>
                </tr>
              ) : null}

              {!loading && accessRequests.length === 0 ? (
                <tr>
                  <td colSpan={6}>No access requests yet</td>
                </tr>
              ) : null}

              {!loading
                ? accessRequests.map((request) => {
                    const reviewedUser = userForAccessRequest(request, users);
                    return (
                    <tr key={request.request_id}>
                      <td>{request.display_name}</td>
                      <td>{request.email}</td>
                      <td>
                        {request.status === "pending" ? (
                          <div className="approval-role-controls">
                            {roleOptions.map((role) => (
                              <label key={role.value}>
                                <input
                                  type="checkbox"
                                  checked={(approvalRolesByRequestId[request.request_id] ?? []).includes(
                                    role.value,
                                  )}
                                  onChange={() =>
                                    toggleApprovalRole(request.request_id, role.value)
                                  }
                                />
                                <span>{role.label}</span>
                              </label>
                            ))}
                          </div>
                        ) : (
                          <div className="role-pills">
                            {reviewedUser?.roles.length ? (
                              reviewedUser.roles.map((role) => (
                                <span key={role}>{roleLabel(role)}</span>
                              ))
                            ) : (
                              <span className="unassigned-role">No roles</span>
                            )}
                          </div>
                        )}
                      </td>
                      <td>
                        <span className={`status-pill ${request.status}`}>
                          {statusLabel(request.status)}
                        </span>
                      </td>
                      <td>{formatDate(request.requested_at)}</td>
                      <td>
                        {request.status === "pending" ? (
                          <div className="table-actions">
                            <button
                              type="button"
                              disabled={
                                reviewingRequestId === request.request_id ||
                                (approvalRolesByRequestId[request.request_id] ?? []).length === 0
                              }
                              onClick={() => handleAccessRequestReview(request, "approve")}
                            >
                              Approve
                            </button>
                            <button
                              type="button"
                              disabled={reviewingRequestId === request.request_id}
                              onClick={() => handleAccessRequestReview(request, "reject")}
                            >
                              Reject
                            </button>
                          </div>
                        ) : (
                          <span className="muted-copy">
                            {request.reviewed_at ? formatDate(request.reviewed_at) : "Reviewed"}
                          </span>
                        )}
                      </td>
                    </tr>
                    );
                  })
                : null}
            </tbody>
          </table>
        </div>
      </section>

      <div className="team-table-wrap">
        <table className="team-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email ID</th>
              <th>Roles</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5}>Loading team members</td>
              </tr>
            ) : null}

            {!loading && users.length === 0 ? (
              <tr>
                <td colSpan={5}>No team members yet</td>
              </tr>
            ) : null}

            {!loading
              ? users.map((user) => (
                  <tr key={user.user_id}>
                    <td>{user.display_name}</td>
                    <td>{user.email}</td>
                    <td>
                      <div className="role-pills">
                        {user.roles.length ? (
                          user.roles.map((role) => <span key={role}>{roleLabel(role)}</span>)
                        ) : (
                          <span className="unassigned-role">No roles</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className={`status-pill ${user.status}`}>
                        {statusLabel(user.status)}
                      </span>
                    </td>
                    <td>
                      <div className="table-actions">
                        <button type="button" onClick={() => openEditForm(user)}>
                          Edit
                        </button>
                        <button type="button" onClick={() => handleStatusChange(user)}>
                          {user.status === "active" ? "Deactivate" : "Reactivate"}
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

function roleLabel(role: AccountView): string {
  return roleOptions.find((option) => option.value === role)?.label ?? role;
}

function sortUsers(a: AdminUser, b: AdminUser): number {
  if (a.status !== b.status) {
    return a.status === "active" ? -1 : 1;
  }

  return a.display_name.localeCompare(b.display_name) || a.email.localeCompare(b.email);
}

function upsertUser(users: AdminUser[], savedUser: AdminUser): AdminUser[] {
  const exists = users.some((user) => user.user_id === savedUser.user_id);
  if (!exists) {
    return [...users, savedUser].sort(sortUsers);
  }

  return users.map((user) => (user.user_id === savedUser.user_id ? savedUser : user)).sort(sortUsers);
}

function statusLabel(status: string): string {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function userForAccessRequest(
  request: AccountAccessRequest,
  users: AdminUser[],
): AdminUser | undefined {
  if (request.created_user_id) {
    return users.find((user) => user.user_id === request.created_user_id);
  }
  return users.find((user) => user.email.toLowerCase() === request.email.toLowerCase());
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
