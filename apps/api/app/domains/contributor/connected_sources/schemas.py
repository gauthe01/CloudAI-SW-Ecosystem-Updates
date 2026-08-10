import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.db.models.connected_source import ConnectedSourceStatus, ConnectedSourceType


class ConnectedSourceRequest(BaseModel):
    source_type: ConnectedSourceType
    display_name: str | None = Field(default=None, max_length=300)
    source_url: str | None = Field(default=None, max_length=4000)
    channel_name: str | None = Field(default=None, max_length=240)
    channel_id: str | None = Field(default=None, max_length=120)
    bot_invited_confirmed: bool = False

    @model_validator(mode="after")
    def source_type_requires_matching_fields(self) -> "ConnectedSourceRequest":
        if self.source_type == ConnectedSourceType.slack_channel:
            if not clean_optional(self.channel_name) or not clean_optional(self.channel_id):
                raise ValueError("Slack sources require channel name and channel ID.")
            if not self.bot_invited_confirmed:
                raise ValueError("Confirm the Slack app/bot has been invited to the channel.")
        else:
            if not clean_optional(self.source_url):
                raise ValueError("This source type requires a URL.")
        return self


class ConnectedSourceDetailResponse(BaseModel):
    channel_name: str | None = None
    channel_id: str | None = None
    bot_invited_confirmed: bool | None = None
    issue_key: str | None = None
    file_name: str | None = None
    page_title: str | None = None
    github_target_kind: str | None = None
    github_repository: str | None = None
    github_number: int | None = None


class ConnectedSourceResponse(BaseModel):
    connected_source_id: uuid.UUID
    partner_id: uuid.UUID
    source_type: ConnectedSourceType
    status: ConnectedSourceStatus
    contributor_status: str
    display_name: str
    source_url: str | None
    external_identifier: str | None
    details: ConnectedSourceDetailResponse
    created_by: uuid.UUID
    approved_at: datetime | None
    rejected_at: datetime | None
    disabled_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConnectedSourceListResponse(BaseModel):
    connected_sources: list[ConnectedSourceResponse]


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
