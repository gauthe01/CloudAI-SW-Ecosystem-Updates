import asyncio
import hashlib
import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date
from html import unescape
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.rulebooks import RulebookLoader
from app.agents.runtime.client import (
    AIClientRuntime,
    AIRuntimeConfigurationError,
    build_ai_client_runtime,
)
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
    PresenterAskCitation,
    PresenterAskResponse,
    PresenterAskSection,
    PresenterAskTable,
    PresenterDecisionBoardResponse,
    PresenterDecisionBoardSignal,
    PresenterExecutiveSummaryResponse,
    PresenterMetadataResponse,
    PresenterMetadataRiskResponse,
    PresenterPartnerResponse,
    PresenterResourceLinkResponse,
    PresenterUpdateResponse,
)

DECISION_BOARD_CACHE_MAX_ITEMS = 128
_DECISION_BOARD_CONTENT_CACHE: dict[str, str] = {}
_DECISION_BOARD_IN_FLIGHT: dict[str, asyncio.Task[str]] = {}
EXECUTIVE_SUMMARY_CACHE_MAX_ITEMS = 128
_EXECUTIVE_SUMMARY_CONTENT_CACHE: dict[str, str] = {}
_EXECUTIVE_SUMMARY_IN_FLIGHT: dict[str, asyncio.Task[str]] = {}
PRESENTER_ASK_CACHE_MAX_ITEMS = 128
_PRESENTER_ASK_CONTENT_CACHE: dict[str, str] = {}
_PRESENTER_ASK_IN_FLIGHT: dict[str, asyncio.Task[str]] = {}

ASK_STOPWORDS = {
    "about",
    "after",
    "again",
    "all",
    "also",
    "and",
    "any",
    "are",
    "based",
    "been",
    "before",
    "between",
    "but",
    "can",
    "could",
    "cycle",
    "did",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "into",
    "latest",
    "more",
    "need",
    "needs",
    "now",
    "our",
    "out",
    "partner",
    "partners",
    "please",
    "should",
    "show",
    "that",
    "the",
    "their",
    "them",
    "there",
    "this",
    "update",
    "updates",
    "was",
    "what",
    "when",
    "where",
    "which",
    "will",
    "with",
}
ASK_LIST_PHRASES = ("list all", "show all", "all updates", "full list", "complete list")
ASK_CHANGE_PHRASES = (
    "what changed",
    "what happened",
    "changed this cycle",
    "changes this cycle",
)
ASK_LOOKAHEAD_PHRASES = ("next month", "coming up", "upcoming", "next steps", "future")
ASK_RISK_TERMS = ("risk", "risks", "blocker", "blockers", "ask", "asks", "action", "actions")
ASK_METADATA_TERMS = (
    "status",
    "goal",
    "goals",
    "priority",
    "timeline",
    "resource",
    "resources",
)
ASK_LOOKAHEAD_EVIDENCE_TERMS = ("next", "upcoming", "planned", "due", "timeline", "scheduled")
ASK_RISK_EVIDENCE_TERMS = ("risk", "block", "ask", "action", "owner", "due", "decision")


@dataclass(frozen=True)
class PresenterAskEvidence:
    citation_id: str
    kind: str
    partner_id: str | None
    partner_name: str | None
    title: str
    text: str
    cycle: str | None
    score: int = 0

    def payload(self) -> dict[str, object]:
        return {
            "citation_id": self.citation_id,
            "kind": self.kind,
            "partner_id": self.partner_id,
            "partner_name": self.partner_name,
            "title": self.title,
            "text": self.text,
            "cycle": self.cycle,
        }

    def citation(self) -> PresenterAskCitation:
        return PresenterAskCitation(
            citation_id=self.citation_id,
            kind=self.kind,
            partner_name=self.partner_name,
            title=self.title,
            summary=self.text[:360],
            cycle=self.cycle,
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
                PartnerUpdate.update_id.asc(),
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
                str(update.update_id),
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
        metadata_context = await self._metadata_context(
            cycle=cycle,
            partner_ids=scoped_partner_ids,
            date_start=date_start,
            date_end=date_end,
        )

        intent = classify_presenter_ask_intent(cleaned_question)
        if intent == "casual":
            return PresenterAskResponse(
                answer=(
                    "Ask me about approved updates, partner metadata, risks, asks, "
                    "or what changed in the selected period."
                ),
                confidence="high",
                suggested_followups=[
                    "What changed this cycle?",
                    "Summarize the biggest risks and asks.",
                    "What is coming up next month?",
                ],
                grounded=True,
                model=None,
            )

        deterministic = deterministic_presenter_ask_response(
            question=cleaned_question,
            intent=intent,
            cycle=cycle,
            updates=updates,
            metadata_context=metadata_context,
        )
        if deterministic is not None:
            return deterministic

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
            intent=intent,
            updates=updates,
            metadata_context=metadata_context,
            rulebook_body=rulebook.body,
            rulebook_trace_version=rulebook.trace_version,
        )

        try:
            content = await cached_presenter_ask_model_content(
                runtime=runtime,
                model=model,
                payload=payload,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI assistant failed to answer: {exc}",
            ) from exc

        parsed = parse_presenter_ask_answer(content, citation_catalog=payload["_citation_catalog"])
        parsed.model = model
        return parsed

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
            content = await cached_executive_summary_model_content(
                runtime=runtime,
                model=model,
                payload=payload,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Executive summary agent failed: {exc}",
            ) from exc

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
        partner_updates = [
            update for update in updates if update.scope == "partner" and update.partner_id
        ]
        metadata_snapshots = await self._decision_board_metadata_inputs(
            cycle=cycle,
            partner_id=partner_id,
            partner_ids=partner_ids,
            date_start=date_start,
            date_end=date_end,
        )
        if not partner_updates and not metadata_snapshots:
            return PresenterDecisionBoardResponse(
                cycle=cycle,
                partner_id=partner_id if len(scoped_partner_ids) <= 1 else None,
                partner_ids=scoped_partner_ids,
                signals=[],
                source_note="No Decision Board items found for the selected partners and period.",
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
            updates=partner_updates,
            metadata_snapshots=metadata_snapshots,
            rulebook_body=rulebook.body,
            rulebook_trace_version=rulebook.trace_version,
        )

        try:
            content = await cached_decision_board_model_content(
                runtime=runtime,
                model=model,
                payload=payload,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Decision board agent failed: {exc}",
            ) from exc

        parsed = parse_decision_board_response(content)
        return PresenterDecisionBoardResponse(
            cycle=cycle,
            partner_id=partner_id if len(scoped_partner_ids) <= 1 else None,
            partner_ids=scoped_partner_ids,
            signals=parsed["signals"],
            source_note=parsed["source_note"],
            update_count=len(partner_updates),
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

    async def _decision_board_metadata_inputs(
        self,
        *,
        cycle: str,
        partner_id: uuid.UUID | None,
        partner_ids: list[uuid.UUID] | None = None,
        date_start: date | None = None,
        date_end: date | None = None,
    ) -> list[dict[str, object]]:
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
            .order_by(
                Partner.name.asc(),
                Partner.partner_id.asc(),
                PartnerMetadataSnapshot.cycle_month.asc(),
                PartnerMetadataSnapshot.metadata_id.asc(),
            )
        )
        if scoped_partner_ids:
            statement = statement.where(Partner.partner_id.in_(scoped_partner_ids))
        result = await self.db.execute(statement)
        snapshots: list[dict[str, object]] = []
        for partner, snapshot in result.all():
            snapshots.append(
                {
                    "partner_id": str(partner.partner_id),
                    "partner_name": partner.name,
                    "cycle": format_cycle_month(snapshot.cycle_month),
                    "status": snapshot.status,
                    "risks": [
                        {
                            "metadata_risk_id": str(risk.risk_id),
                            "description": risk.description,
                            "severity": risk.severity,
                            "due_date": risk.due_date,
                            "green_action": risk.green_action,
                            "ramification": risk.ramification,
                        }
                        for risk in sorted(
                            snapshot.risks,
                            key=lambda item: (item.sort_order, str(item.risk_id)),
                        )
                    ],
                }
            )
        return snapshots

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
    return f"{scope} {title} - {email_period_label(period_label)}"


def draft_email_body(
    *,
    period_label: str,
    partner_name: str | None,
    updates: list[PresenterUpdateResponse],
) -> str:
    greeting = "Hello,"
    scope = partner_name or "the Cloud AI Software Ecosystem"
    display_period = email_period_label(period_label)
    if not updates:
        return (
            f"{greeting}\n\n"
            f"There are no approved updates available for {scope} in {display_period} yet.\n\n"
            "Regards,"
        )
    grouped_updates = group_email_updates(updates, single_partner=partner_name is not None)
    lines = [
        greeting,
        "",
        f"Please find the approved {display_period} update for {scope}:",
        "",
    ]
    for category in grouped_updates:
        if category.label:
            lines.append(f"{category.label}:")
        for partner_group in category.partners:
            lines.append(f"{partner_group.partner_name}:")
            for item in partner_group.items:
                lines.append(f"\t- {item}")
            lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
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
    cleaned_lines = [clean_email_line(line) for line in lines]
    return "\n".join(line for line in cleaned_lines if line).strip()


def normalize_link_html_for_email(value: str) -> str:
    pattern = re.compile(
        r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        re.IGNORECASE | re.DOTALL,
    )

    def replace(match: re.Match[str]) -> str:
        label = unescape(re.sub(r"<[^>]+>", "", match.group(2))).strip()
        return label

    return pattern.sub(replace, value)


@dataclass(frozen=True)
class EmailPartnerUpdateGroup:
    partner_name: str
    items: list[str]


@dataclass(frozen=True)
class EmailCategoryUpdateGroup:
    label: str | None
    partners: list[EmailPartnerUpdateGroup]


EMAIL_CATEGORY_ORDER = ["HyperScalers", "OSVs", "ISVs", "Customers", "Other Partners"]

EMAIL_PARTNER_CATEGORY = {
    "amazon": "HyperScalers",
    "amazon web services": "HyperScalers",
    "aws": "HyperScalers",
    "gcp": "HyperScalers",
    "google": "HyperScalers",
    "google cloud": "HyperScalers",
    "microsoft": "HyperScalers",
    "msft": "HyperScalers",
    "canonical": "OSVs",
    "redhat": "OSVs",
    "red hat": "OSVs",
    "rhel": "OSVs",
    "rhat": "OSVs",
    "suse": "OSVs",
    "sap hana cloud": "ISVs",
    "cohere": "ISVs",
    "databricks": "ISVs",
    "elastic": "ISVs",
    "elasticco": "ISVs",
    "mongodb": "ISVs",
    "mistral": "ISVs",
    "nutanix": "ISVs",
    "pinecone": "ISVs",
    "rafay": "ISVs",
    "rafay systems": "ISVs",
    "redis": "ISVs",
    "tinkerblox": "ISVs",
    "tinklrbox": "ISVs",
    "vmware": "ISVs",
    "jpmc": "Customers",
    "jp morgan": "Customers",
    "jp morgan chase": "Customers",
    "optum": "Customers",
    "salesforce": "Customers",
    "teradata": "Customers",
    "uber": "Customers",
    "uhg": "Customers",
    "united health group": "Customers",
}


def email_period_label(period_label: str) -> str:
    if re.fullmatch(r"\d{4}-\d{2}", period_label):
        try:
            return parse_cycle_month(period_label).strftime("%B %Y")
        except HTTPException:
            return period_label
    return period_label


def group_email_updates(
    updates: list[PresenterUpdateResponse],
    *,
    single_partner: bool,
) -> list[EmailCategoryUpdateGroup]:
    partner_groups: list[EmailPartnerUpdateGroup] = []
    partner_index: dict[str, EmailPartnerUpdateGroup] = {}
    for update in updates:
        item = email_update_line(update)
        if not item:
            continue
        partner_name = update.partner_name
        existing = partner_index.get(partner_name)
        if existing:
            existing.items.append(item)
        else:
            group = EmailPartnerUpdateGroup(partner_name=partner_name, items=[item])
            partner_index[partner_name] = group
            partner_groups.append(group)
    if single_partner:
        return [EmailCategoryUpdateGroup(label=None, partners=partner_groups)]

    category_index: dict[str, list[EmailPartnerUpdateGroup]] = {
        label: [] for label in EMAIL_CATEGORY_ORDER
    }
    for group in partner_groups:
        category_index[email_category_for_partner(group.partner_name)].append(group)
    return [
        EmailCategoryUpdateGroup(label=label, partners=category_index[label])
        for label in EMAIL_CATEGORY_ORDER
        if category_index[label]
    ]


def email_category_for_partner(partner_name: str) -> str:
    normalized_name = (
        partner_name.strip().lower().replace(".", "").replace("&", "and")
    )
    normalized_name = re.sub(r"\s+", " ", normalized_name)
    return EMAIL_PARTNER_CATEGORY.get(normalized_name, "Other Partners")


def email_update_line(update: PresenterUpdateResponse) -> str:
    title = single_line_email_text(html_to_email_text(update.title))
    summary = single_line_email_text(html_to_email_text(update.summary))
    if not summary:
        return title
    if not title:
        return summary
    lowered_title = title.lower()
    lowered_summary = summary.lower()
    if lowered_title in lowered_summary:
        return summary
    if lowered_summary in lowered_title:
        return title
    return f"{title}: {summary}"


def single_line_email_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def clean_email_line(line: str) -> str:
    cleaned = re.sub(r"\([^)]*https?://[^)]*\)", "", line, flags=re.IGNORECASE)
    cleaned = re.sub(r"https?://\S+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(source|sources)\s*:\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(source|sources)\s*:\s*.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" -\t")


def presenter_ask_system_prompt() -> str:
    return (
        "You are the presenter Ask AI assistant for Cloud AI Software Ecosystem Updates.\n"
        "Use only the supplied JSON evidence and rulebook. Do not use model memory, "
        "outside knowledge, assumptions, or raw context not supplied in the packet.\n"
        "Answer the user's question directly. Do not dump every evidence item.\n"
        "Keep the main answer to one or two presenter-ready sentences unless the user "
        "explicitly asks for a list.\n"
        "If evidence is insufficient, say exactly what is missing in the selected scope.\n"
        "Return JSON only with this shape: {\"answer\":\"...\",\"confidence\":\"high|medium|low\","
        "\"sections\":[{\"title\":\"...\",\"body\":\"...\",\"bullets\":[\"...\"]}],"
        "\"bullets\":[\"...\"],\"tables\":[{\"title\":\"...\",\"columns\":[\"...\"],"
        "\"rows\":[[\"...\"]]}],\"citations\":[{\"citation_id\":\"...\"}],"
        "\"suggested_followups\":[\"...\"]}."
    )


def build_presenter_ask_payload(
    *,
    question: str,
    cycle: str,
    date_start: date | None,
    date_end: date | None,
    scoped_partner_ids: list[uuid.UUID],
    intent: str,
    updates: list[PresenterUpdateResponse],
    metadata_context: list[dict[str, object]],
    rulebook_body: str,
    rulebook_trace_version: str,
) -> dict[str, object]:
    selected_evidence = select_presenter_ask_evidence(
        question=question,
        intent=intent,
        updates=updates,
        metadata_context=metadata_context,
    )
    citation_catalog = {item.citation_id: item.citation() for item in selected_evidence}
    return {
        "task": "presenter_ask_ai",
        "question": question,
        "intent": intent,
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
        "evidence": [item.payload() for item in selected_evidence],
        "output_contract": {
            "answer": "Direct presenter answer. Do not repeat all evidence.",
            "sections": "Use only for grouping multiple answer parts.",
            "bullets": "Use only when the user asks for multiple facts or risks.",
            "citations": "Use citation_id values from supplied evidence only.",
        },
        "_citation_catalog": citation_catalog,
    }


def parse_presenter_ask_answer(
    content: str,
    *,
    citation_catalog: dict[str, PresenterAskCitation],
) -> PresenterAskResponse:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI assistant returned an invalid response.",
        ) from exc
    if not isinstance(parsed, dict):
        parsed = {}
    answer = concise_ask_text(parsed.get("answer"))
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI assistant returned an empty answer.",
        )
    confidence = str(parsed.get("confidence") or "medium").lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    citations: list[PresenterAskCitation] = []
    seen_citations: set[str] = set()
    for raw in parsed.get("citations") or []:
        citation_id = str(raw.get("citation_id") or "") if isinstance(raw, dict) else ""
        citation = citation_catalog.get(citation_id)
        if citation and citation_id not in seen_citations:
            citations.append(citation)
            seen_citations.add(citation_id)
        if len(citations) >= 4:
            break
    return PresenterAskResponse(
        answer=answer,
        confidence=confidence,
        sections=normalize_ask_sections(parsed.get("sections")),
        bullets=normalize_string_list(parsed.get("bullets"), limit=16),
        tables=normalize_ask_tables(parsed.get("tables")),
        citations=citations,
        suggested_followups=normalize_string_list(parsed.get("suggested_followups"), limit=4),
        grounded=True,
        model=None,
    )


def normalize_string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value[:limit]:
        text = " ".join(str(item or "").split())
        if text:
            items.append(text)
    return items


def normalize_ask_sections(value: Any) -> list[PresenterAskSection]:
    if not isinstance(value, list):
        return []
    sections: list[PresenterAskSection] = []
    for item in value[:6]:
        if not isinstance(item, dict):
            continue
        title = " ".join(str(item.get("title") or "").split())
        body = concise_ask_text(item.get("body"), max_chars=420) or None
        bullets = normalize_string_list(item.get("bullets"), limit=10)
        if title or body or bullets:
            sections.append(
                PresenterAskSection(
                    title=title or "Details",
                    body=body,
                    bullets=bullets,
                )
            )
    return sections


def normalize_ask_tables(value: Any) -> list[PresenterAskTable]:
    if not isinstance(value, list):
        return []
    tables: list[PresenterAskTable] = []
    for item in value[:3]:
        if not isinstance(item, dict):
            continue
        columns = normalize_string_list(item.get("columns"), limit=6)
        raw_rows = item.get("rows") or []
        if not columns or not isinstance(raw_rows, list):
            continue
        rows: list[list[str]] = []
        for raw_row in raw_rows[:12]:
            if not isinstance(raw_row, list):
                continue
            row = [" ".join(str(cell or "").split()) for cell in raw_row[: len(columns)]]
            rows.append(row + [""] * max(0, len(columns) - len(row)))
        if rows:
            tables.append(
                PresenterAskTable(
                    title=" ".join(str(item.get("title") or "").split()) or None,
                    columns=columns,
                    rows=rows,
                )
            )
    return tables


def concise_ask_text(value: Any, *, max_chars: int = 520) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    shortened = " ".join(sentence for sentence in sentences[:2] if sentence).strip()
    if shortened and len(shortened) <= max_chars:
        return shortened
    return text[: max_chars - 3].rstrip(" ,;:") + "..."


def ask_tokens(text: str | None) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9+'-]*", (text or "").lower())
    return {
        word.strip("'")
        for word in words
        if len(word.strip("'")) >= 3 and word.strip("'") not in ASK_STOPWORDS
    }


def classify_presenter_ask_intent(question: str) -> str:
    lowered = question.lower()
    if lowered in {"hi", "hii", "hello", "hey", "hey there", "hello there"}:
        return "casual"
    if any(phrase in lowered for phrase in ("how many", "number of", "count", "total")):
        return "count"
    if any(phrase in lowered for phrase in ASK_LIST_PHRASES):
        return "list_updates"
    if any(phrase in lowered for phrase in ASK_CHANGE_PHRASES):
        return "cycle_change"
    if any(phrase in lowered for phrase in ASK_LOOKAHEAD_PHRASES):
        return "lookahead"
    if any(term in lowered for term in ASK_RISK_TERMS):
        return "risk_ask"
    if any(term in lowered for term in ASK_METADATA_TERMS):
        return "metadata"
    return "focused_search"


def deterministic_presenter_ask_response(
    *,
    question: str,
    intent: str,
    cycle: str,
    updates: list[PresenterUpdateResponse],
    metadata_context: list[dict[str, object]],
) -> PresenterAskResponse | None:
    if not updates and not metadata_context:
        return PresenterAskResponse(
            answer="I do not see that in the selected approved updates or partner metadata.",
            confidence="high",
            grounded=True,
            model=None,
        )
    if intent == "count":
        partner_count = len({str(update.partner_id) for update in updates if update.partner_id})
        topic_count = len(
            [update for update in updates if update.scope == "topic" or not update.partner_id]
        )
        parts = [f"{cycle} has {len(updates)} approved update{'s' if len(updates) != 1 else ''}"]
        if partner_count:
            parts.append(f"across {partner_count} partner{'s' if partner_count != 1 else ''}")
        if topic_count:
            parts.append(f"plus {topic_count} topic-level update{'s' if topic_count != 1 else ''}")
        return PresenterAskResponse(
            answer=" ".join(parts) + ".",
            confidence="high",
            grounded=True,
            model=None,
        )
    if intent == "list_updates":
        bullets = [
            f"{update.partner_name}: {strip_html(update.summary) or update.title}"
            for update in updates[:20]
        ]
        return PresenterAskResponse(
            answer=(
                f"I found {len(updates)} approved update{'s' if len(updates) != 1 else ''} "
                f"for the selected scope."
            ),
            confidence="high",
            bullets=bullets,
            suggested_followups=[
                "Summarize these into executive themes.",
                "Which updates imply risks or asks?",
            ],
            grounded=True,
            model=None,
        )
    return None


def select_presenter_ask_evidence(
    *,
    question: str,
    intent: str,
    updates: list[PresenterUpdateResponse],
    metadata_context: list[dict[str, object]],
) -> list[PresenterAskEvidence]:
    evidence = [
        *presenter_update_evidence(updates),
        *presenter_metadata_evidence(metadata_context),
    ]
    if not evidence:
        return []
    ranked: list[PresenterAskEvidence] = []
    for item in evidence:
        ranked.append(
            PresenterAskEvidence(
                citation_id=item.citation_id,
                kind=item.kind,
                partner_id=item.partner_id,
                partner_name=item.partner_name,
                title=item.title,
                text=item.text,
                cycle=item.cycle,
                score=score_presenter_ask_evidence(question=question, intent=intent, item=item),
            )
        )
    ranked.sort(
        key=lambda item: (
            item.score,
            item.kind == "approved_update",
            item.partner_name or "",
            item.title,
            item.citation_id,
        ),
        reverse=True,
    )
    if any(item.score > 0 for item in ranked):
        ranked = [item for item in ranked if item.score > 0]
    return dedupe_presenter_ask_evidence(ranked)[:18]


def presenter_update_evidence(updates: list[PresenterUpdateResponse]) -> list[PresenterAskEvidence]:
    items: list[PresenterAskEvidence] = []
    for update in updates:
        summary = strip_html(update.summary)
        text = summary or update.title
        if not text:
            continue
        items.append(
            PresenterAskEvidence(
                citation_id=f"approved_update:{update.update_id}",
                kind="approved_update",
                partner_id=str(update.partner_id) if update.partner_id else None,
                partner_name=update.partner_name,
                title=update.title,
                text=text[:1200],
                cycle=update.cycle,
            )
        )
    return items


def presenter_metadata_evidence(
    metadata_context: list[dict[str, object]],
) -> list[PresenterAskEvidence]:
    items: list[PresenterAskEvidence] = []
    for snapshot in metadata_context:
        partner_id = str(snapshot.get("partner_id") or "") or None
        partner_name = str(snapshot.get("partner_name") or "") or None
        cycle = str(snapshot.get("cycle") or "") or None
        profile_parts = [
            f"Status: {snapshot.get('status')}" if snapshot.get("status") else "",
            (
                f"Why this partner: {snapshot.get('why_this_partner')}"
                if snapshot.get("why_this_partner")
                else ""
            ),
            (
                f"Business priority: {snapshot.get('business_priority')}"
                if snapshot.get("business_priority")
                else ""
            ),
            (
                f"Highlights/status: {snapshot.get('highlights_status')}"
                if snapshot.get("highlights_status")
                else ""
            ),
            f"Goals: {snapshot.get('goals')}" if snapshot.get("goals") else "",
            (
                f"Execution timeline: {snapshot.get('execution_timeline')}"
                if snapshot.get("execution_timeline")
                else ""
            ),
        ]
        profile_text = " ".join(str(part) for part in profile_parts if part).strip()
        if profile_text:
            items.append(
                PresenterAskEvidence(
                    citation_id=f"metadata_profile:{partner_id or partner_name}:{cycle}",
                    kind="metadata_profile",
                    partner_id=partner_id,
                    partner_name=partner_name,
                    title="Partner metadata",
                    text=profile_text[:1400],
                    cycle=cycle,
                )
            )
        for index, risk in enumerate(snapshot.get("risks") or []):
            if not isinstance(risk, dict):
                continue
            risk_parts = [
                f"Risk: {risk.get('description')}" if risk.get("description") else "",
                (
                    f"Go-to-green action: {risk.get('green_action')}"
                    if risk.get("green_action")
                    else ""
                ),
                f"Severity: {risk.get('severity')}" if risk.get("severity") else "",
                f"Owner: {risk.get('assigned_to')}" if risk.get("assigned_to") else "",
                f"Due date: {risk.get('due_date')}" if risk.get("due_date") else "",
                f"Ramification: {risk.get('ramification')}" if risk.get("ramification") else "",
            ]
            risk_text = " ".join(str(part) for part in risk_parts if part).strip()
            if risk_text:
                items.append(
                    PresenterAskEvidence(
                        citation_id=f"metadata_risk:{risk.get('metadata_risk_id') or index}",
                        kind="metadata_risk",
                        partner_id=partner_id,
                        partner_name=partner_name,
                        title="Partner metadata risk",
                        text=risk_text[:1200],
                        cycle=cycle,
                    )
                )
        for index, resource in enumerate(snapshot.get("resources") or []):
            if not isinstance(resource, dict):
                continue
            resource_text = " ".join(
                str(part)
                for part in [
                    resource.get("title"),
                    resource.get("description"),
                    resource.get("source_kind"),
                ]
                if part
            )
            if resource_text:
                items.append(
                    PresenterAskEvidence(
                        citation_id=f"metadata_resource:{partner_id or partner_name}:{index}",
                        kind="metadata_resource",
                        partner_id=partner_id,
                        partner_name=partner_name,
                        title=str(resource.get("title") or "Partner resource"),
                        text=resource_text[:800],
                        cycle=cycle,
                    )
                )
    return items


def score_presenter_ask_evidence(
    *,
    question: str,
    intent: str,
    item: PresenterAskEvidence,
) -> int:
    question_tokens = ask_tokens(question)
    haystack = f"{item.partner_name or ''} {item.title} {item.text}"
    item_tokens = ask_tokens(haystack)
    score = len(question_tokens & item_tokens) * 3
    lowered = item.text.lower()
    kind = item.kind
    if intent == "cycle_change" and kind == "approved_update":
        score += 2
    if intent == "lookahead" and any(term in lowered for term in ASK_LOOKAHEAD_EVIDENCE_TERMS):
        score += 4
    if intent == "risk_ask":
        if kind == "metadata_risk":
            score += 6
        if any(term in lowered for term in ASK_RISK_EVIDENCE_TERMS):
            score += 4
    if intent == "metadata" and kind.startswith("metadata_"):
        score += 5
    if intent == "focused_search" and kind == "approved_update":
        score += 1
    return score


def dedupe_presenter_ask_evidence(items: list[PresenterAskEvidence]) -> list[PresenterAskEvidence]:
    seen: set[tuple[str | None, str, str]] = set()
    deduped: list[PresenterAskEvidence] = []
    for item in items:
        key = (item.partner_id or item.partner_name, item.kind, " ".join(item.text.lower().split()))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def stable_model_cache_key(*, model: str, payload: dict[str, object]) -> str:
    serialized = json.dumps(
        {"model": model, "payload": payload},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def cached_presenter_ask_model_content(
    *,
    runtime: AIClientRuntime,
    model: str,
    payload: dict[str, object],
) -> str:
    model_payload = {key: value for key, value in payload.items() if not key.startswith("_")}
    cache_key = stable_model_cache_key(model=model, payload=model_payload)
    cached = _PRESENTER_ASK_CONTENT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    task = _PRESENTER_ASK_IN_FLIGHT.get(cache_key)
    if task is None:
        task = asyncio.create_task(
            create_presenter_ask_model_content(
                runtime=runtime,
                model=model,
                payload=model_payload,
            )
        )
        _PRESENTER_ASK_IN_FLIGHT[cache_key] = task
    try:
        content = await task
    finally:
        if task.done() and _PRESENTER_ASK_IN_FLIGHT.get(cache_key) is task:
            _PRESENTER_ASK_IN_FLIGHT.pop(cache_key, None)
    _PRESENTER_ASK_CONTENT_CACHE[cache_key] = content
    while len(_PRESENTER_ASK_CONTENT_CACHE) > PRESENTER_ASK_CACHE_MAX_ITEMS:
        _PRESENTER_ASK_CONTENT_CACHE.pop(next(iter(_PRESENTER_ASK_CONTENT_CACHE)))
    return content


async def create_presenter_ask_model_content(
    *,
    runtime: AIClientRuntime,
    model: str,
    payload: dict[str, object],
) -> str:
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
        max_tokens=1100,
    )
    return response.choices[0].message.content or "{}"


def executive_summary_system_prompt() -> str:
    return (
        "You are the presenter executive summary agent for Cloud AI Software Ecosystem Updates.\n"
        "Use only approved update titles and approved update summaries from the supplied JSON. "
        "Do not use model memory, outside knowledge, metadata, partner status, decision-board "
        "data, source links, approval timestamps, reporting month, or assumptions as summary "
        "facts.\n"
        "Return JSON only with this shape: {\"bullets\": [\"...\"], \"source_note\": \"...\"}.\n"
        "If there are no usable approved update facts, return an empty bullets array. "
        "Compress approved updates into monthly status-email style bullets without synthesis. "
        "Preserve dates and quantitative facts that appear in the title or summary. Do not "
        "include source labels, markdown links, or raw URLs."
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
            "partner_ids": sorted(str(partner_id) for partner_id in scoped_partner_ids),
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
            }
            for update in updates[:80]
        ],
        "output_contract": {
            "bullets": (
                "Concise monthly-status bullets grounded in approved updates. Preserve dates "
                "and quantitative details. Do not include source labels, markdown links, or URLs."
            ),
            "source_note": "Use only when no usable approved update facts are available.",
        },
    }


async def cached_executive_summary_model_content(
    *,
    runtime: AIClientRuntime,
    model: str,
    payload: dict[str, object],
) -> str:
    cache_key = executive_summary_cache_key(model=model, payload=payload)
    cached = _EXECUTIVE_SUMMARY_CONTENT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    task = _EXECUTIVE_SUMMARY_IN_FLIGHT.get(cache_key)
    if task is None:
        task = asyncio.create_task(
            fetch_executive_summary_model_content(
                runtime=runtime,
                model=model,
                payload=payload,
            )
        )
        _EXECUTIVE_SUMMARY_IN_FLIGHT[cache_key] = task

    try:
        content = await task
    finally:
        if task.done() and _EXECUTIVE_SUMMARY_IN_FLIGHT.get(cache_key) is task:
            _EXECUTIVE_SUMMARY_IN_FLIGHT.pop(cache_key, None)

    parse_executive_summary_response(content)
    _EXECUTIVE_SUMMARY_CONTENT_CACHE[cache_key] = content
    while len(_EXECUTIVE_SUMMARY_CONTENT_CACHE) > EXECUTIVE_SUMMARY_CACHE_MAX_ITEMS:
        _EXECUTIVE_SUMMARY_CONTENT_CACHE.pop(next(iter(_EXECUTIVE_SUMMARY_CONTENT_CACHE)))
    return content


async def fetch_executive_summary_model_content(
    *,
    runtime: AIClientRuntime,
    model: str,
    payload: dict[str, object],
) -> str:
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
        max_tokens=1600,
    )
    return response.choices[0].message.content or "{}"


def executive_summary_cache_key(*, model: str, payload: dict[str, object]) -> str:
    serialized = json.dumps(
        {"model": model, "payload": payload},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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
    bullets = [" ".join(str(item).split()) for item in raw_bullets[:16] if str(item).strip()]
    source_note = parsed.get("source_note")
    cleaned_note = " ".join(str(source_note).split()) if source_note else None
    return {"bullets": bullets, "source_note": cleaned_note}


def decision_board_system_prompt() -> str:
    return (
        "You are the presenter Decision Board agent for Cloud AI Software Ecosystem Updates.\n"
        "Use only the supplied approved partner updates, same-period partner metadata risks, "
        "and rulebook. Do not use model memory, outside knowledge, pending updates, topic "
        "updates, raw source payloads, or assumptions.\n"
        "Return JSON only with this shape: "
        "{\"signals\": [{\"partner_id\": \"...\", \"partner_name\": \"...\", "
        "\"priority\": \"P1|P2|P3\", \"title\": \"...\", \"update_line\": \"...\", "
        "\"action\": \"...\", \"source_kind\": \"approved_update|metadata_risk\", "
        "\"update_id\": \"...\", \"metadata_risk_id\": \"...\"}], "
        "\"source_note\": \"...\"}.\n"
        "If no supplied input contains a decision-board item, return an empty signals array. "
        "Do not include rationale, visible source labels, owner fields, or separate due-date "
        "or severity fields."
    )


def build_decision_board_payload(
    *,
    cycle: str,
    date_start: date | None,
    date_end: date | None,
    scoped_partner_ids: list[uuid.UUID],
    updates: list[PresenterUpdateResponse],
    metadata_snapshots: list[dict[str, object]],
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
                "partner_id": str(update.partner_id),
                "partner_name": update.partner_name,
                "cycle": update.cycle,
                "title": update.title,
                "summary": strip_html(update.summary),
                "approved_at": update.approved_at.isoformat() if update.approved_at else None,
            }
            for update in updates
        ],
        "partner_metadata": metadata_snapshots,
        "output_contract": {
            "signals": (
                "All decision-board cards that are semantically necessary for the supplied scope. "
                "Each card must include partner_id, partner_name, "
                "priority, title, update_line, and source_kind. action is optional and "
                "must be present only when explicitly grounded."
            ),
            "source_note": "Use a short scope/data note when no cards are found.",
        },
    }


async def cached_decision_board_model_content(
    *,
    runtime: AIClientRuntime,
    model: str,
    payload: dict[str, object],
) -> str:
    cache_key = decision_board_cache_key(model=model, payload=payload)
    cached = _DECISION_BOARD_CONTENT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    task = _DECISION_BOARD_IN_FLIGHT.get(cache_key)
    if task is None:
        task = asyncio.create_task(
            fetch_decision_board_model_content(
                runtime=runtime,
                model=model,
                payload=payload,
            )
        )
        _DECISION_BOARD_IN_FLIGHT[cache_key] = task

    try:
        content = await task
    finally:
        if task.done() and _DECISION_BOARD_IN_FLIGHT.get(cache_key) is task:
            _DECISION_BOARD_IN_FLIGHT.pop(cache_key, None)

    parse_decision_board_response(content)
    _DECISION_BOARD_CONTENT_CACHE[cache_key] = content
    while len(_DECISION_BOARD_CONTENT_CACHE) > DECISION_BOARD_CACHE_MAX_ITEMS:
        _DECISION_BOARD_CONTENT_CACHE.pop(next(iter(_DECISION_BOARD_CONTENT_CACHE)))
    return content


async def fetch_decision_board_model_content(
    *,
    runtime: AIClientRuntime,
    model: str,
    payload: dict[str, object],
) -> str:
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
        max_tokens=6000,
    )
    return response.choices[0].message.content or "{}"


def decision_board_cache_key(*, model: str, payload: dict[str, object]) -> str:
    serialized = json.dumps(
        {"model": model, "payload": payload},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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
    for raw_item in raw_signals:
        if not isinstance(raw_item, dict):
            continue
        title = clean_agent_text(raw_item.get("title"))
        action = clean_agent_text(raw_item.get("action"))
        update_line = clean_agent_text(raw_item.get("update_line"))
        if not title or not update_line:
            continue
        signals.append(
            PresenterDecisionBoardSignal(
                partner_id=parse_optional_uuid(raw_item.get("partner_id")),
                partner_name=clean_agent_text(raw_item.get("partner_name")) or None,
                priority=normalize_priority(raw_item.get("priority")),
                title=title,
                update_line=update_line,
                action=action or None,
                source_kind=normalize_decision_board_source_kind(raw_item.get("source_kind")),
                update_id=parse_optional_uuid(raw_item.get("update_id")),
                metadata_risk_id=parse_optional_uuid(raw_item.get("metadata_risk_id")),
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


def normalize_decision_board_source_kind(value: object) -> str | None:
    source_kind = clean_agent_text(value).lower()
    if source_kind in {"approved_update", "metadata_risk"}:
        return source_kind
    return None


def normalize_priority(value: object) -> str | None:
    priority = clean_agent_text(value).upper()
    if priority in {"P1", "P2", "P3"}:
        return priority
    return None


def strip_html(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(without_tags.split())
