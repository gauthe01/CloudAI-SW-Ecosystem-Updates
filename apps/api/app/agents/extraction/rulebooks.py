from app.db.models.connected_source import ConnectedSourceType

SOURCE_EVENT_RULEBOOK_BY_SOURCE_TYPE = {
    ConnectedSourceType.slack_channel.value: "source_event.slack",
    ConnectedSourceType.jira_issue.value: "source_event.jira",
    ConnectedSourceType.sharepoint_file.value: "source_event.sharepoint",
    ConnectedSourceType.confluence_page.value: "source_event.confluence",
    ConnectedSourceType.github_repository.value: "source_event.github",
    ConnectedSourceType.github_issue.value: "source_event.github",
    ConnectedSourceType.github_pull_request.value: "source_event.github",
}


def source_event_rulebook_name(source_type: str) -> str:
    try:
        return SOURCE_EVENT_RULEBOOK_BY_SOURCE_TYPE[source_type]
    except KeyError as exc:
        raise ValueError(f"No source-event rulebook is registered for {source_type!r}.") from exc
