from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import RoleType
from app.db.session import get_db_session
from app.domains.admin.topic_updates.schemas import AdminTopicUpdateListResponse
from app.domains.admin.topic_updates.service import AdminTopicUpdateService
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse

router = APIRouter(prefix="/api/admin/topic-updates", tags=["admin-topic-updates"])


def get_admin_topic_update_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminTopicUpdateService:
    return AdminTopicUpdateService(db)


@router.get("", response_model=AdminTopicUpdateListResponse)
async def list_topic_updates(
    service: Annotated[AdminTopicUpdateService, Depends(get_admin_topic_update_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
    cycle: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
) -> AdminTopicUpdateListResponse:
    return await service.list_topic_updates(cycle=cycle, search=search)
