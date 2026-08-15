import json
import re
import uuid
from collections import Counter
from datetime import date
from html import unescape

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.rulebooks import RulebookLoader
from app.agents.runtime.client import AIRuntimeConfigurationError, build_ai_client_runtime
from app.db.models.partner import Partner, PartnerStatus
from app.db.models.partner_metadata import (
    PartnerMetadataSnapshot,
    PartnerResourceLink,
)
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateStatus
from app.db.models.topic_update import TopicUpdate, TopicUpdateStatus
from app.domains.contributor.metadata.service import format_cycle_month, parse_cycle_month
from app.domains.presenter.schemas import (
    DecisionBoardItem,
    DraftEmailResponse,
    PresenterAnalysisResponse,
    PresenterAskResponse,
    PresenterDecisionBoardResponse,
    PresenterDecisionBoardSignal,
    PresenterExecutiveSummaryResponse,
    PresenterMetadataResponse,
    PresenterMetadataRiskResponse,
    PresenterPartnerResponse,
    PresenterResourceLinkResponse,
    PresenterUpdateResponse,
)


class PresenterService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_partners(
        self,
        *,
        cycle: str,
        date_start: date | None = None,
        date_end: date | None = None,
    ) -> list[PresenterPartnerResponse]:
        start_month, end_month = resolve_period_month_bounds(
            cycle=cycle,
            date_start=date_start,
            date_end=date_end,
        )
        statement = (
            select(
                Partner,
                func.count(PartnerUpdate.update_id).label("approved_updates_count"),
                func.max(PartnerUpdate.approved_at).label("last_activity_at"),
            )
            .outerjoin(
                PartnerUpdate,
                (PartnerUpdate.partner_id == Partner.partner_id)
                & (PartnerUpdate.cycle_month >= start_month)
                & (PartnerUpdate.cycle_month <= end_month)
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
        date_start: date | None = None,
        date_end: date | None = None,
    ) -> list[PresenterUpdateResponse]:
        start_month, end_month = resolve_period_month_bounds(
            cycle=cycle,
            date_start=date_start,
            date_end=date_end,
        )
        scoped_partner_ids = normalize_partner_scope(partner_id=partner_id, partner_ids=partner_ids)
        partner_statement = (
            select(PartnerUpdate, Partner)
            .join(Partner, Partner.partner_id == PartnerUpdate.partner_id)
            .where(Partner.status == PartnerStatus.active.value)
            .where(PartnerUpdate.cycle_month >= start_month)
            .where(PartnerUpdate.cycle_month <= end_month)
            .where(PartnerUpdate.status == PartnerUpdateStatus.approved.value)
            .order_by(
                PartnerUpdate.cycle_month.desc(),
                PartnerUpdate.approved_at.desc().nullslast(),
                Partner.name.asc(),
                PartnerUpdate.updated_at.desc(),
            )
        )
        if scoped_partner_ids:
            partner_statement = partner_statement.where(Partner.partner_id.in_(scoped_partner_ids))
        cleaned_search = search.strip() if search else ""
        if cleaned_search:
            query = f"%{cleaned_search.lower()}%"
            partner_statement = partner_statement.where(
                or_(
                    func.lower(Partner.name).like(query),
                    func.lower(PartnerUpdate.title).like(query),
                    func.lower(PartnerUpdate.summary).like(query),
                    func.lower(PartnerUpdate.source_label).like(query),
                )
            )
        partner_result = await self.db.execute(partner_statement)
        responses = [
            self._update_to_response(update, partner) for update, partner in partner_result.all()
        ]

        if not scoped_partner_ids:
            topic_statement = (
                select(TopicUpdate)
                .where(TopicUpdate.cycle_month >= start_month)
                .where(TopicUpdate.cycle_month <= end_month)
                .where(TopicUpdate.status == TopicUpdateStatus.approved.value)
                .order_by(
                    TopicUpdate.cycle_month.desc(),
                    TopicUpdate.approved_at.desc().nullslast(),
                    TopicUpdate.topic_label.asc(),
                    TopicUpdate.updated_at.desc(),
                )
            )
            if cleaned_search:
                query = f"%{cleaned_search.lower()}%"
                topic_statement = topic_statement.where(
                    or_(
                        func.lower(TopicUpdate.topic_label).like(query),
                        func.lower(TopicUpdate.title).like(query),
                        func.lower(TopicUpdate.summary).like(query),
                        func.lower(TopicUpdate.source_label).like(query),
                    )
                )
            topic_result = await self.db.execute(topic_statement)
            responses.extend(
                self._topic_update_to_response(topic_update)
                for topic_update in topic_result.scalars().all()
            )
        return sorted(
            responses,
            key=lambda update: (
                update.cycle,
                update.approved_at.timestamp() if update.approved_at else 0.0,
                update.partner_name,
                update.title,
            ),
            reverse=True,
        )

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
        date_start: date | None = None,
        date_end: date | None = None,
    ) -> PresenterAnalysisResponse:
        scoped_partner_ids = normalize_partner_scope(partner_id=partner_id, partner_ids=partner_ids)
        period_label = format_period_label(cycle=cycle, date_start=date_start, date_end=date_end)
        updates = await self.list_approved_updates(
            cycle=cycle,
            partner_id=partner_id,
            partner_ids=partner_ids,
            date_start=date_start,
            date_end=date_end,
        )
        partners = await self.list_partners(
            cycle=cycle,
            date_start=date_start,
            date_end=date_end,
        )
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
            date_start=date_start,
            date_end=date_end,
        )
        return PresenterAnalysisResponse(
            cycle=cycle,
            partner_id=partner_id if len(scoped_partner_ids) <= 1 else None,
            partner_ids=scoped_partner_ids,
            executive_summary=build_executive_summary(
                period_label=period_label,
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
        date_start: date | None = None,
        date_end: date | None = None,
    ) -> DraftEmailResponse:
        scoped_partner_ids = normalize_partner_scope(partner_id=partner_id, partner_ids=partner_ids)
        period_label = format_period_label(cycle=cycle, date_start=date_start, date_end=date_end)
        updates = await self.list_approved_updates(
            cycle=cycle,
            partner_id=partner_id,
            partner_ids=partner_ids,
            date_start=date_start,
            date_end=date_end,
        )
        partner_name = None
        if len(scoped_partner_ids) == 1:
            partner_id = scoped_partner_ids[0]
            partner = await self._get_active_partner_or_404(partner_id)
            partner_name = partner.name
        subject = draft_email_subject(period_label=period_label, partner_name=partner_name)
        body = draft_email_body(
            period_label=period_label,
            partner_name=partner_name,
            updates=updates,
        )
        return DraftEmailResponse(
            cycle=cycle,
            partner_id=partner_id if len(scoped_partner_ids) <= 1 else None,
            partner_ids=scoped_partner_ids,
            subject=subject,
            body=body,
            update_count=len(updates),
        )

    async def ask_ai(
        self,
        *,
        cycle: str,
        question: str,
        partner_id: uuid.UUID | None = None,
        partner_ids: list[uuid.UUID] | None = None,
        date_start: date | None = None,
        date_end: date | None = None,
    ) -> PresenterAskResponse:
        cleaned_question = " ".join(question.split())
        if not cleaned_question:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Question is required.",
            )

        scoped_partner_ids = normalize_partner_scope(partner_id=partner_id, partner_ids=partner_ids)
        updates = await self.list_approved_updates(
            cycle=cycle,
            partner_id=partner_id,
            partner_ids=partner_ids,
            date_start=date_start,
            date_end=date_end,
            search=None,
        )

        try:
            runtime = build_ai_client_runtime()
        except AIRuntimeConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        rulebook = RulebookLoader().load("presenter_chatbot")
        model = runtime.reporting_model or runtime.update_extraction_model
        payload = build_presenter_ask_payload(
            question=cleaned_question,
            cycle=cycle,
            date_start=date_start,
            date_end=date_end,
            scoped_partner_ids=scoped_partner_ids,
            updates=updates,
            rulebook_body=rulebook.body,
            rulebook_trace_version=rulebook.trace_version,
        )

        try:
            response = await runtime.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": presenter_ask_system_prompt()},
                    {
                        "role": "user",
                        "content": json.dumps(payload, sort_keys=True, default=str),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=900,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI assistant failed to answer: {exc}",
            ) from exc

        content = response.choices[0].message.content or "{}"
        answer = parse_presenter_ask_answer(content)
        return PresenterAskResponse(answer=answer, grounded=True, model=model)

    async def generate_executive_summary(
        self,
        *,
        cycle: str,
        partner_id: uuid.UUID | None = None,
        partner_ids: list[uuid.UUID] | None = None,
        date_start: date | None = None,
        date_end: date | None = None,
    ) -> PresenterExecutiveSummaryResponse:
        scoped_partner_ids = normalize_partner_scope(partner_id=partner_id, partner_ids=partner_ids)
        updates = await self.list_approved_updates(
            cycle=cycle,
            partner_id=partner_id,
            partner_ids=partner_ids,
            date_start=date_start,
            date_end=date_end,
            search=None,
        )
        if not updates:
            return PresenterExecutiveSummaryResponse(
                cycle=cycle,
                partner_id=partner_id if len(scoped_partner_ids) <= 1 else None,
                partner_ids=scoped_partner_ids,
                bullets=[],
                source_note="No approved updates are available for this selection.",
                update_count=0,
                grounded=True,
                model=None,
            )

        try:
            runtime = build_ai_client_runtime()
        except AIRuntimeConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        rulebook = RulebookLoader().load("presenter_executive_summary")
        model = runtime.reporting_model or runtime.update_extraction_model
        payload = build_executive_summary_payload(
            cycle=cycle,
            date_start=date_start,
            date_end=date_end,
            scoped_partner_ids=scoped_partner_ids,
            updates=updates,
            rulebook_body=rulebook.body,
            rulebook_trace_version=rulebook.trace_version,
        )

        try:
            response = await runtime.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": executive_summary_system_prompt()},
                    {
                        "role": "user",
                        "content": json.dumps(payload, sort_keys=True, default=str),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=900,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Executive summary agent failed: {exc}",
            ) from exc

        content = response.choices[0].message.content or "{}"
        parsed = parse_executive_summary_response(content)
        return PresenterExecutiveSummaryResponse(
            cycle=cycle,
            partner_id=partner_id if len(scoped_partner_ids) <= 1 else None,
            partner_ids=scoped_partner_ids,
            bullets=parsed["bullets"],
            source_note=parsed["source_note"],
            update_count=len(updates),
            grounded=True,
            model=model,
        )

    async def generate_decision_board(
        self,
        *,
        cycle: str,
        partner_id: uuid.UUID | None = None,
        partner_ids: list[uuid.UUID] | None = None,
        date_start: date | None = None,
        date_end: date | None = None,
    ) -> PresenterDecisionBoardResponse:
        scoped_partner_ids = normalize_partner_scope(partner_id=partner_id, partner_ids=partner_ids)
        updates = await self.list_approved_updates(
            cycle=cycle,
            partner_id=partner_id,
            partner_ids=partner_ids,
            date_start=date_start,
            date_end=date_end,
            search=None,
        )
        if not updates:
            return PresenterDecisionBoardResponse(
                cycle=cycle,
                partner_id=partner_id if len(scoped_partner_ids) <= 1 else None,
                partner_ids=scoped_partner_ids,
                signals=[],
                source_note="No approved updates are available for this selection.",
                update_count=0,
                grounded=True,
                model=None,
            )

        try:
            runtime = build_ai_client_runtime()
        except AIRuntimeConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        rulebook = RulebookLoader().load("decision_board")
        model = runtime.reporting_model or runtime.update_extraction_model
        payload = build_decision_board_payload(
            cycle=cycle,
            date_start=date_start,
            date_end=date_end,
            scoped_partner_ids=scoped_partner_ids,
            updates=updates,
            rulebook_body=rulebook.body,
            rulebook_trace_version=rulebook.trace_version,
        )

        try:
            response = await runtime.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": decision_board_system_prompt()},
                    {
                        "role": "user",
                        "content": json.dumps(payload, sort_keys=True, default=str),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=1100,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Decision board agent failed: {exc}",
            ) from exc

        content = response.choices[0].message.content or "{}"
        parsed = parse_decision_board_response(content)
        return PresenterDecisionBoardResponse(
            cycle=cycle,
            partner_id=partner_id if len(scoped_partner_ids) <= 1 else None,
            partner_ids=scoped_partner_ids,
            signals=parsed["signals"],
            source_note=parsed["source_note"],
            update_count=len(updates),
            grounded=True,
            model=model,
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
            .where(PartnerResourceLink.archived_at.is_(None))
            .order_by(PartnerResourceLink.created_at.asc(), PartnerResourceLink.title.asc())
        )
        return list(result.scalars().all())

    async def _metadata_context(
        self,
        *,
        cycle: str,
        partner_ids: list[uuid.UUID],
        date_start: date | None,
        date_end: date | None,
    ) -> list[dict[str, object]]:
        start_month, end_month = resolve_period_month_bounds(
            cycle=cycle,
            date_start=date_start,
            date_end=date_end,
        )
        statement = (
            select(Partner, PartnerMetadataSnapshot)
            .join(PartnerMetadataSnapshot, PartnerMetadataSnapshot.partner_id == Partner.partner_id)
            .options(selectinload(PartnerMetadataSnapshot.risks))
            .where(Partner.status == PartnerStatus.active.value)
            .where(PartnerMetadataSnapshot.cycle_month >= start_month)
            .where(PartnerMetadataSnapshot.cycle_month <= end_month)
            .order_by(Partner.name.asc(), PartnerMetadataSnapshot.cycle_month.desc())
            .limit(30)
        )
        if partner_ids:
            statement = statement.where(Partner.partner_id.in_(partner_ids))

        result = await self.db.execute(statement)
        rows: list[dict[str, object]] = []
        for partner, snapshot in result.all():
            resources = await self._load_resource_links(partner.partner_id)
            rows.append(
                {
                    "partner_id": str(partner.partner_id),
                    "partner_name": partner.name,
                    "cycle": format_cycle_month(snapshot.cycle_month),
                    "status": snapshot.status,
                    "why_this_partner": snapshot.why_this_partner,
                    "business_priority": snapshot.business_priority,
                    "highlights_status": snapshot.highlights_status,
                    "goals": snapshot.goals,
                    "execution_timeline": snapshot.execution_timeline,
                    "risks": [
                        {
                            "description": risk.description,
                            "green_action": risk.green_action,
                            "severity": risk.severity,
                            "assigned_to": risk.assigned_to,
                            "due_date": risk.due_date,
                            "ramification": risk.ramification,
                        }
                        for risk in sorted(snapshot.risks, key=lambda item: item.sort_order)
                    ],
                    "resources": [
                        {
                            "title": resource.title,
                            "url": resource.url,
                            "description": resource.description,
                            "source_kind": resource.source_kind,
                        }
                        for resource in resources
                    ][:12],
                }
            )
        return rows

    async def _decision_board(
        self,
        *,
        cycle: str,
        partner_id: uuid.UUID | None,
        partner_ids: list[uuid.UUID] | None = None,
        date_start: date | None = None,
        date_end: date | None = None,
    ) -> list[DecisionBoardItem]:
        start_month, end_month = resolve_period_month_bounds(
            cycle=cycle,
            date_start=date_start,
            date_end=date_end,
        )
        scoped_partner_ids = normalize_partner_scope(partner_id=partner_id, partner_ids=partner_ids)
        statement = (
            select(Partner, PartnerMetadataSnapshot)
            .join(
                PartnerMetadataSnapshot,
                PartnerMetadataSnapshot.partner_id == Partner.partner_id,
            )
            .options(selectinload(PartnerMetadataSnapshot.risks))
            .where(Partner.status == PartnerStatus.active.value)
            .where(PartnerMetadataSnapshot.cycle_month >= start_month)
            .where(PartnerMetadataSnapshot.cycle_month <= end_month)
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
            scope="partner",
            topic_label=None,
            cycle=format_cycle_month(update.cycle_month),
            title=update.title,
            summary=update.summary,
            source_type=update.source_type,
            source_label=update.source_label,
            source_url=update.source_url,
            approved_at=update.approved_at,
            approved_by=update.approved_by,
        )

    def _topic_update_to_response(
        self,
        update: TopicUpdate,
    ) -> PresenterUpdateResponse:
        return PresenterUpdateResponse(
            update_id=update.topic_update_id,
            partner_id=None,
            partner_name=update.topic_label,
            scope="topic",
            topic_label=update.topic_label,
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
                    due_date=risk.due_date,
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
    period_label: str,
    updates: list[PresenterUpdateResponse],
    partner_count: int,
) -> str:
    if not updates:
        return f"No approved partner updates are available for {period_label} yet."
    top_partners = Counter(update.partner_name for update in updates).most_common(3)
    partner_phrase = ", ".join(f"{name} ({count})" for name, count in top_partners)
    return (
        f"{period_label} has {len(updates)} approved update(s) across {partner_count} "
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


def resolve_period_month_bounds(
    *,
    cycle: str,
    date_start: date | None,
    date_end: date | None,
) -> tuple[date, date]:
    if date_start is None and date_end is None:
        cycle_month = parse_cycle_month(cycle)
        return cycle_month, cycle_month
    if date_start is None or date_end is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both date_start and date_end are required for range mode.",
        )
    if date_start > date_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_start must be before or equal to date_end.",
        )
    return date_start.replace(day=1), date_end.replace(day=1)


def format_period_label(
    *,
    cycle: str,
    date_start: date | None,
    date_end: date | None,
) -> str:
    if date_start is None or date_end is None:
        return cycle
    return f"{date_start.isoformat()} to {date_end.isoformat()}"


def draft_email_subject(*, period_label: str, partner_name: str | None) -> str:
    scope = partner_name or "Partner Ecosystem"
    title = "Monthly Update" if len(period_label) == 7 else "Update"
    return f"{scope} {title} - {period_label}"


def draft_email_body(
    *,
    period_label: str,
    partner_name: str | None,
    updates: list[PresenterUpdateResponse],
) -> str:
    greeting = "Hello,"
    scope = partner_name or "the partner ecosystem"
    if not updates:
        return (
            f"{greeting}\n\n"
            f"There are no approved updates available for {scope} in {period_label} yet.\n\n"
            "Regards,"
        )
    lines = [
        greeting,
        "",
        f"Please find the approved {period_label} update for {scope}:",
        "",
    ]
    for index, update in enumerate(updates[:12], start=1):
        lines.append(f"{index}. {update.partner_name} - {update.title}")
        summary = html_to_email_text(update.summary)
        if summary:
            lines.extend(f"   {line}" for line in summary.splitlines())
    if len(updates) > 12:
        lines.append("")
        lines.append(f"{len(updates) - 12} additional approved update(s) are available.")
    lines.extend(["", "Regards,"])
    return "\n".join(lines)


def html_to_email_text(value: str) -> str:
    text = normalize_link_html_for_email(value or "")
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</\s*(p|div|ul|ol)\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<\s*li\b[^>]*>", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"</\s*li\s*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def normalize_link_html_for_email(value: str) -> str:
    pattern = re.compile(
        r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        re.IGNORECASE | re.DOTALL,
    )

    def replace(match: re.Match[str]) -> str:
        href = unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
        label = unescape(re.sub(r"<[^>]+>", "", match.group(2))).strip()
        if not label:
            return href
        if href and href != label:
            return f"{label} ({href})"
        return label

    return pattern.sub(replace, value)


def presenter_ask_system_prompt() -> str:
    return (
        "You are the presenter Ask AI assistant for Cloud AI Software Ecosystem Updates.\n"
        "Use only the supplied JSON context and rulebook. Do not use model memory, outside "
        "knowledge, assumptions, or invented bridge text for factual claims.\n"
        "If the context does not answer the question, answer exactly: "
        "\"I do not see that in the selected approved updates.\"\n"
        "Return JSON only with this shape: {\"answer\": \"plain text or simple markdown\"}.\n"
        "Preserve quantitative facts and relevant links. Do not combine distinct facts with "
        "semicolons; use separate bullets instead."
    )


def build_presenter_ask_payload(
    *,
    question: str,
    cycle: str,
    date_start: date | None,
    date_end: date | None,
    scoped_partner_ids: list[uuid.UUID],
    updates: list[PresenterUpdateResponse],
    rulebook_body: str,
    rulebook_trace_version: str,
) -> dict[str, object]:
    return {
        "question": question,
        "scope": {
            "cycle": cycle,
            "date_start": date_start.isoformat() if date_start else None,
            "date_end": date_end.isoformat() if date_end else None,
            "partner_ids": [str(partner_id) for partner_id in scoped_partner_ids],
            "partner_scope": "selected" if scoped_partner_ids else "all_partners",
        },
        "rulebook": {
            "trace_version": rulebook_trace_version,
            "body": rulebook_body,
        },
        "approved_updates": [
            {
                "update_id": str(update.update_id),
                "partner_id": str(update.partner_id) if update.partner_id else None,
                "partner_name": update.partner_name,
                "scope": update.scope,
                "topic_label": update.topic_label,
                "cycle": update.cycle,
                "title": update.title,
                "summary": strip_html(update.summary),
                "source_type": update.source_type.value,
                "source_label": update.source_label,
                "source_url": update.source_url,
                "approved_at": update.approved_at.isoformat() if update.approved_at else None,
            }
            for update in updates[:80]
        ],
        "output_contract": {
            "answer": (
                "Grounded answer only. Use bullets for multiple facts. Use markdown links "
                "only when the URL is supplied in context."
            ),
        },
    }


def parse_presenter_ask_answer(content: str) -> str:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI assistant returned an invalid response.",
        ) from exc
    answer = str(parsed.get("answer") or "").strip() if isinstance(parsed, dict) else ""
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI assistant returned an empty answer.",
        )
    return answer


def executive_summary_system_prompt() -> str:
    return (
        "You are the presenter executive summary agent for Cloud AI Software Ecosystem Updates.\n"
        "Use only the supplied approved updates and rulebook. Do not use model memory, "
        "outside knowledge, metadata, decision-board data, or assumptions.\n"
        "Return JSON only with this shape: {\"bullets\": [\"...\"], \"source_note\": \"...\"}.\n"
        "If there are no usable approved update facts, return an empty bullets array. "
        "Preserve quantitative facts and source links when they are supplied."
    )


def build_executive_summary_payload(
    *,
    cycle: str,
    date_start: date | None,
    date_end: date | None,
    scoped_partner_ids: list[uuid.UUID],
    updates: list[PresenterUpdateResponse],
    rulebook_body: str,
    rulebook_trace_version: str,
) -> dict[str, object]:
    return {
        "task": "presenter_executive_summary",
        "scope": {
            "cycle": cycle,
            "date_start": date_start.isoformat() if date_start else None,
            "date_end": date_end.isoformat() if date_end else None,
            "partner_ids": [str(partner_id) for partner_id in scoped_partner_ids],
            "partner_scope": "selected" if scoped_partner_ids else "all_partners",
        },
        "rulebook": {
            "trace_version": rulebook_trace_version,
            "body": rulebook_body,
        },
        "approved_updates": [
            {
                "update_id": str(update.update_id),
                "partner_id": str(update.partner_id) if update.partner_id else None,
                "partner_name": update.partner_name,
                "scope": update.scope,
                "topic_label": update.topic_label,
                "cycle": update.cycle,
                "title": update.title,
                "summary": strip_html(update.summary),
                "source_type": update.source_type.value,
                "source_label": update.source_label,
                "source_url": update.source_url,
                "approved_at": update.approved_at.isoformat() if update.approved_at else None,
            }
            for update in updates[:80]
        ],
        "output_contract": {
            "bullets": "3-6 concise executive bullets, each grounded in approved updates.",
            "source_note": "Optional short scope/data note.",
        },
    }


def parse_executive_summary_response(content: str) -> dict[str, list[str] | str | None]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Executive summary agent returned an invalid response.",
        ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Executive summary agent returned an invalid response.",
        )

    raw_bullets = parsed.get("bullets") or []
    if not isinstance(raw_bullets, list):
        raw_bullets = []
    bullets = [" ".join(str(item).split()) for item in raw_bullets[:8] if str(item).strip()]
    source_note = parsed.get("source_note")
    cleaned_note = " ".join(str(source_note).split()) if source_note else None
    return {"bullets": bullets, "source_note": cleaned_note}


def decision_board_system_prompt() -> str:
    return (
        "You are the presenter Decision Board agent for Cloud AI Software Ecosystem Updates.\n"
        "Use only the supplied approved updates and rulebook. Do not use model memory, "
        "outside knowledge, partner metadata, pending updates, or assumptions.\n"
        "Return JSON only with this shape: "
        "{\"signals\": [{\"partner_id\": \"...\", \"partner_name\": \"...\", "
        "\"priority\": \"P1|P2|P3\", \"title\": \"...\", \"action\": \"...\", "
        "\"rationale\": \"...\", \"owner\": \"...\", \"due_date\": \"...\", "
        "\"severity\": \"...\", \"source_label\": \"...\", \"source_url\": \"...\"}], "
        "\"source_note\": \"...\"}.\n"
        "If no approved update contains a decision, blocker, owner ask, deadline, risk, "
        "or explicit next action, return an empty signals array. Preserve quantitative "
        "facts and source links. Do not combine distinct facts with semicolons; use "
        "separate cards or concise separate clauses."
    )


def build_decision_board_payload(
    *,
    cycle: str,
    date_start: date | None,
    date_end: date | None,
    scoped_partner_ids: list[uuid.UUID],
    updates: list[PresenterUpdateResponse],
    rulebook_body: str,
    rulebook_trace_version: str,
) -> dict[str, object]:
    return {
        "task": "presenter_decision_board",
        "scope": {
            "cycle": cycle,
            "date_start": date_start.isoformat() if date_start else None,
            "date_end": date_end.isoformat() if date_end else None,
            "partner_ids": [str(partner_id) for partner_id in scoped_partner_ids],
            "partner_scope": "selected" if scoped_partner_ids else "all_partners",
        },
        "rulebook": {
            "trace_version": rulebook_trace_version,
            "body": rulebook_body,
        },
        "approved_updates": [
            {
                "update_id": str(update.update_id),
                "partner_id": str(update.partner_id) if update.partner_id else None,
                "partner_name": update.partner_name,
                "scope": update.scope,
                "topic_label": update.topic_label,
                "cycle": update.cycle,
                "title": update.title,
                "summary": strip_html(update.summary),
                "source_type": update.source_type.value,
                "source_label": update.source_label,
                "source_url": update.source_url,
                "approved_at": update.approved_at.isoformat() if update.approved_at else None,
            }
            for update in updates[:80]
        ],
        "output_contract": {
            "signals": (
                "0-12 decision cards. Each card must be grounded in one or more approved "
                "updates and must include title, action, and rationale."
            ),
            "source_note": "Optional short scope/data note.",
        },
    }


def parse_decision_board_response(
    content: str,
) -> dict[str, list[PresenterDecisionBoardSignal] | str | None]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Decision board agent returned an invalid response.",
        ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Decision board agent returned an invalid response.",
        )

    raw_signals = parsed.get("signals") or []
    if not isinstance(raw_signals, list):
        raw_signals = []

    signals: list[PresenterDecisionBoardSignal] = []
    for raw_item in raw_signals[:12]:
        if not isinstance(raw_item, dict):
            continue
        title = clean_agent_text(raw_item.get("title"))
        action = clean_agent_text(raw_item.get("action"))
        rationale = clean_agent_text(raw_item.get("rationale"))
        if not title or not action or not rationale:
            continue
        signals.append(
            PresenterDecisionBoardSignal(
                partner_id=parse_optional_uuid(raw_item.get("partner_id")),
                partner_name=clean_agent_text(raw_item.get("partner_name")) or None,
                priority=normalize_priority(raw_item.get("priority")),
                title=title,
                action=action,
                rationale=rationale,
                owner=clean_agent_text(raw_item.get("owner")) or None,
                due_date=clean_agent_text(raw_item.get("due_date")) or None,
                severity=clean_agent_text(raw_item.get("severity")) or None,
                source_label=clean_agent_text(raw_item.get("source_label")) or None,
                source_url=clean_agent_text(raw_item.get("source_url")) or None,
            )
        )

    source_note = parsed.get("source_note")
    cleaned_note = clean_agent_text(source_note) or None
    return {"signals": signals, "source_note": cleaned_note}


def clean_agent_text(value: object) -> str:
    return " ".join(str(value or "").split())


def parse_optional_uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def normalize_priority(value: object) -> str | None:
    priority = clean_agent_text(value).upper()
    if priority in {"P1", "P2", "P3"}:
        return priority
    return None


def strip_html(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(without_tags.split())
