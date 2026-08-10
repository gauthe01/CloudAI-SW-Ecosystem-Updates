import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.connected_source import (
    ConnectedSource,
    ConnectedSourceStatus,
    ConnectedSourceType,
)
from app.db.models.identity import User
from app.db.models.integration import Integration, IntegrationStatus, IntegrationType
from app.db.models.partner import Partner
from app.db.models.partner_metadata import PartnerResourceLink, ResourceLinkSourceKind
from app.domains.admin.connected_sources.schemas import (
    AdminConnectedSourcePartnerResponse,
    AdminConnectedSourceResponse,
    AdminConnectedSourceReviewRequest,
    AdminConnectedSourceUserResponse,
)
from app.domains.contributor.connected_sources.schemas import ConnectedSourceDetailResponse
from app.domains.contributor.connected_sources.service import detail_model_for_type
from app.domains.identity.schemas import UserResponse

ACCESS_TEST_PASSED_SUMMARY = (
    "Access readiness passed. Live external API validation requires provider webhook delivery "
    "through AWS HTTPS or a local tunnel."
)


class AdminConnectedSourceApprovalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_sources(self) -> list[AdminConnectedSourceResponse]:
        result = await self.db.execute(
            select(ConnectedSource)
            .join(Partner, Partner.partner_id == ConnectedSource.partner_id)
            .order_by(
                ConnectedSource.created_at.desc(),
                Partner.name.asc(),
                ConnectedSource.display_name.asc(),
            )
        )
        return [await self._to_response(source) for source in result.scalars().all()]

    async def test_access(self, connected_source_id: uuid.UUID) -> AdminConnectedSourceResponse:
        source = await self._get_source_or_404(connected_source_id)
        if source.status in {
            ConnectedSourceStatus.archived.value,
            ConnectedSourceStatus.rejected.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Archived or rejected sources cannot be access-tested.",
            )

        now = datetime.now(UTC)
        integration = await self._load_required_integration(source)
        if not self._integration_is_enabled(integration):
            source.status = ConnectedSourceStatus.needs_access_setup.value
            source.last_tested_at = now
            source.last_error_summary = (
                f"{display_name_for_integration(required_integration_for_source(source))} "
                "global integration must be enabled before this source can be activated."
            )
            source.updated_at = now
            await self.db.commit()
            return await self._to_response(source)

        source.last_tested_at = now
        source.last_error_summary = ACCESS_TEST_PASSED_SUMMARY
        if source.status in {
            ConnectedSourceStatus.needs_access_setup.value,
            ConnectedSourceStatus.failed.value,
        }:
            source.status = ConnectedSourceStatus.pending.value
        source.updated_at = now
        await self.db.commit()
        return await self._to_response(source)

    async def approve_source(
        self,
        *,
        connected_source_id: uuid.UUID,
        current_admin: UserResponse,
    ) -> AdminConnectedSourceResponse:
        source = await self._get_source_or_404(connected_source_id)
        if source.status != ConnectedSourceStatus.pending.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending sources can be approved.",
            )
        integration = await self._load_required_integration(source)
        if not self._integration_is_enabled(integration):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Enable the global integration before approving this source.",
            )
        if source.last_tested_at is None or source.last_error_summary != ACCESS_TEST_PASSED_SUMMARY:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Run a successful access test before approving this source.",
            )

        now = datetime.now(UTC)
        source.status = ConnectedSourceStatus.active.value
        source.approved_by = current_admin.user_id
        source.approved_at = now
        source.rejected_at = None
        source.disabled_at = None
        source.last_error_summary = None
        source.updated_at = now
        await self._upsert_connected_source_resource_link(source, now)
        await self.db.commit()
        return await self._to_response(source)

    async def reject_source(
        self,
        *,
        connected_source_id: uuid.UUID,
        payload: AdminConnectedSourceReviewRequest,
    ) -> AdminConnectedSourceResponse:
        source = await self._get_source_or_404(connected_source_id)
        if source.status == ConnectedSourceStatus.archived.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Archived sources cannot be rejected.",
            )
        now = datetime.now(UTC)
        source.status = ConnectedSourceStatus.rejected.value
        source.rejected_at = now
        source.approved_by = None
        source.approved_at = None
        source.disabled_at = None
        source.last_error_summary = clean_note(payload.note) or "Rejected by admin."
        source.updated_at = now
        await self.db.commit()
        return await self._to_response(source)

    async def mark_needs_access_setup(
        self,
        *,
        connected_source_id: uuid.UUID,
        payload: AdminConnectedSourceReviewRequest,
    ) -> AdminConnectedSourceResponse:
        source = await self._get_source_or_404(connected_source_id)
        if source.status == ConnectedSourceStatus.archived.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Archived sources cannot be marked for access setup.",
            )
        now = datetime.now(UTC)
        source.status = ConnectedSourceStatus.needs_access_setup.value
        source.approved_by = None
        source.approved_at = None
        source.disabled_at = None
        source.last_error_summary = (
            clean_note(payload.note)
            or "Admin marked this source as needing access setup before activation."
        )
        source.updated_at = now
        await self.db.commit()
        return await self._to_response(source)

    async def disable_source(
        self,
        *,
        connected_source_id: uuid.UUID,
        payload: AdminConnectedSourceReviewRequest,
    ) -> AdminConnectedSourceResponse:
        source = await self._get_source_or_404(connected_source_id)
        if source.status != ConnectedSourceStatus.active.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only active sources can be disabled.",
            )
        now = datetime.now(UTC)
        source.status = ConnectedSourceStatus.disabled.value
        source.disabled_at = now
        source.last_error_summary = clean_note(payload.note) or "Disabled by admin."
        source.updated_at = now
        await self.db.commit()
        return await self._to_response(source)

    async def _get_source_or_404(self, connected_source_id: uuid.UUID) -> ConnectedSource:
        result = await self.db.execute(
            select(ConnectedSource).where(
                ConnectedSource.connected_source_id == connected_source_id
            )
        )
        source = result.scalar_one_or_none()
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connected source not found.",
            )
        return source

    async def _load_required_integration(self, source: ConnectedSource) -> Integration | None:
        integration_type = required_integration_for_source(source)
        result = await self.db.execute(
            select(Integration).where(Integration.integration_type == integration_type.value)
        )
        return result.scalar_one_or_none()

    async def _to_response(self, source: ConnectedSource) -> AdminConnectedSourceResponse:
        partner = await self._load_partner(source.partner_id)
        requested_by = await self._load_user(source.created_by)
        approved_by = await self._load_user(source.approved_by) if source.approved_by else None
        integration_type = required_integration_for_source(source)
        integration = await self._load_required_integration(source)
        details = await self._load_details(source)
        return AdminConnectedSourceResponse(
            connected_source_id=source.connected_source_id,
            partner=AdminConnectedSourcePartnerResponse(
                partner_id=partner.partner_id,
                name=partner.name,
            ),
            source_type=ConnectedSourceType(source.source_type),
            status=ConnectedSourceStatus(source.status),
            review_bucket=review_bucket_for_status(source.status),
            display_name=source.display_name,
            source_url=source.source_url,
            external_identifier=source.external_identifier,
            details=details,
            requested_by=AdminConnectedSourceUserResponse(
                user_id=requested_by.user_id,
                email=requested_by.email,
                display_name=requested_by.display_name,
            ),
            approved_by=(
                AdminConnectedSourceUserResponse(
                    user_id=approved_by.user_id,
                    email=approved_by.email,
                    display_name=approved_by.display_name,
                )
                if approved_by
                else None
            ),
            required_integration_type=integration_type,
            integration_status=(
                IntegrationStatus(integration.status) if integration is not None else None
            ),
            integration_available=self._integration_is_enabled(integration),
            exact_duplicate_count=await self._exact_duplicate_count(source),
            access_test_summary=source.last_error_summary,
            approved_at=source.approved_at,
            rejected_at=source.rejected_at,
            disabled_at=source.disabled_at,
            archived_at=source.archived_at,
            last_tested_at=source.last_tested_at,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )

    async def _load_partner(self, partner_id: uuid.UUID) -> Partner:
        result = await self.db.execute(select(Partner).where(Partner.partner_id == partner_id))
        return result.scalar_one()

    async def _load_user(self, user_id: uuid.UUID) -> User:
        result = await self.db.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one()

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

    async def _exact_duplicate_count(self, source: ConnectedSource) -> int:
        statement = (
            select(func.count())
            .select_from(ConnectedSource)
            .where(ConnectedSource.connected_source_id != source.connected_source_id)
            .where(ConnectedSource.partner_id == source.partner_id)
            .where(ConnectedSource.source_type == source.source_type)
            .where(ConnectedSource.status != ConnectedSourceStatus.archived.value)
        )
        if source.external_identifier:
            statement = statement.where(
                ConnectedSource.external_identifier == source.external_identifier
            )
        else:
            statement = statement.where(ConnectedSource.source_url == source.source_url)
        result = await self.db.execute(statement)
        return int(result.scalar_one())

    def _integration_is_enabled(self, integration: Integration | None) -> bool:
        return integration is not None and integration.status == IntegrationStatus.enabled.value

    async def _upsert_connected_source_resource_link(
        self,
        source: ConnectedSource,
        now: datetime,
    ) -> None:
        if source.source_url is None:
            return
        source_type = ConnectedSourceType(source.source_type)
        if source_type == ConnectedSourceType.slack_channel:
            return

        result = await self.db.execute(
            select(PartnerResourceLink)
            .where(PartnerResourceLink.partner_id == source.partner_id)
            .where(PartnerResourceLink.url == source.source_url)
            .where(PartnerResourceLink.source_kind == ResourceLinkSourceKind.connected_source.value)
        )
        resource_link = result.scalar_one_or_none()
        if resource_link is None:
            self.db.add(
                PartnerResourceLink(
                    partner_id=source.partner_id,
                    title=source.display_name,
                    url=source.source_url,
                    description=resource_link_description(source_type),
                    source_kind=ResourceLinkSourceKind.connected_source.value,
                    created_by=source.created_by,
                    created_at=now,
                    updated_at=now,
                    archived_at=None,
                )
            )
            return

        resource_link.title = source.display_name
        resource_link.description = resource_link.description or resource_link_description(
            source_type
        )
        resource_link.archived_at = None
        resource_link.updated_at = now


def required_integration_for_source(source: ConnectedSource) -> IntegrationType:
    source_type = ConnectedSourceType(source.source_type)
    if source_type == ConnectedSourceType.slack_channel:
        return IntegrationType.slack
    if source_type == ConnectedSourceType.jira_issue:
        return IntegrationType.jira
    if source_type == ConnectedSourceType.sharepoint_file:
        return IntegrationType.sharepoint
    if source_type == ConnectedSourceType.confluence_page:
        return IntegrationType.confluence
    return IntegrationType.github


def display_name_for_integration(integration_type: IntegrationType) -> str:
    return {
        IntegrationType.slack: "Slack",
        IntegrationType.jira: "Jira",
        IntegrationType.sharepoint: "SharePoint / Microsoft Graph",
        IntegrationType.confluence: "Confluence",
        IntegrationType.github: "GitHub",
    }[integration_type]


def resource_link_description(source_type: ConnectedSourceType) -> str:
    return {
        ConnectedSourceType.jira_issue: "Connected Jira source approved for update generation.",
        ConnectedSourceType.sharepoint_file: (
            "Connected SharePoint file approved for update generation."
        ),
        ConnectedSourceType.confluence_page: (
            "Connected Confluence page approved for update generation."
        ),
        ConnectedSourceType.github_repository: (
            "Connected GitHub repository approved for update generation."
        ),
        ConnectedSourceType.github_issue: "Connected GitHub issue approved for update generation.",
        ConnectedSourceType.github_pull_request: (
            "Connected GitHub pull request approved for update generation."
        ),
        ConnectedSourceType.slack_channel: (
            "Connected Slack channel approved for update generation."
        ),
    }[source_type]


def review_bucket_for_status(status_value: str) -> str:
    if status_value == ConnectedSourceStatus.pending.value:
        return "needs_review"
    if status_value == ConnectedSourceStatus.active.value:
        return "active"
    if status_value == ConnectedSourceStatus.rejected.value:
        return "rejected"
    if status_value in {
        ConnectedSourceStatus.needs_access_setup.value,
        ConnectedSourceStatus.failed.value,
        ConnectedSourceStatus.disabled.value,
    }:
        return "attention"
    return "all"


def clean_note(note: str | None) -> str | None:
    if note is None:
        return None
    cleaned = note.strip()
    return cleaned or None
