from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.connected_source import (
    ConnectedSource,
    ConnectedSourceJiraIssue,
    ConnectedSourceSlackChannel,
    ConnectedSourceType,
)
from app.db.models.integration import IntegrationType
from app.db.models.source_event import SourcePayloadRetentionPolicy
from app.db.models.source_sync import SourceSyncState
from app.domains.admin.integrations.secrets import get_integration_secret_value
from app.domains.source_events.schemas import SourceEventIngestRequest


@dataclass(frozen=True)
class SyncItem:
    external_event_id: str
    idempotency_key: str
    source_url: str | None
    source_event_timestamp: datetime
    technical_metadata: dict[str, Any]
    raw_payload_json: dict[str, Any] | None = None
    retention_policy: str = SourcePayloadRetentionPolicy.structured_payload.value


@dataclass(frozen=True)
class ConnectorSyncResult:
    items: list[SyncItem]
    cursor_value: str | None
    cursor_timestamp: datetime | None
    ignored_count: int = 0
    skipped_reason: str | None = None
    backfill_completed: bool = False


class SourceSyncConnector(Protocol):
    source_type: ConnectedSourceType

    async def fetch(
        self,
        *,
        source: ConnectedSource,
        state: SourceSyncState,
    ) -> ConnectorSyncResult:
        """Fetch new source items and normalize them into source-event requests."""


class UnsupportedSourceSyncConnector:
    def __init__(self, source_type: ConnectedSourceType) -> None:
        self.source_type = source_type

    async def fetch(
        self,
        *,
        source: ConnectedSource,
        state: SourceSyncState,
    ) -> ConnectorSyncResult:
        return ConnectorSyncResult(
            items=[],
            cursor_value=state.cursor_value,
            cursor_timestamp=state.cursor_timestamp,
            skipped_reason=f"Automatic polling is not implemented for {source.source_type}.",
        )


class SlackSourceSyncConnector:
    source_type = ConnectedSourceType.slack_channel

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def fetch(
        self,
        *,
        source: ConnectedSource,
        state: SourceSyncState,
    ) -> ConnectorSyncResult:
        detail = await self._load_detail(source)
        bot_token = await self._bot_token()
        backfill_required = state.backfill_completed_at is None
        oldest = slack_oldest_cursor(state=state)
        latest = oldest if backfill_required and oldest else None
        fetch_oldest = None if backfill_required else oldest
        responses = await self._get_history_pages(
            bot_token=bot_token,
            channel_id=detail.channel_id,
            oldest=fetch_oldest,
            latest=latest,
        )
        raw_messages = [
            message
            for response in responses
            for message in response.get("messages", [])
        ]
        messages = [message for message in raw_messages if should_enqueue_slack_message(message)]
        items = [
            slack_message_to_sync_item(
                source=source,
                detail=detail,
                message=message,
            )
            for message in sorted(messages, key=slack_message_ts)
        ]
        latest_ts = latest_slack_ts(messages)
        latest_raw_ts = latest_slack_ts(raw_messages)
        cursor_value = latest_ts or latest_raw_ts or state.cursor_value
        if backfill_required and latest:
            cursor_value = state.cursor_value
        if backfill_required and cursor_value is None:
            cursor_value = str(datetime.now(UTC).timestamp())
        return ConnectorSyncResult(
            items=items,
            cursor_value=cursor_value,
            cursor_timestamp=(
                slack_timestamp_to_datetime(cursor_value)
                if cursor_value
                else state.cursor_timestamp
            ),
            ignored_count=max(0, len(raw_messages) - len(messages)),
            backfill_completed=backfill_required,
        )

    async def _load_detail(self, source: ConnectedSource) -> ConnectedSourceSlackChannel:
        result = await self.db.execute(
            select(ConnectedSourceSlackChannel).where(
                ConnectedSourceSlackChannel.connected_source_id == source.connected_source_id
            )
        )
        detail = result.scalar_one_or_none()
        if detail is None:
            raise RuntimeError("Slack connected source is missing channel details.")
        return detail

    async def _bot_token(self) -> str:
        token = await get_integration_secret_value(
            self.db,
            self.settings,
            integration_type=IntegrationType.slack,
            secret_name="bot_token",
        )
        if not token:
            raise RuntimeError("Slack bot token is not configured.")
        return token

    async def _get_history_pages(
        self,
        *,
        bot_token: str,
        channel_id: str,
        oldest: str | None,
        latest: str | None,
    ) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            payload = await self._get_history(
                bot_token=bot_token,
                channel_id=channel_id,
                oldest=oldest,
                latest=latest,
                cursor=cursor,
            )
            pages.append(payload)
            next_cursor = (
                payload.get("response_metadata", {}).get("next_cursor")
                if isinstance(payload.get("response_metadata"), dict)
                else None
            )
            if not next_cursor:
                return pages
            cursor = str(next_cursor)

    async def _get_history(
        self,
        *,
        bot_token: str,
        channel_id: str,
        oldest: str | None,
        latest: str | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "channel": channel_id,
            "limit": 200,
            "inclusive": "false",
        }
        if oldest:
            params["oldest"] = oldest
        if latest:
            params["latest"] = latest
        if cursor:
            params["cursor"] = cursor
        async with httpx.AsyncClient(
            timeout=self.settings.source_sync_http_timeout_seconds
        ) as client:
            response = await client.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {bot_token}"},
                params=params,
            )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Slack history fetch failed: {payload.get('error') or 'unknown'}")
        return payload


class JiraSourceSyncConnector:
    source_type = ConnectedSourceType.jira_issue

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def fetch(
        self,
        *,
        source: ConnectedSource,
        state: SourceSyncState,
    ) -> ConnectorSyncResult:
        detail = await self._load_detail(source)
        base_url = await self._secret("base_url")
        token = await self._secret("service_token")
        issue = await self._fetch_issue(
            base_url=base_url.rstrip("/"),
            token=token,
            issue_key=detail.issue_key,
        )
        backfill_required = state.backfill_completed_at is None
        since = None if backfill_required else (
            state.cursor_timestamp
            or datetime.now(UTC) - timedelta(days=self.settings.source_sync_initial_lookback_days)
        )
        until = state.cursor_timestamp if backfill_required else None
        candidates = jira_issue_to_sync_items(
            source=source,
            detail=detail,
            issue=issue,
            base_url=base_url.rstrip("/"),
            since=since,
            until=until,
        )
        latest = max((item.source_event_timestamp for item in candidates), default=None)
        cursor_timestamp = latest or state.cursor_timestamp
        cursor_value = latest.isoformat() if latest else state.cursor_value
        if backfill_required and state.cursor_timestamp is not None:
            cursor_timestamp = state.cursor_timestamp
            cursor_value = state.cursor_value
        if backfill_required and cursor_timestamp is None:
            cursor_timestamp = datetime.now(UTC)
            cursor_value = cursor_timestamp.isoformat()
        return ConnectorSyncResult(
            items=candidates,
            cursor_value=cursor_value,
            cursor_timestamp=cursor_timestamp,
            backfill_completed=backfill_required,
        )

    async def _load_detail(self, source: ConnectedSource) -> ConnectedSourceJiraIssue:
        result = await self.db.execute(
            select(ConnectedSourceJiraIssue).where(
                ConnectedSourceJiraIssue.connected_source_id == source.connected_source_id
            )
        )
        detail = result.scalar_one_or_none()
        if detail is None:
            raise RuntimeError("Jira connected source is missing issue details.")
        return detail

    async def _secret(self, secret_name: str) -> str:
        value = await get_integration_secret_value(
            self.db,
            self.settings,
            integration_type=IntegrationType.jira,
            secret_name=secret_name,
        )
        if not value:
            raise RuntimeError(f"Jira {secret_name} is not configured.")
        return value

    async def _fetch_issue(self, *, base_url: str, token: str, issue_key: str) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=self.settings.source_sync_http_timeout_seconds
        ) as client:
            response = await client.get(
                f"{base_url}/rest/api/2/issue/{issue_key}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                params={
                    "expand": "changelog",
                    "fields": (
                        "summary,status,priority,duedate,attachment,comment,"
                        "description,created,updated"
                    ),
                },
            )
            response.raise_for_status()
            payload = response.json()
            expanded_changelog = (
                nested_list(payload, "changelog", "histories")
                if isinstance(payload, dict)
                else []
            )
            comments = await self._get_paginated_values(
                client=client,
                base_url=base_url,
                token=token,
                path=f"/rest/api/2/issue/{issue_key}/comment",
                value_key="comments",
            )
            try:
                changelog = await self._get_paginated_values(
                    client=client,
                    base_url=base_url,
                    token=token,
                    path=f"/rest/api/2/issue/{issue_key}/changelog",
                    value_key="values",
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                changelog = expanded_changelog
        if not isinstance(payload, dict):
            raise RuntimeError("Jira issue fetch returned an invalid payload.")
        fields = payload.get("fields")
        if isinstance(fields, dict):
            fields["comment"] = {"comments": comments}
        payload["changelog"] = {"histories": changelog}
        return payload

    async def _get_paginated_values(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        token: str,
        path: str,
        value_key: str,
    ) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        start_at = 0
        max_results = 100
        while True:
            response = await client.get(
                f"{base_url}{path}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                params={"startAt": start_at, "maxResults": max_results},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("Jira paginated fetch returned an invalid payload.")
            page_values = payload.get(value_key)
            if not isinstance(page_values, list) and value_key == "values":
                page_values = payload.get("histories")
            if not isinstance(page_values, list):
                return values
            values.extend(item for item in page_values if isinstance(item, dict))
            total = int(payload.get("total") or len(values))
            start_at += int(payload.get("maxResults") or max_results)
            if not page_values or start_at >= total:
                return values


def connector_for_source(
    *,
    source_type: str,
    db: AsyncSession,
    settings: Settings,
) -> SourceSyncConnector:
    parsed = ConnectedSourceType(source_type)
    if parsed == ConnectedSourceType.slack_channel:
        return SlackSourceSyncConnector(db, settings)
    if parsed == ConnectedSourceType.jira_issue:
        return JiraSourceSyncConnector(db, settings)
    return UnsupportedSourceSyncConnector(parsed)


def to_ingest_request(item: SyncItem, connected_source_id) -> SourceEventIngestRequest:
    return SourceEventIngestRequest(
        connected_source_id=connected_source_id,
        external_event_id=item.external_event_id,
        idempotency_key=item.idempotency_key,
        source_url=item.source_url,
        source_event_timestamp=item.source_event_timestamp,
        technical_metadata=item.technical_metadata,
        raw_payload_json=item.raw_payload_json,
        retention_policy=item.retention_policy,
    )


def slack_oldest_cursor(*, state: SourceSyncState) -> str | None:
    if state.cursor_value:
        return state.cursor_value
    if state.cursor_timestamp:
        return str(state.cursor_timestamp.timestamp())
    return None


def should_enqueue_slack_message(message: dict[str, Any]) -> bool:
    if message.get("subtype") or message.get("bot_id"):
        return False
    return bool(str(message.get("text") or "").strip() and str(message.get("ts") or "").strip())


def latest_slack_ts(messages: list[dict[str, Any]]) -> str | None:
    values = [str(message.get("ts") or "") for message in messages if message.get("ts")]
    return max(values, key=float) if values else None


def slack_message_ts(message: dict[str, Any]) -> float:
    return float(str(message.get("ts") or "0"))


def slack_timestamp_to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(float(value), UTC)


def slack_message_to_sync_item(
    *,
    source: ConnectedSource,
    detail: ConnectedSourceSlackChannel,
    message: dict[str, Any],
) -> SyncItem:
    ts = str(message["ts"])
    text = str(message.get("text") or "").strip()
    event_timestamp = slack_timestamp_to_datetime(ts) or datetime.now(UTC)
    source_url = f"https://slack.com/app_redirect?channel={detail.channel_id}&message_ts={ts}"
    source_payload = {
        "source_item": {
            "source_type": "slack",
            "event_type": "message",
            "channel_name": detail.channel_name,
            "channel_id": detail.channel_id,
            "message_ts": ts,
            "thread_ts": message.get("thread_ts"),
            "author": message.get("user") or message.get("username"),
            "text": text,
            "source_url": source_url,
            "source_timestamp": event_timestamp.isoformat(),
        }
    }
    return SyncItem(
        external_event_id=f"{detail.channel_id}:{ts}",
        idempotency_key=f"sync:slack:{source.connected_source_id}:{ts}",
        source_url=source_url,
        source_event_timestamp=event_timestamp,
        technical_metadata={
            "sync_kind": "poll",
            "channel_id": detail.channel_id,
            "channel_name": detail.channel_name,
            "message_ts": ts,
            "thread_ts": message.get("thread_ts"),
        },
        raw_payload_json=source_payload,
    )


def jira_issue_to_sync_items(
    *,
    source: ConnectedSource,
    detail: ConnectedSourceJiraIssue,
    issue: dict[str, Any],
    base_url: str,
    since: datetime | None,
    until: datetime | None = None,
) -> list[SyncItem]:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    issue_summary = str(fields.get("summary") or issue.get("key") or detail.issue_key)
    issue_url = detail.issue_url or f"{base_url}/browse/{detail.issue_key}"
    items: list[SyncItem] = []
    histories = nested_list(issue, "changelog", "histories")

    description = jira_text(fields.get("description"))
    description_timestamp = jira_description_timestamp(fields=fields, histories=histories)
    if description and should_include_jira_sync_item(
        description_timestamp,
        since=since,
        until=until,
    ):
        description_digest = hashlib.sha256(description.encode("utf-8")).hexdigest()[:16]
        items.append(
            SyncItem(
                external_event_id=(
                    f"{detail.issue_key}:description:"
                    f"{description_timestamp.isoformat()}:{description_digest}"
                ),
                idempotency_key=(
                    f"sync:jira:{source.connected_source_id}:description:"
                    f"{description_timestamp.isoformat()}:{description_digest}"
                ),
                source_url=issue_url,
                source_event_timestamp=description_timestamp,
                technical_metadata={
                    "sync_kind": "poll",
                    "issue_key": detail.issue_key,
                    "event_type": "description",
                },
                raw_payload_json={
                    "source_item": {
                        "source_type": "jira",
                        "event_type": "description",
                        "issue_key": detail.issue_key,
                        "issue_summary": issue_summary,
                        "body": description,
                        "source_url": issue_url,
                        "source_timestamp": description_timestamp.isoformat(),
                    }
                },
            )
        )

    comments = nested_list(fields, "comment", "comments")
    for comment in comments:
        comment_id = str(comment.get("id") or "")
        body = jira_text(comment.get("body"))
        event_timestamp = parse_jira_datetime(comment.get("updated") or comment.get("created"))
        if not comment_id or not body or not should_include_jira_sync_item(
            event_timestamp,
            since=since,
            until=until,
        ):
            continue
        source_url = f"{issue_url}?focusedCommentId={comment_id}"
        items.append(
            SyncItem(
                external_event_id=f"{detail.issue_key}:comment:{comment_id}",
                idempotency_key=f"sync:jira:{source.connected_source_id}:comment:{comment_id}",
                source_url=source_url,
                source_event_timestamp=event_timestamp,
                technical_metadata={
                    "sync_kind": "poll",
                    "issue_key": detail.issue_key,
                    "event_type": "comment",
                    "comment_id": comment_id,
                },
                raw_payload_json={
                    "source_item": {
                        "source_type": "jira",
                        "event_type": "comment",
                        "issue_key": detail.issue_key,
                        "issue_summary": issue_summary,
                        "comment_id": comment_id,
                        "author": jira_user_name(comment.get("author")),
                        "body": body,
                        "source_url": source_url,
                        "source_timestamp": event_timestamp.isoformat(),
                    }
                },
            )
        )

    for history in histories:
        history_id = str(history.get("id") or "")
        event_timestamp = parse_jira_datetime(history.get("created"))
        changed_items = [
            item for item in history.get("items", [])
            if isinstance(item, dict) and is_meaningful_jira_change(item)
        ]
        if not history_id or not changed_items or not should_include_jira_sync_item(
            event_timestamp,
            since=since,
            until=until,
        ):
            continue
        items.append(
            SyncItem(
                external_event_id=f"{detail.issue_key}:changelog:{history_id}",
                idempotency_key=f"sync:jira:{source.connected_source_id}:changelog:{history_id}",
                source_url=issue_url,
                source_event_timestamp=event_timestamp,
                technical_metadata={
                    "sync_kind": "poll",
                    "issue_key": detail.issue_key,
                    "event_type": "changelog",
                    "history_id": history_id,
                    "changed_fields": [item.get("field") for item in changed_items],
                },
                raw_payload_json={
                    "source_item": {
                        "source_type": "jira",
                        "event_type": "changelog",
                        "issue_key": detail.issue_key,
                        "issue_summary": issue_summary,
                        "history_id": history_id,
                        "author": jira_user_name(history.get("author")),
                        "changes": changed_items,
                        "source_url": issue_url,
                        "source_timestamp": event_timestamp.isoformat(),
                    }
                },
            )
        )

    return sorted(items, key=lambda item: item.source_event_timestamp)


def jira_description_timestamp(
    *,
    fields: dict[str, Any],
    histories: list[dict[str, Any]],
) -> datetime:
    description_change_times = [
        parse_jira_datetime(history.get("created"))
        for history in histories
        if any(
            isinstance(item, dict)
            and str(item.get("field") or "").strip().lower() == "description"
            for item in history.get("items", [])
        )
    ]
    if description_change_times:
        return max(description_change_times)
    return parse_jira_datetime(fields.get("created") or fields.get("updated"))


def should_include_jira_sync_item(
    event_timestamp: datetime,
    *,
    since: datetime | None,
    until: datetime | None,
) -> bool:
    if since is not None and event_timestamp <= since:
        return False
    if until is not None and event_timestamp > until:
        return False
    return True


def nested_list(payload: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return []
        current = current.get(key)
    if not isinstance(current, list):
        return []
    return [item for item in current if isinstance(item, dict)]


def jira_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return extract_adf_text(value).strip()
    return str(value).strip()


def extract_adf_text(node: Any) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return " ".join(extract_adf_text(item) for item in node)
    if not isinstance(node, dict):
        return ""
    parts: list[str] = []
    if node.get("type") == "text" and node.get("text"):
        parts.append(str(node["text"]))
    content = node.get("content")
    if isinstance(content, list):
        parts.append(extract_adf_text(content))
    return " ".join(part for part in parts if part)


def parse_jira_datetime(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        return datetime.now(UTC)
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    if len(cleaned) > 5 and cleaned[-5] in {"+", "-"} and cleaned[-3] != ":":
        cleaned = cleaned[:-2] + ":" + cleaned[-2:]
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def jira_user_name(user: Any) -> str | None:
    if not isinstance(user, dict):
        return None
    return user.get("displayName") or user.get("name") or user.get("emailAddress")


def is_meaningful_jira_change(item: dict[str, Any]) -> bool:
    field = str(item.get("field") or "").strip().lower()
    if not field:
        return False
    if field in {
        "status",
        "priority",
        "severity",
        "duedate",
        "due date",
        "attachment",
    }:
        return True
    return any(keyword in field for keyword in ("target", "dependency", "link", "blocked"))
