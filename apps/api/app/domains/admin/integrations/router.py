from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.identity import RoleType
from app.db.models.integration import IntegrationType
from app.db.session import get_db_session
from app.domains.admin.integrations.schemas import (
    IntegrationActionResponse,
    IntegrationCredentialUpdateRequest,
    IntegrationListResponse,
    IntegrationResponse,
)
from app.domains.admin.integrations.service import AdminIntegrationService
from app.domains.identity.dependencies import require_roles
from app.domains.identity.schemas import UserResponse

router = APIRouter(prefix="/api/admin/integrations", tags=["admin-integrations"])


def get_admin_integration_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminIntegrationService:
    return AdminIntegrationService(db, settings)


@router.get("", response_model=IntegrationListResponse)
async def list_integrations(
    service: Annotated[AdminIntegrationService, Depends(get_admin_integration_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> IntegrationListResponse:
    return IntegrationListResponse(integrations=await service.list_integrations())


@router.patch("/{integration_type}/credentials", response_model=IntegrationResponse)
async def update_integration_credentials(
    integration_type: IntegrationType,
    payload: IntegrationCredentialUpdateRequest,
    service: Annotated[AdminIntegrationService, Depends(get_admin_integration_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> IntegrationResponse:
    return await service.update_credentials(
        integration_type=integration_type,
        payload=payload,
        current_admin=current_admin,
    )


@router.post("/{integration_type}/test", response_model=IntegrationActionResponse)
async def test_integration(
    integration_type: IntegrationType,
    service: Annotated[AdminIntegrationService, Depends(get_admin_integration_service)],
    current_admin: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> IntegrationActionResponse:
    return IntegrationActionResponse(
        integration=await service.test_integration(
            integration_type=integration_type,
            current_admin=current_admin,
        )
    )


@router.post("/{integration_type}/enable", response_model=IntegrationActionResponse)
async def enable_integration(
    integration_type: IntegrationType,
    service: Annotated[AdminIntegrationService, Depends(get_admin_integration_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> IntegrationActionResponse:
    return IntegrationActionResponse(
        integration=await service.enable_integration(integration_type=integration_type)
    )


@router.post("/{integration_type}/disable", response_model=IntegrationActionResponse)
async def disable_integration(
    integration_type: IntegrationType,
    service: Annotated[AdminIntegrationService, Depends(get_admin_integration_service)],
    _: Annotated[UserResponse, Depends(require_roles(RoleType.admin))],
) -> IntegrationActionResponse:
    return IntegrationActionResponse(
        integration=await service.disable_integration(integration_type=integration_type)
    )
