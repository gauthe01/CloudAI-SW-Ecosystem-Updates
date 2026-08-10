"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

import { requestAccountAccess } from "@/features/auth/access-request-api";
import { routes } from "@/lib/routes";

type RequestAccessFormState = {
  displayName: string;
  email: string;
  password: string;
  confirmPassword: string;
};

const emptyForm: RequestAccessFormState = {
  displayName: "",
  email: "",
  password: "",
  confirmPassword: "",
};

const passwordRules: Array<{ id: string; label: string; test: (password: string) => boolean }> = [
  {
    id: "length",
    label: "Minimum 8 characters",
    test: (password) => password.length >= 8,
  },
  {
    id: "uppercase",
    label: "One uppercase letter",
    test: (password) => /[A-Z]/.test(password),
  },
  {
    id: "number",
    label: "One number",
    test: (password) => /\d/.test(password),
  },
  {
    id: "special",
    label: "One special character",
    test: (password) => /[^A-Za-z0-9]/.test(password),
  },
];

export function RequestAccessForm() {
  const [form, setForm] = useState<RequestAccessFormState>(emptyForm);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const satisfiedRuleIds = useMemo(
    () => new Set(passwordRules.filter((rule) => rule.test(form.password)).map((rule) => rule.id)),
    [form.password],
  );
  const passwordReady = satisfiedRuleIds.size === passwordRules.length;

  function updateField(field: keyof RequestAccessFormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const trimmedEmail = form.email.trim().toLowerCase();
    if (!trimmedEmail.endsWith("@arm.com")) {
      setError("Use your ARM email address.");
      return;
    }
    if (!passwordReady) {
      setError("Create a stronger password.");
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError("Passwords don't match.");
      return;
    }

    setSubmitting(true);
    try {
      await requestAccountAccess({
        displayName: form.displayName.trim(),
        email: trimmedEmail,
        password: form.password,
        confirmPassword: form.confirmPassword,
      });
      setSubmitted(true);
      setForm(emptyForm);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Something went wrong. Please try again later.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="request-status-panel" role="status">
        <h3>Request submitted</h3>
        <p>An admin will review your access request before you can sign in.</p>
        <Link className="auth-link" href={routes.login}>
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <form className="login-form request-access-form" onSubmit={handleSubmit}>
      <div className="form-field">
        <label htmlFor="request-display-name">Name</label>
        <input
          id="request-display-name"
          type="text"
          value={form.displayName}
          onChange={(event) => updateField("displayName", event.target.value)}
          placeholder="Full name"
          autoComplete="name"
          required
        />
      </div>

      <div className="form-field">
        <label htmlFor="request-email">ARM email ID</label>
        <input
          id="request-email"
          type="email"
          value={form.email}
          onChange={(event) => updateField("email", event.target.value)}
          placeholder="name@arm.com"
          autoComplete="email"
          required
        />
      </div>

      <div className="password-pair">
        <div className="form-field">
          <label htmlFor="request-password">Set password</label>
          <div className="password-field">
            <input
              id="request-password"
              type={showPassword ? "text" : "password"}
              value={form.password}
              onChange={(event) => updateField("password", event.target.value)}
              placeholder="Create password"
              autoComplete="new-password"
              required
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword((current) => !current)}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
        </div>

        <div className="form-field">
          <label htmlFor="request-confirm-password">Confirm password</label>
          <div className="password-field">
            <input
              id="request-confirm-password"
              type={showConfirmPassword ? "text" : "password"}
              value={form.confirmPassword}
              onChange={(event) => updateField("confirmPassword", event.target.value)}
              placeholder="Re-enter password"
              autoComplete="new-password"
              required
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowConfirmPassword((current) => !current)}
            >
              {showConfirmPassword ? "Hide" : "Show"}
            </button>
          </div>
        </div>
      </div>

      <ul className="password-rules" aria-label="Password requirements">
        {passwordRules.map((rule) => (
          <li key={rule.id} className={satisfiedRuleIds.has(rule.id) ? "met" : undefined}>
            {rule.label}
          </li>
        ))}
      </ul>

      {error ? <p className="form-error">{error}</p> : null}

      <button className="primary-action" type="submit" disabled={submitting}>
        {submitting ? "Submitting" : "Request access"}
      </button>

      <Link className="auth-link centered-auth-link" href={routes.login}>
        Back to sign in
      </Link>
    </form>
  );
}
