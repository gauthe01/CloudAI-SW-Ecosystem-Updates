from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.topic_update import EventTopic, EventTopicStatus, TopicUpdate, TopicUpdateStatus
from app.domains.admin.topic_updates.schemas import (
    AdminEventTopicListResponse,
    AdminEventTopicResponse,
    AdminTopicUpdateListResponse,
    AdminTopicUpdateResponse,
)
from app.domains.contributor.metadata.service import format_cycle_month, parse_cycle_month


class AdminTopicUpdateService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_event_topics(self) -> AdminEventTopicListResponse:
        result = await self.db.execute(
            select(EventTopic)
            .where(EventTopic.status == EventTopicStatus.active.value)
            .order_by(EventTopic.name.asc())
        )
        return AdminEventTopicListResponse(
            topics=[self._topic_to_response(topic) for topic in result.scalars().all()]
        )

    async def list_topic_updates(
        self,
        *,
        cycle: str | None = None,
        search: str | None = None,
    ) -> AdminTopicUpdateListResponse:
        statement = select(TopicUpdate).where(
            TopicUpdate.status == TopicUpdateStatus.approved.value
        )
        if cycle:
            cycle_month = parse_cycle_month(cycle)
            statement = statement.where(TopicUpdate.cycle_month == cycle_month)
        cleaned_search = search.strip() if search else ""
        if cleaned_search:
            query = f"%{cleaned_search.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(TopicUpdate.topic_label).like(query),
                    func.lower(TopicUpdate.title).like(query),
                    func.lower(TopicUpdate.summary).like(query),
                    func.lower(TopicUpdate.source_label).like(query),
                )
            )
        statement = statement.order_by(
            TopicUpdate.cycle_month.desc(),
            TopicUpdate.topic_label.asc(),
            TopicUpdate.approved_at.desc().nullslast(),
            TopicUpdate.updated_at.desc(),
        )
        result = await self.db.execute(statement)
        topics = list(result.scalars().all())
        return AdminTopicUpdateListResponse(
            topics=[self._to_response(topic) for topic in topics],
            total_count=len(topics),
            topic_count=len({(topic.topic_label, topic.cycle_month) for topic in topics}),
        )

    def _to_response(self, topic: TopicUpdate) -> AdminTopicUpdateResponse:
        return AdminTopicUpdateResponse(
            topic_update_id=topic.topic_update_id,
            topic_id=topic.topic_id,
            topic_label=topic.topic_label,
            cycle=format_cycle_month(topic.cycle_month),
            title=topic.title,
            summary=topic.summary,
            source_type=topic.source_type,
            source_label=topic.source_label,
            source_url=topic.source_url,
            status=topic.status,
            approved_at=topic.approved_at,
            approved_by=topic.approved_by,
            created_at=topic.created_at,
            updated_at=topic.updated_at,
        )

    def _topic_to_response(self, topic: EventTopic) -> AdminEventTopicResponse:
        return AdminEventTopicResponse(
            topic_id=topic.topic_id,
            name=topic.name,
            normalized_name=topic.normalized_name,
            status=topic.status,
            created_at=topic.created_at,
            updated_at=topic.updated_at,
        )
