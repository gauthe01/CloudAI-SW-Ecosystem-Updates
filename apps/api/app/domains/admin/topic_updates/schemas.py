import uuid
from datetime import datetime

from pydantic import BaseModel


class AdminTopicUpdateResponse(BaseModel):
    topic_update_id: uuid.UUID
    topic_label: str
    cycle: str
    title: str
    summary: str
    source_type: str
    source_label: str | None
    source_url: str | None
    status: str
    approved_at: datetime | None
    approved_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AdminTopicUpdateListResponse(BaseModel):
    topics: list[AdminTopicUpdateResponse]
    total_count: int
    topic_count: int
