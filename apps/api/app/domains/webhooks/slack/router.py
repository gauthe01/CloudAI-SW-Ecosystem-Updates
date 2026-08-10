import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.domains.webhooks.slack.service import SlackWebhookService

router = APIRouter(prefix="/api/webhooks/slack", tags=["webhooks-slack"])


def get_slack_webhook_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SlackWebhookService:
    return SlackWebhookService(db, settings)


@router.post("/events")
async def receive_slack_event(
    request: Request,
    service: Annotated[SlackWebhookService, Depends(get_slack_webhook_service)],
) -> dict:
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode())
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from exc

    return await service.handle_event_payload(
        raw_body=raw_body,
        timestamp=request.headers.get("X-Slack-Request-Timestamp"),
        signature=request.headers.get("X-Slack-Signature"),
        payload=payload,
    )
