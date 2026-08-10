import uuid

import pytest
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models.identity import RoleType, User, UserLocalCredential, UserRoleAssignment
from app.db.models.integration import (
    Integration,
    IntegrationSecret,
    IntegrationStatus,
    IntegrationTestRun,
    IntegrationTestStatus,
    IntegrationType,
)
from app.db.session import get_session_factory
from app.domains.admin.integrations.schemas import IntegrationCredentialUpdateRequest
from app.domains.admin.integrations.service import AdminIntegrationService
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.service import user_to_response


@pytest.mark.asyncio
async def test_admin_integrations_seed_all_supported_types() -> None:
    async with get_session_factory()() as session:
        await cleanup_integrations(session)
        service = AdminIntegrationService(session, get_settings())

        integrations = await service.list_integrations()

        assert [integration.integration_type for integration in integrations] == [
            IntegrationType.slack,
            IntegrationType.jira,
            IntegrationType.sharepoint,
            IntegrationType.confluence,
            IntegrationType.github,
        ]
        assert all(
            integration.status == IntegrationStatus.not_configured
            for integration in integrations
        )

        await cleanup_integrations(session)
        await session.commit()


@pytest.mark.asyncio
async def test_admin_can_save_credentials_without_returning_or_storing_raw_values() -> None:
    admin_email = f"integration-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_integrations(session)
        admin = await create_admin(session, admin_email)
        service = AdminIntegrationService(session, get_settings())

        response = await service.update_credentials(
            integration_type=IntegrationType.slack,
            payload=IntegrationCredentialUpdateRequest(
                secrets={
                    "signing_secret": "raw-signing-secret",
                    "bot_token": "xoxb-raw-token",
                }
            ),
            current_admin=user_to_response(admin),
        )

        assert response.status == IntegrationStatus.configured
        assert response.required_configured_count == response.required_field_count
        assert all(field.configured for field in response.fields)
        assert "raw-signing-secret" not in response.model_dump_json()
        assert "xoxb-raw-token" not in response.model_dump_json()

        result = await session.execute(select(IntegrationSecret))
        secrets = list(result.scalars().all())
        assert secrets
        assert all("raw" not in secret.secret_ciphertext for secret in secrets)

        await cleanup_integrations(session)
        await cleanup_test_users(session, [admin_email])
        await session.commit()


@pytest.mark.asyncio
async def test_readiness_test_fails_until_required_credentials_are_configured() -> None:
    admin_email = f"integration-test-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_integrations(session)
        admin = await create_admin(session, admin_email)
        service = AdminIntegrationService(session, get_settings())

        failed = await service.test_integration(
            integration_type=IntegrationType.jira,
            current_admin=user_to_response(admin),
        )

        assert failed.status == IntegrationStatus.not_configured
        assert failed.last_test_status == IntegrationTestStatus.failed
        assert "Missing required configuration" in (failed.last_error_summary or "")

        await cleanup_integrations(session)
        await cleanup_test_users(session, [admin_email])
        await session.commit()


@pytest.mark.asyncio
async def test_readiness_test_enables_configured_integration() -> None:
    admin_email = f"integration-enable-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_integrations(session)
        admin = await create_admin(session, admin_email)
        service = AdminIntegrationService(session, get_settings())
        current_admin = user_to_response(admin)

        await service.update_credentials(
            integration_type=IntegrationType.github,
            payload=IntegrationCredentialUpdateRequest(
                secrets={
                    "app_id": "12345",
                    "private_key": "private-key",
                    "webhook_secret": "webhook-secret",
                }
            ),
            current_admin=current_admin,
        )
        enabled = await service.test_integration(
            integration_type=IntegrationType.github,
            current_admin=current_admin,
        )

        assert enabled.status == IntegrationStatus.enabled
        assert enabled.last_test_status == IntegrationTestStatus.succeeded
        assert enabled.enabled_at is not None

        disabled = await service.disable_integration(integration_type=IntegrationType.github)
        assert disabled.status == IntegrationStatus.disabled
        assert disabled.disabled_at is not None

        await cleanup_integrations(session)
        await cleanup_test_users(session, [admin_email])
        await session.commit()


@pytest.mark.asyncio
async def test_admin_cannot_enable_without_successful_readiness_test() -> None:
    admin_email = f"integration-conflict-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_integrations(session)
        admin = await create_admin(session, admin_email)
        service = AdminIntegrationService(session, get_settings())

        await service.update_credentials(
            integration_type=IntegrationType.sharepoint,
            payload=IntegrationCredentialUpdateRequest(
                secrets={
                    "tenant_id": "tenant-id",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                }
            ),
            current_admin=user_to_response(admin),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.enable_integration(integration_type=IntegrationType.sharepoint)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

        await cleanup_integrations(session)
        await cleanup_test_users(session, [admin_email])
        await session.commit()


async def create_admin(session: AsyncSession, email: str) -> User:
    await cleanup_test_users(session, [email])
    repository = IdentityRepository(session)
    admin = repository.add_user_with_local_password(
        email=email,
        display_name="Integration Admin",
        password_hash=hash_password("test-password"),
        roles=[RoleType.admin],
    )
    await session.commit()
    return admin


async def cleanup_integrations(session: AsyncSession) -> None:
    await session.execute(delete(IntegrationTestRun))
    await session.execute(delete(IntegrationSecret))
    await session.execute(delete(Integration))


async def cleanup_test_users(session: AsyncSession, emails: list[str]) -> None:
    await session.execute(
        delete(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(
        delete(UserLocalCredential).where(UserLocalCredential.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(delete(User).where(User.email.in_(emails)))


def select_user_ids(emails: list[str]):
    return select(User.user_id).where(User.email.in_(emails))
