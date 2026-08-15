import { AccountView } from "@/features/auth/auth-api";

export const viewLabels: Record<AccountView, string> = {
  contributor: "Contributor View",
  presenter: "Presenter View",
  admin: "Admin Console",
};

export const viewOrder: AccountView[] = ["contributor", "presenter", "admin"];

export const sectionLabels: Record<AccountView, string[]> = {
  contributor: ["Partner Metadata", "Draft Updates", "Approved Updates", "Connected Sources"],
  presenter: ["Partner Updates", "Executive Summary", "Decision Board", "Event Calendar"],
  admin: [
    "Admin Console",
    "Partners",
    "Knowledge Upload",
    "Events/Topics",
    "Team",
    "Global Integrations",
    "Source Approvals",
  ],
};

export const adminSectionDisplayLabels: Record<string, string> = {
  "Admin Console": "Admin Console",
  Partners: "Partners",
  Team: "Team Members",
  "Global Integrations": "Global Integrations",
  "Source Approvals": "Connected Sources",
  "Knowledge Upload": "Knowledge Upload",
  "Events/Topics": "Events/Topics",
};
