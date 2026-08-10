"use client";

import { useEffect, useState } from "react";

type ApiStatus = {
  status: "checking" | "ok" | "unavailable";
  appName?: string;
  environment?: string;
  version?: string;
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function FoundationStatus() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>({ status: "checking" });

  useEffect(() => {
    let cancelled = false;

    async function checkApi() {
      try {
        const response = await fetch(`${apiBaseUrl}/healthz`, {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`Health check failed with ${response.status}`);
        }

        const payload = await response.json();
        if (!cancelled) {
          setApiStatus({
            status: "ok",
            appName: payload.app_name,
            environment: payload.environment,
            version: payload.version,
          });
        }
      } catch {
        if (!cancelled) {
          setApiStatus({ status: "unavailable" });
        }
      }
    }

    void checkApi();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="foundation-panel">
      <h2>Local Health</h2>
      <div className="status-row">
        <span className="status-label">Web</span>
        <span className="status-value ok">Loaded</span>
      </div>
      <div className="status-row">
        <span className="status-label">API</span>
        <span className={`status-value ${apiStatus.status === "ok" ? "ok" : "pending"}`}>
          {apiStatus.status === "checking" && "Checking"}
          {apiStatus.status === "ok" && "Reachable"}
          {apiStatus.status === "unavailable" && "Start API"}
        </span>
      </div>
      <div className="status-row">
        <span className="status-label">Environment</span>
        <span className="status-value">{apiStatus.environment ?? "local"}</span>
      </div>
      <div className="status-row">
        <span className="status-label">API version</span>
        <span className="status-value">{apiStatus.version ?? "0.1.0"}</span>
      </div>
    </div>
  );
}
