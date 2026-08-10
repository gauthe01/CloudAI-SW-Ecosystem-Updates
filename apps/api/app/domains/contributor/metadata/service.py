import uuid
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.partner_metadata import (
    PartnerMetadataRisk,
    PartnerMetadataSnapshot,
    PartnerResourceLink,
    ResourceLinkSourceKind,
)
from app.domains.contributor.metadata.schemas import (
    PartnerMetadataResponse,
    PartnerMetadataRiskPayload,
    PartnerMetadataRiskResponse,
    PartnerMetadataSaveRequest,
    PartnerResourceLinkPayload,
    PartnerResourceLinkResponse,
)
from app.domains.identity.schemas import UserResponse


class ContributorMetadataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_metadata(
        self,
        *,
        partner_id: uuid.UUID,
        cycle: str,
        current_user: UserResponse,
    ) -> PartnerMetadataResponse:
        cycle_month = parse_cycle_month(cycle)
        await self._ensure_assigned_active_partner(partner_id, current_user)
        snapshot = await self._load_snapshot(partner_id, cycle_month)
        resources = await self._load_resource_links(partner_id)
        return self._to_response(
            partner_id=partner_id,
            cycle_month=cycle_month,
            snapshot=snapshot,
            resources=resources,
        )

    async def save_metadata(
        self,
        *,
        partner_id: uuid.UUID,
        cycle: str,
        payload: PartnerMetadataSaveRequest,
        current_user: UserResponse,
    ) -> PartnerMetadataResponse:
        cycle_month = parse_cycle_month(cycle)
        await self._ensure_assigned_active_partner(partner_id, current_user)

        snapshot = await self._load_snapshot(partner_id, cycle_month)
        now = datetime.now(UTC)
        if snapshot is None:
            snapshot = PartnerMetadataSnapshot(
                partner_id=partner_id,
                cycle_month=cycle_month,
                created_at=now,
            )
            self.db.add(snapshot)
            await self.db.flush()

        snapshot.status = payload.status.value if payload.status else None
        snapshot.why_this_partner = clean_optional(payload.why_this_partner)
        snapshot.business_priority = clean_optional(payload.business_priority)
        snapshot.highlights_status = clean_optional(payload.highlights_status)
        snapshot.goals = clean_optional(payload.goals)
        snapshot.execution_timeline = clean_optional(payload.execution_timeline)
        snapshot.saved_by = current_user.user_id
        snapshot.saved_at = now
        snapshot.updated_at = now

        await self.db.execute(
            delete(PartnerMetadataRisk).where(
                PartnerMetadataRisk.metadata_id == snapshot.metadata_id
            )
        )
        self.db.add_all(
            [
                self._risk_payload_to_model(snapshot.metadata_id, risk, index)
                for index, risk in enumerate(payload.risks)
                if risk.description
            ]
        )

        await self.db.execute(
            delete(PartnerResourceLink).where(
                PartnerResourceLink.partner_id == partner_id,
                PartnerResourceLink.source_kind == ResourceLinkSourceKind.manual.value,
            )
        )
        self.db.add_all(
            [
                self._resource_payload_to_model(partner_id, resource, current_user.user_id, now)
                for resource in payload.resources
            ]
        )

        await self.db.commit()
        snapshot = await self._load_snapshot(partner_id, cycle_month)
        resources = await self._load_resource_links(partner_id)
        return self._to_response(
            partner_id=partner_id,
            cycle_month=cycle_month,
            snapshot=snapshot,
            resources=resources,
        )

    async def _ensure_assigned_active_partner(
        self,
        partner_id: uuid.UUID,
        current_user: UserResponse,
    ) -> None:
        statement = (
            select(Partner.partner_id)
            .join(
                PartnerContributorAssignment,
                PartnerContributorAssignment.partner_id == Partner.partner_id,
            )
            .where(Partner.partner_id == partner_id)
            .where(PartnerContributorAssignment.user_id == current_user.user_id)
            .where(Partner.status == PartnerStatus.active.value)
        )
        result = await self.db.execute(statement)
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Partner metadata is not assigned to this contributor.",
            )

    async def _load_snapshot(
        self,
        partner_id: uuid.UUID,
        cycle_month: date,
    ) -> PartnerMetadataSnapshot | None:
        statement = (
            select(PartnerMetadataSnapshot)
            .options(selectinload(PartnerMetadataSnapshot.risks))
            .where(PartnerMetadataSnapshot.partner_id == partner_id)
            .where(PartnerMetadataSnapshot.cycle_month == cycle_month)
            .execution_options(populate_existing=True)
        )
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def _load_resource_links(self, partner_id: uuid.UUID) -> list[PartnerResourceLink]:
        statement = (
            select(PartnerResourceLink)
            .where(PartnerResourceLink.partner_id == partner_id)
            .order_by(PartnerResourceLink.created_at.asc(), PartnerResourceLink.title.asc())
        )
        result = await self.db.execute(statement)
        return list(result.scalars().all())

    def _risk_payload_to_model(
        self,
        metadata_id: uuid.UUID,
        risk: PartnerMetadataRiskPayload,
        sort_order: int,
    ) -> PartnerMetadataRisk:
        return PartnerMetadataRisk(
            metadata_id=metadata_id,
            sort_order=sort_order,
            description=risk.description,
            green_action=clean_optional(risk.green_action),
            severity=clean_optional(risk.severity),
            assigned_to=clean_optional(risk.assigned_to),
            due_date=risk.due_date,
            ramification=clean_optional(risk.ramification),
        )

    def _resource_payload_to_model(
        self,
        partner_id: uuid.UUID,
        resource: PartnerResourceLinkPayload,
        user_id: uuid.UUID,
        now: datetime,
    ) -> PartnerResourceLink:
        return PartnerResourceLink(
            partner_id=partner_id,
            title=resource.title,
            url=str(resource.url),
            description=clean_optional(resource.description),
            source_kind=ResourceLinkSourceKind.manual.value,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )

    def _to_response(
        self,
        *,
        partner_id: uuid.UUID,
        cycle_month: date,
        snapshot: PartnerMetadataSnapshot | None,
        resources: list[PartnerResourceLink],
    ) -> PartnerMetadataResponse:
        ordered_risks = sorted(snapshot.risks, key=lambda risk: risk.sort_order) if snapshot else []
        return PartnerMetadataResponse(
            metadata_id=snapshot.metadata_id if snapshot else None,
            partner_id=partner_id,
            cycle=format_cycle_month(cycle_month),
            status=snapshot.status if snapshot else None,
            why_this_partner=snapshot.why_this_partner if snapshot else None,
            business_priority=snapshot.business_priority if snapshot else None,
            highlights_status=snapshot.highlights_status if snapshot else None,
            goals=snapshot.goals if snapshot else None,
            execution_timeline=snapshot.execution_timeline if snapshot else None,
            risks=[
                PartnerMetadataRiskResponse(
                    risk_id=risk.risk_id,
                    description=risk.description,
                    green_action=risk.green_action,
                    severity=risk.severity,
                    assigned_to=risk.assigned_to,
                    due_date=risk.due_date,
                    ramification=risk.ramification,
                )
                for risk in ordered_risks
            ],
            resources=[
                PartnerResourceLinkResponse(
                    resource_link_id=resource.resource_link_id,
                    title=resource.title,
                    url=resource.url,
                    description=resource.description,
                    source_kind=ResourceLinkSourceKind(resource.source_kind),
                    disabled=resource.archived_at is not None,
                    archived_at=resource.archived_at,
                )
                for resource in resources
            ],
            saved_at=snapshot.saved_at if snapshot else None,
            saved_by=snapshot.saved_by if snapshot else None,
        )


def parse_cycle_month(cycle: str) -> date:
    try:
        year_text, month_text = cycle.split("-", 1)
        year = int(year_text)
        month = int(month_text)
        return date(year, month, 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cycle must use YYYY-MM format.",
        ) from exc


def format_cycle_month(cycle_month: date) -> str:
    return cycle_month.strftime("%Y-%m")


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
