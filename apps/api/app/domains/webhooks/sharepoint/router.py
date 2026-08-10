import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.domains.webhooks.sharepoint.service import SharePointWebhookService

router = APIRouter(prefix="/api/webhooks/sharepoint", tags=["webhooks-sharepoint"])


def get_sharepoint_webhook_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SharePointWebhookService:
    return SharePointWebhookService(db, settings)


@router.post("/events", response_model=None)
async def receive_sharepoint_event(
    request: Request,
    service: Annotated[SharePointWebhookService, Depends(get_sharepoint_webhook_service)],
):
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        return PlainTextResponse(validation_token)

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode())
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from exc

    return await service.handle_event_payload(payload=payload)
