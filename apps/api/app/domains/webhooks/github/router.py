import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.domains.webhooks.github.service import GitHubWebhookService

router = APIRouter(prefix="/api/webhooks/github", tags=["webhooks-github"])


def get_github_webhook_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GitHubWebhookService:
    return GitHubWebhookService(db, settings)


@router.post("/events")
async def receive_github_event(
    request: Request,
    service: Annotated[GitHubWebhookService, Depends(get_github_webhook_service)],
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
        signature=request.headers.get("X-Hub-Signature-256")
        or request.headers.get("X-Hub-Signature"),
        event_name=request.headers.get("X-GitHub-Event"),
        delivery_id=request.headers.get("X-GitHub-Delivery"),
        payload=payload,
    )
