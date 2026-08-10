import uuid
from datetime import datetime

from pydantic import BaseModel


class ContributorPartnerResponse(BaseModel):
    partner_id: uuid.UUID
    name: str
    description: str | None
    updates_count: int
    connected_sources_count: int
    last_activity_at: datetime | None


class ContributorPartnerListResponse(BaseModel):
    partners: list[ContributorPartnerResponse]


class ContributorDashboardTabCounts(BaseModel):
    pending_updates: int
    approved_updates: int
    connected_sources: int


class ContributorDashboardContextResponse(BaseModel):
    partner: ContributorPartnerResponse
    active_cycle: str
    active_cycle_label: str
    default_tab: str
    tab_counts: ContributorDashboardTabCounts
