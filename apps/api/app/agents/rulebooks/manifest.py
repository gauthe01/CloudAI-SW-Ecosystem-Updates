from dataclasses import dataclass


@dataclass(frozen=True)
class RulebookManifestEntry:
    name: str
    filename: str
    description: str


RULEBOOK_MANIFEST: dict[str, RulebookManifestEntry] = {
    "source_event.slack": RulebookManifestEntry(
        name="source_event.slack",
        filename="source_event.slack.md",
        description="Slack message and thread-reply extraction guidance.",
    ),
    "source_event.jira": RulebookManifestEntry(
        name="source_event.jira",
        filename="source_event.jira.md",
        description="Jira ticket/comment/status extraction guidance.",
    ),
    "source_event.sharepoint": RulebookManifestEntry(
        name="source_event.sharepoint",
        filename="source_event.sharepoint.md",
        description="SharePoint document extraction guidance.",
    ),
    "source_event.confluence": RulebookManifestEntry(
        name="source_event.confluence",
        filename="source_event.confluence.md",
        description="Confluence page extraction guidance.",
    ),
    "source_event.github": RulebookManifestEntry(
        name="source_event.github",
        filename="source_event.github.md",
        description="GitHub repository, issue, and pull request extraction guidance.",
    ),
    "update_quality": RulebookManifestEntry(
        name="update_quality",
        filename="update_quality.md",
        description="Draft update quality, language, and review guidance.",
    ),
    "presenter_intelligence": RulebookManifestEntry(
        name="presenter_intelligence",
        filename="presenter_intelligence.md",
        description="Presenter intelligence synthesis guidance.",
    ),
    "presenter_chatbot": RulebookManifestEntry(
        name="presenter_chatbot",
        filename="presenter_chatbot.md",
        description="Grounded presenter Ask AI chatbot guidance.",
    ),
    "presenter_executive_summary": RulebookManifestEntry(
        name="presenter_executive_summary",
        filename="presenter_executive_summary.md",
        description="Presenter executive summary generation guidance.",
    ),
    "executive_email": RulebookManifestEntry(
        name="executive_email",
        filename="executive_email.md",
        description="Executive email generation guidance.",
    ),
    "decision_board": RulebookManifestEntry(
        name="decision_board",
        filename="decision_board.md",
        description="Decision board and leadership action analysis guidance.",
    ),
}
