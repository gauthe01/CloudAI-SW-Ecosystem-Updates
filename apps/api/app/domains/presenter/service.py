import uuid
from collections import Counter
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.partner import Partner, PartnerStatus
from app.db.models.partner_metadata import (
    PartnerMetadataSnapshot,
    PartnerResourceLink,
)
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateStatus
from app.domains.contributor.metadata.service import format_cycle_month, parse_cycle_month
from app.domains.presenter.schemas import (
    DecisionBoardItem,
    DraftEmailResponse,
    PresenterAnalysisResponse,
    PresenterMetadataResponse,
    PresenterMetadataRiskResponse,
    PresenterPartnerResponse,
    PresenterResourceLinkResponse,
    PresenterUpdateResponse,
)


class PresenterService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_partners(self, *, cycle: str) -> list[PresenterPartnerResponse]:
        cycle_month = parse_cycle_month(cycle)
        statement = (
            select(
                Partner,
                func.count(PartnerUpdate.update_id).label("approved_updates_count"),
                func.max(PartnerUpdate.approved_at).label("last_activity_at"),
            )
            .outerjoin(
                PartnerUpdate,
                (PartnerUpdate.partner_id == Partner.partner_id)
                & (PartnerUpdate.cycle_month == cycle_month)
                & (PartnerUpdate.status == PartnerUpdateStatus.approved.value),
            )
            .where(Partner.status == PartnerStatus.active.value)
            .group_by(Partner.partner_id)
            .order_by(Partner.name.asc())
        )
        result = await self.db.execute(statement)
        return [
            PresenterPartnerResponse(
                partner_id=partner.partner_id,
                name=partner.name,
                description=partner.description,
                approved_updates_count=int(approved_updates_count or 0),
                last_activity_at=last_activity_at,
            )
            for partner, approved_updates_count, last_activity_at in result.all()
        ]

    async def list_approved_updates(
        self,
        *,
        cycle: str,
        partner_id: uuid.UUID | None = None,
        partner_ids: list[uuid.UUID] | None = None,
        search: str | None = None,
    ) -> list[PresenterUpdateResponse]:
        cycle_month = parse_cycle_month(cycle)
        scoped_partner_ids = normalize_partner_scope(partner_id=partner_id, partner_ids=partner_ids)
        statement = (
            select(PartnerUpdate, Partner)
            .join(Partner, Partner.partner_id == PartnerUpdate.partner_id)
            .where(Partner.status == PartnerStatus.active.value)
            .where(PartnerUpdate.cycle_month == cycle_month)
            .where(PartnerUpdate.status == PartnerUpdateStatus.approved.value)
            .order_by(
                PartnerUpdate.approved_at.desc().nullslast(),
                Partner.name.asc(),
                PartnerUpdate.updated_at.desc(),
            )
        )
        if scoped_partner_ids:
            statement = statement.where(Partner.partner_id.in_(scoped_partner_ids))
        cleaned_search = search.strip() if search else ""
        if cleaned_search:
            query = f"%{cleaned_search.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(Partner.name).like(query),
                    func.lower(PartnerUpdate.title).like(query),
                    func.lower(PartnerUpdate.summary).like(query),
                    func.lower(PartnerUpdate.source_label).like(query),
                )
            )
        result = await self.db.execute(statement)
        return [self._update_to_response(update, partner) for update, partner in result.all()]

    async def get_partner_metadata(
        self,
        *,
        cycle: str,
        partner_id: uuid.UUID,
    ) -> PresenterMetadataResponse:
        cycle_month = parse_cycle_month(cycle)
        partner = await self._get_active_partner_or_404(partner_id)
        snapshot = await self._load_snapshot(partner_id, cycle_month)
        resources = await self._load_resource_links(partner_id)
        return self._metadata_to_response(
            partner=partner,
            cycle_month=cycle_month,
            snapshot=snapshot,
            resources=resources,
        )

    async def get_analysis(
        self,
        *,
        cycle: str,
        partner_id: uuid.UUID | None = None,
        partner_ids: list[uuid.UUID] | None = None,
    ) -> PresenterAnalysisResponse:
        scoped_partner_ids = normalize_partner_scope(partner_id=partner_id, partner_ids=partner_ids)
        updates = await self.list_approved_updates(
            cycle=cycle,
            partner_id=partner_id,
            partner_ids=partner_ids,
        )
        partners = await self.list_partners(cycle=cycle)
        scoped_partners = [
            partner
            for partner in partners
            if not scoped_partner_ids or partner.partner_id in scoped_partner_ids
        ]
        source_mix = Counter(update.source_type.value for update in updates)
        decision_board = await self._decision_board(
            cycle=cycle,
            partner_id=partner_id,
            partner_ids=partner_ids,
        )
        return PresenterAnalysisResponse(
            cycle=cycle,
            partner_id=partner_id if len(scoped_partner_ids) <= 1 else None,
            partner_ids=scoped_partner_ids,
            executive_summary=build_executive_summary(
                cycle=cycle,
                updates=updates,
                partner_count=len(scoped_partners),
            ),
            decision_board=decision_board,
            update_count=len(updates),
            partner_count=len(scoped_partners),
            source_mix=dict(sorted(source_mix.items())),
        )

    async def draft_email(
        self,
        *,
        cycle: str,
        partner_id: uuid.UUID | None = None,
        partner_ids: list[uuid.UUID] | None = None,
    ) -> DraftEmailResponse:
        scoped_partner_ids = normalize_partner_scope(partner_id=partner_id, partner_ids=partner_ids)
        updates = await self.list_approved_updates(
            cycle=cycle,
            partner_id=partner_id,
            partner_ids=partner_ids,
        )
        partner_name = None
        if len(scoped_partner_ids) == 1:
            partner_id = scoped_partner_ids[0]
            partner = await self._get_active_partner_or_404(partner_id)
            partner_name = partner.name
        subject = draft_email_subject(cycle=cycle, partner_name=partner_name)
        body = draft_email_body(cycle=cycle, partner_name=partner_name, updates=updates)
        return DraftEmailResponse(
            cycle=cycle,
            partner_id=partner_id if len(scoped_partner_ids) <= 1 else None,
            partner_ids=scoped_partner_ids,
            subject=subject,
            body=body,
            update_count=len(updates),
        )

    async def _get_active_partner_or_404(self, partner_id: uuid.UUID) -> Partner:
        result = await self.db.execute(
            select(Partner)
            .where(Partner.partner_id == partner_id)
            .where(Partner.status == PartnerStatus.active.value)
        )
        partner = result.scalar_one_or_none()
        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partner not found.",
            )
        return partner

    async def _load_snapshot(
        self,
        partner_id: uuid.UUID,
        cycle_month: date,
    ) -> PartnerMetadataSnapshot | None:
        result = await self.db.execute(
            select(PartnerMetadataSnapshot)
            .options(selectinload(PartnerMetadataSnapshot.risks))
            .where(PartnerMetadataSnapshot.partner_id == partner_id)
            .where(PartnerMetadataSnapshot.cycle_month == cycle_month)
        )
        return result.scalar_one_or_none()

    async def _load_resource_links(self, partner_id: uuid.UUID) -> list[PartnerResourceLink]:
        result = await self.db.execute(
            select(PartnerResourceLink)
            .where(PartnerResourceLink.partner_id == partner_id)
            .order_by(PartnerResourceLink.created_at.asc(), PartnerResourceLink.title.asc())
        )
        return list(result.scalars().all())

    async def _decision_board(
        self,
        *,
        cycle: str,
        partner_id: uuid.UUID | None,
        partner_ids: list[uuid.UUID] | None = None,
    ) -> list[DecisionBoardItem]:
        cycle_month = parse_cycle_month(cycle)
        scoped_partner_ids = normalize_partner_scope(partner_id=partner_id, partner_ids=partner_ids)
        statement = (
            select(Partner, PartnerMetadataSnapshot)
            .join(
                PartnerMetadataSnapshot,
                PartnerMetadataSnapshot.partner_id == Partner.partner_id,
            )
            .options(selectinload(PartnerMetadataSnapshot.risks))
            .where(Partner.status == PartnerStatus.active.value)
            .where(PartnerMetadataSnapshot.cycle_month == cycle_month)
        )
        if scoped_partner_ids:
            statement = statement.where(Partner.partner_id.in_(scoped_partner_ids))
        result = await self.db.execute(statement)
        items: list[DecisionBoardItem] = []
        for partner, snapshot in result.all():
            for risk in sorted(snapshot.risks, key=lambda item: item.sort_order):
                if (risk.severity or "").lower() in {"amber", "red", "high", "critical"}:
                    items.append(
                        DecisionBoardItem(
                            partner_id=partner.partner_id,
                            partner_name=partner.name,
                            signal=risk.description,
                            rationale=risk.ramification or "Risk requires presenter attention.",
                            severity=risk.severity or "amber",
                        )
                    )
        return items[:12]

    def _update_to_response(
        self,
        update: PartnerUpdate,
        partner: Partner,
    ) -> PresenterUpdateResponse:
        return PresenterUpdateResponse(
            update_id=update.update_id,
            partner_id=partner.partner_id,
            partner_name=partner.name,
            cycle=format_cycle_month(update.cycle_month),
            title=update.title,
            summary=update.summary,
            source_type=update.source_type,
            source_label=update.source_label,
            source_url=update.source_url,
            approved_at=update.approved_at,
            approved_by=update.approved_by,
        )

    def _metadata_to_response(
        self,
        *,
        partner: Partner,
        cycle_month: date,
        snapshot: PartnerMetadataSnapshot | None,
        resources: list[PartnerResourceLink],
    ) -> PresenterMetadataResponse:
        risks = sorted(snapshot.risks, key=lambda risk: risk.sort_order) if snapshot else []
        return PresenterMetadataResponse(
            partner_id=partner.partner_id,
            partner_name=partner.name,
            cycle=format_cycle_month(cycle_month),
            status=snapshot.status if snapshot else None,
            why_this_partner=snapshot.why_this_partner if snapshot else None,
            business_priority=snapshot.business_priority if snapshot else None,
            highlights_status=snapshot.highlights_status if snapshot else None,
            goals=snapshot.goals if snapshot else None,
            execution_timeline=snapshot.execution_timeline if snapshot else None,
            risks=[
                PresenterMetadataRiskResponse(
                    description=risk.description,
                    green_action=risk.green_action,
                    severity=risk.severity,
                    assigned_to=risk.assigned_to,
                    due_date=risk.due_date.isoformat() if risk.due_date else None,
                    ramification=risk.ramification,
                )
                for risk in risks
            ],
            resources=[
                PresenterResourceLinkResponse(
                    resource_link_id=resource.resource_link_id,
                    title=resource.title,
                    url=resource.url,
                    description=resource.description,
                    source_kind=resource.source_kind,
                    disabled=resource.archived_at is not None,
                )
                for resource in resources
            ],
            saved_at=snapshot.saved_at if snapshot else None,
        )


def build_executive_summary(
    *,
    cycle: str,
    updates: list[PresenterUpdateResponse],
    partner_count: int,
) -> str:
    if not updates:
        return f"No approved partner updates are available for {cycle} yet."
    top_partners = Counter(update.partner_name for update in updates).most_common(3)
    partner_phrase = ", ".join(f"{name} ({count})" for name, count in top_partners)
    return (
        f"{cycle} has {len(updates)} approved update(s) across {partner_count} "
        f"partner(s). Most active partner signals: {partner_phrase}."
    )


def normalize_partner_scope(
    *,
    partner_id: uuid.UUID | None,
    partner_ids: list[uuid.UUID] | None,
) -> list[uuid.UUID]:
    ordered_ids: list[uuid.UUID] = []
    if partner_id is not None:
        ordered_ids.append(partner_id)
    for item in partner_ids or []:
        if item not in ordered_ids:
            ordered_ids.append(item)
    return ordered_ids


def draft_email_subject(*, cycle: str, partner_name: str | None) -> str:
    scope = partner_name or "Partner Ecosystem"
    return f"{scope} Monthly Update - {cycle}"


def draft_email_body(
    *,
    cycle: str,
    partner_name: str | None,
    updates: list[PresenterUpdateResponse],
) -> str:
    greeting = "Hello,"
    scope = partner_name or "the partner ecosystem"
    if not updates:
        return (
            f"{greeting}\n\n"
            f"There are no approved updates available for {scope} in {cycle} yet.\n\n"
            "Regards,"
        )
    lines = [
        greeting,
        "",
        f"Please find the approved {cycle} update for {scope}:",
        "",
    ]
    for index, update in enumerate(updates[:12], start=1):
        lines.append(f"{index}. {update.partner_name} - {update.title}")
        lines.append(f"   {update.summary}")
    if len(updates) > 12:
        lines.append("")
        lines.append(f"{len(updates) - 12} additional approved update(s) are available.")
    lines.extend(["", "Regards,"])
    return "\n".join(lines)
