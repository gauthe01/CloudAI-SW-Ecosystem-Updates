import re
import uuid
from datetime import UTC, datetime
from urllib.parse import unquote, urlparse

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.connected_source import (
    ConnectedSource,
    ConnectedSourceConfluencePage,
    ConnectedSourceGitHubTarget,
    ConnectedSourceJiraIssue,
    ConnectedSourceSharePointFile,
    ConnectedSourceSlackChannel,
    ConnectedSourceStatus,
    ConnectedSourceType,
)
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.domains.contributor.connected_sources.schemas import (
    ConnectedSourceDetailResponse,
    ConnectedSourceRequest,
    ConnectedSourceResponse,
)
from app.domains.identity.schemas import UserResponse

JIRA_ISSUE_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
GITHUB_PATH_PATTERN = re.compile(
    r"^/(?P<owner>[^/]+)/(?P<repo>[^/]+)(?:/(?P<section>issues|pull)/(?P<number>\d+))?/?$"
)

NON_DUPLICATE_STATUSES = {
    ConnectedSourceStatus.rejected.value,
    ConnectedSourceStatus.archived.value,
}


class ContributorConnectedSourceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_sources(
        self,
        *,
        partner_id: uuid.UUID,
        current_user: UserResponse,
    ) -> list[ConnectedSourceResponse]:
        await self._ensure_assigned_active_partner(partner_id, current_user)
        result = await self.db.execute(
            select(ConnectedSource)
            .where(ConnectedSource.partner_id == partner_id)
            .order_by(ConnectedSource.created_at.desc(), ConnectedSource.display_name.asc())
        )
        return [await self._to_response(source) for source in result.scalars().all()]

    async def create_source(
        self,
        *,
        partner_id: uuid.UUID,
        payload: ConnectedSourceRequest,
        current_user: UserResponse,
    ) -> ConnectedSourceResponse:
        await self._ensure_assigned_active_partner(partner_id, current_user)
        normalized = normalize_source_payload(payload)
        await self._ensure_not_exact_duplicate(
            partner_id=partner_id,
            source_type=payload.source_type,
            external_identifier=normalized.external_identifier,
            source_url=normalized.source_url,
        )
        now = datetime.now(UTC)
        source = ConnectedSource(
            partner_id=partner_id,
            source_type=payload.source_type.value,
            status=ConnectedSourceStatus.pending.value,
            display_name=normalized.display_name,
            source_url=normalized.source_url,
            external_identifier=normalized.external_identifier,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(source)
        await self.db.flush()
        self.db.add(normalized.detail_model(source.connected_source_id))
        await self.db.commit()
        return await self._to_response(source)

    async def update_source(
        self,
        *,
        partner_id: uuid.UUID,
        connected_source_id: uuid.UUID,
        payload: ConnectedSourceRequest,
        current_user: UserResponse,
    ) -> ConnectedSourceResponse:
        await self._ensure_assigned_active_partner(partner_id, current_user)
        source = await self._get_source_or_404(partner_id, connected_source_id)
        if source.status not in {
            ConnectedSourceStatus.pending.value,
            ConnectedSourceStatus.rejected.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending or rejected sources can be edited.",
            )
        normalized = normalize_source_payload(payload)
        await self._ensure_not_exact_duplicate(
            partner_id=partner_id,
            source_type=payload.source_type,
            external_identifier=normalized.external_identifier,
            source_url=normalized.source_url,
            exclude_connected_source_id=connected_source_id,
        )
        now = datetime.now(UTC)
        await self._delete_detail_row(source)
        source.source_type = payload.source_type.value
        source.status = ConnectedSourceStatus.pending.value
        source.display_name = normalized.display_name
        source.source_url = normalized.source_url
        source.external_identifier = normalized.external_identifier
        source.rejected_at = None
        source.updated_at = now
        self.db.add(normalized.detail_model(source.connected_source_id))
        await self.db.commit()
        return await self._to_response(source)

    async def archive_source(
        self,
        *,
        partner_id: uuid.UUID,
        connected_source_id: uuid.UUID,
        current_user: UserResponse,
    ) -> ConnectedSourceResponse:
        await self._ensure_assigned_active_partner(partner_id, current_user)
        source = await self._get_source_or_404(partner_id, connected_source_id)
        now = datetime.now(UTC)
        source.status = ConnectedSourceStatus.archived.value
        source.archived_at = now
        source.updated_at = now
        await self.db.commit()
        return await self._to_response(source)

    async def pause_source(
        self,
        *,
        partner_id: uuid.UUID,
        connected_source_id: uuid.UUID,
        current_user: UserResponse,
    ) -> ConnectedSourceResponse:
        await self._ensure_assigned_active_partner(partner_id, current_user)
        source = await self._get_source_or_404(partner_id, connected_source_id)
        if source.status != ConnectedSourceStatus.active.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only active sources can be paused.",
            )
        now = datetime.now(UTC)
        source.status = ConnectedSourceStatus.disabled.value
        source.disabled_at = now
        source.updated_at = now
        await self.db.commit()
        return await self._to_response(source)

    async def resume_source(
        self,
        *,
        partner_id: uuid.UUID,
        connected_source_id: uuid.UUID,
        current_user: UserResponse,
    ) -> ConnectedSourceResponse:
        await self._ensure_assigned_active_partner(partner_id, current_user)
        source = await self._get_source_or_404(partner_id, connected_source_id)
        if source.status != ConnectedSourceStatus.disabled.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only paused sources can be resumed.",
            )
        source.status = ConnectedSourceStatus.active.value
        source.disabled_at = None
        source.updated_at = datetime.now(UTC)
        await self.db.commit()
        return await self._to_response(source)

    async def _ensure_assigned_active_partner(
        self,
        partner_id: uuid.UUID,
        current_user: UserResponse,
    ) -> None:
        result = await self.db.execute(
            select(Partner.partner_id)
            .join(
                PartnerContributorAssignment,
                PartnerContributorAssignment.partner_id == Partner.partner_id,
            )
            .where(Partner.partner_id == partner_id)
            .where(PartnerContributorAssignment.user_id == current_user.user_id)
            .where(Partner.status == PartnerStatus.active.value)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Connected sources are not assigned to this contributor.",
            )

    async def _get_source_or_404(
        self,
        partner_id: uuid.UUID,
        connected_source_id: uuid.UUID,
    ) -> ConnectedSource:
        result = await self.db.execute(
            select(ConnectedSource)
            .where(ConnectedSource.partner_id == partner_id)
            .where(ConnectedSource.connected_source_id == connected_source_id)
        )
        source = result.scalar_one_or_none()
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connected source not found.",
            )
        return source

    async def _ensure_not_exact_duplicate(
        self,
        *,
        partner_id: uuid.UUID,
        source_type: ConnectedSourceType,
        external_identifier: str | None,
        source_url: str | None,
        exclude_connected_source_id: uuid.UUID | None = None,
    ) -> None:
        statement = (
            select(func.count())
            .select_from(ConnectedSource)
            .where(ConnectedSource.partner_id == partner_id)
            .where(ConnectedSource.source_type == source_type.value)
            .where(ConnectedSource.status.notin_(NON_DUPLICATE_STATUSES))
        )
        if external_identifier:
            statement = statement.where(ConnectedSource.external_identifier == external_identifier)
        else:
            statement = statement.where(ConnectedSource.source_url == source_url)
        if exclude_connected_source_id:
            statement = statement.where(
                ConnectedSource.connected_source_id != exclude_connected_source_id
            )
        result = await self.db.execute(statement)
        if int(result.scalar_one()) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This exact connected source already exists for the partner.",
            )

    async def _delete_detail_row(self, source: ConnectedSource) -> None:
        model = detail_model_for_type(ConnectedSourceType(source.source_type))
        await self.db.execute(
            delete(model).where(model.connected_source_id == source.connected_source_id)
        )

    async def _to_response(self, source: ConnectedSource) -> ConnectedSourceResponse:
        details = await self._load_details(source)
        return ConnectedSourceResponse(
            connected_source_id=source.connected_source_id,
            partner_id=source.partner_id,
            source_type=ConnectedSourceType(source.source_type),
            status=ConnectedSourceStatus(source.status),
            contributor_status=contributor_status(source.status),
            display_name=source.display_name,
            source_url=source.source_url,
            external_identifier=source.external_identifier,
            details=details,
            created_by=source.created_by,
            approved_at=source.approved_at,
            rejected_at=source.rejected_at,
            disabled_at=source.disabled_at,
            archived_at=source.archived_at,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )

    async def _load_details(self, source: ConnectedSource) -> ConnectedSourceDetailResponse:
        source_type = ConnectedSourceType(source.source_type)
        model = detail_model_for_type(source_type)
        result = await self.db.execute(
            select(model).where(model.connected_source_id == source.connected_source_id)
        )
        detail = result.scalar_one_or_none()
        if detail is None:
            return ConnectedSourceDetailResponse()
        if source_type == ConnectedSourceType.slack_channel:
            return ConnectedSourceDetailResponse(
                channel_name=detail.channel_name,
                channel_id=detail.channel_id,
                bot_invited_confirmed=detail.bot_invited_confirmed,
            )
        if source_type == ConnectedSourceType.jira_issue:
            return ConnectedSourceDetailResponse(issue_key=detail.issue_key)
        if source_type == ConnectedSourceType.sharepoint_file:
            return ConnectedSourceDetailResponse(file_name=detail.file_name)
        if source_type == ConnectedSourceType.confluence_page:
            return ConnectedSourceDetailResponse(page_title=detail.page_title)
        return ConnectedSourceDetailResponse(
            github_target_kind=detail.target_kind,
            github_repository=detail.repository,
            github_number=detail.number,
        )


class NormalizedConnectedSource:
    def __init__(
        self,
        *,
        display_name: str,
        source_url: str | None,
        external_identifier: str,
        detail_model,
    ) -> None:
        self.display_name = display_name
        self.source_url = source_url
        self.external_identifier = external_identifier
        self.detail_model = detail_model


def normalize_source_payload(payload: ConnectedSourceRequest) -> NormalizedConnectedSource:
    if payload.source_type == ConnectedSourceType.slack_channel:
        channel_name = require_clean(payload.channel_name)
        channel_id = require_clean(payload.channel_id)
        display_name = clean_display_name(payload.display_name, channel_name)
        return NormalizedConnectedSource(
            display_name=display_name,
            source_url=None,
            external_identifier=channel_id,
            detail_model=lambda source_id: ConnectedSourceSlackChannel(
                connected_source_id=source_id,
                channel_name=channel_name,
                channel_id=channel_id,
                bot_invited_confirmed=payload.bot_invited_confirmed,
            ),
        )

    source_url = normalize_url(require_clean(payload.source_url))
    if payload.source_type == ConnectedSourceType.jira_issue:
        issue_key = extract_jira_issue_key(source_url)
        return NormalizedConnectedSource(
            display_name=clean_display_name(payload.display_name, issue_key),
            source_url=source_url,
            external_identifier=issue_key,
            detail_model=lambda source_id: ConnectedSourceJiraIssue(
                connected_source_id=source_id,
                issue_url=source_url,
                issue_key=issue_key,
            ),
        )

    if payload.source_type == ConnectedSourceType.sharepoint_file:
        file_name = last_url_segment(source_url)
        return NormalizedConnectedSource(
            display_name=clean_display_name(payload.display_name, file_name or "SharePoint File"),
            source_url=source_url,
            external_identifier=source_url.lower(),
            detail_model=lambda source_id: ConnectedSourceSharePointFile(
                connected_source_id=source_id,
                file_url=source_url,
                file_name=file_name,
            ),
        )

    if payload.source_type == ConnectedSourceType.confluence_page:
        page_title = last_url_segment(source_url)
        return NormalizedConnectedSource(
            display_name=clean_display_name(payload.display_name, page_title or "Confluence Page"),
            source_url=source_url,
            external_identifier=source_url.lower(),
            detail_model=lambda source_id: ConnectedSourceConfluencePage(
                connected_source_id=source_id,
                page_url=source_url,
                page_title=page_title,
            ),
        )

    github = parse_github_target(source_url)
    expected_type = {
        "repository": ConnectedSourceType.github_repository,
        "issue": ConnectedSourceType.github_issue,
        "pull_request": ConnectedSourceType.github_pull_request,
    }[github["target_kind"]]
    if payload.source_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub URL does not match selected source type.",
        )
    return NormalizedConnectedSource(
        display_name=clean_display_name(payload.display_name, github["display_name"]),
        source_url=source_url,
        external_identifier=github["external_identifier"],
        detail_model=lambda source_id: ConnectedSourceGitHubTarget(
            connected_source_id=source_id,
            target_url=source_url,
            target_kind=github["target_kind"],
            repository=github["repository"],
            number=github["number"],
        ),
    )


def detail_model_for_type(source_type: ConnectedSourceType):
    return {
        ConnectedSourceType.jira_issue: ConnectedSourceJiraIssue,
        ConnectedSourceType.slack_channel: ConnectedSourceSlackChannel,
        ConnectedSourceType.sharepoint_file: ConnectedSourceSharePointFile,
        ConnectedSourceType.confluence_page: ConnectedSourceConfluencePage,
        ConnectedSourceType.github_repository: ConnectedSourceGitHubTarget,
        ConnectedSourceType.github_issue: ConnectedSourceGitHubTarget,
        ConnectedSourceType.github_pull_request: ConnectedSourceGitHubTarget,
    }[source_type]


def contributor_status(status_value: str) -> str:
    if status_value in {
        ConnectedSourceStatus.needs_access_setup.value,
        ConnectedSourceStatus.failed.value,
    }:
        return ConnectedSourceStatus.pending.value
    return status_value


def require_clean(value: str | None) -> str:
    cleaned = value.strip() if value else ""
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Value is required.")
    return cleaned


def clean_display_name(value: str | None, fallback: str) -> str:
    cleaned = value.strip() if value else ""
    return (cleaned or fallback).strip()[:300]


def normalize_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid http(s) URL is required.",
        )
    return value.strip()


def extract_jira_issue_key(source_url: str) -> str:
    match = JIRA_ISSUE_PATTERN.search(source_url.upper())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jira source must be a single Jira issue URL containing an issue key.",
        )
    return match.group(1)


def last_url_segment(source_url: str) -> str | None:
    path = urlparse(source_url).path.rstrip("/")
    if not path:
        return None
    segment = unquote(path.rsplit("/", 1)[-1]).strip()
    return segment or None


def parse_github_target(source_url: str) -> dict:
    parsed = urlparse(source_url)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub source must use github.com.",
        )
    match = GITHUB_PATH_PATTERN.match(parsed.path)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub source must be a repository, issue, or pull request URL.",
        )
    owner = match.group("owner")
    repo = match.group("repo").removesuffix(".git")
    repository = f"{owner}/{repo}"
    section = match.group("section")
    number = int(match.group("number")) if match.group("number") else None
    if section == "issues":
        return {
            "target_kind": "issue",
            "repository": repository,
            "number": number,
            "display_name": f"{repository} issue #{number}",
            "external_identifier": f"github:issue:{repository.lower()}:{number}",
        }
    if section == "pull":
        return {
            "target_kind": "pull_request",
            "repository": repository,
            "number": number,
            "display_name": f"{repository} PR #{number}",
            "external_identifier": f"github:pull_request:{repository.lower()}:{number}",
        }
    return {
        "target_kind": "repository",
        "repository": repository,
        "number": None,
        "display_name": repository,
        "external_identifier": f"github:repository:{repository.lower()}",
    }
