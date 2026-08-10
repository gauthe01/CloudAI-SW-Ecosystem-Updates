import base64
import uuid

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models.connected_source import ConnectedSource, ConnectedSourceStatus
from app.db.models.identity import (
    RoleType,
    User,
    UserLocalCredential,
    UserRoleAssignment,
    UserSession,
)
from app.db.models.integration import (
    Integration,
    IntegrationSecret,
    IntegrationTestRun,
    IntegrationType,
)
from app.db.models.partner import Partner, PartnerContributorAssignment, PartnerStatus
from app.db.models.partner_update import PartnerUpdate, PartnerUpdateStatus
from app.db.models.source_event import AgentRun, SourceEvent, SourcePayload
from app.db.models.storage_object import StorageObject
from app.db.session import get_session_factory
from app.domains.admin.integrations.schemas import IntegrationCredentialUpdateRequest
from app.domains.admin.integrations.service import AdminIntegrationService
from app.domains.contributor.connected_sources.schemas import ConnectedSourceRequest
from app.domains.contributor.connected_sources.service import ContributorConnectedSourceService
from app.domains.identity.repository import IdentityRepository
from app.domains.identity.service import user_to_response
from app.main import create_app

SHAREPOINT_CLIENT_STATE = "test-sharepoint-client-state"


@pytest.mark.asyncio
async def test_sharepoint_validation_token_returns_plain_text() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/webhooks/sharepoint/events?validationToken=validation-value"
        )

    assert response.status_code == 200
    assert response.text == "validation-value"
    assert response.headers["content-type"].startswith("text/plain")


@pytest.mark.asyncio
async def test_sharepoint_notification_creates_pending_update_and_stores_file_copy(
    tmp_path,
) -> None:
    admin_email = f"sharepoint-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"sharepoint-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"SharePoint Partner {uuid.uuid4()}"
    file_url = "https://contoso.sharepoint.com/sites/aws/Shared%20Documents/aws-status.txt"
    extracted_text = "Release status update: partner validation risk is now blocked."
    settings = get_settings().model_copy(update={"local_upload_storage_dir": str(tmp_path)})

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_sharepoint_integration(session, admin_email)
        await create_active_sharepoint_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            file_url=file_url,
        )

    payload = sharepoint_payload(file_url=file_url, extracted_text=extracted_text)
    response = await post_sharepoint_payload(payload, settings=settings)

    assert response.status_code == 200
    assert response.json()["processed_count"] == 1

    async with get_session_factory()() as session:
        source_events = list((await session.execute(select(SourceEvent))).scalars().all())
        payloads = list((await session.execute(select(SourcePayload))).scalars().all())
        storage_objects = list((await session.execute(select(StorageObject))).scalars().all())
        updates = list((await session.execute(select(PartnerUpdate))).scalars().all())

        assert len(source_events) == 1
        assert source_events[0].source_type == "sharepoint_file"
        assert source_events[0].technical_metadata["change_type"] == "updated"
        assert extracted_text not in str(source_events[0].technical_metadata)

        assert len(storage_objects) == 1
        assert storage_objects[0].original_filename == "aws-status.txt"
        assert storage_objects[0].text_preview == extracted_text
        assert (tmp_path / storage_objects[0].storage_key).exists()

        assert len(payloads) == 1
        assert payloads[0].raw_payload_json is None
        assert payloads[0].raw_text_encrypted is None
        assert payloads[0].storage_object_id == storage_objects[0].storage_object_id

        assert len(updates) == 1
        assert updates[0].status == PartnerUpdateStatus.pending.value
        assert updates[0].source_type == "sharepoint"
        assert updates[0].source_url == file_url
        assert updates[0].source_event_id == source_events[0].source_event_id
        assert "partner validation risk" in updates[0].summary

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_sharepoint_duplicate_notification_does_not_duplicate_update(tmp_path) -> None:
    admin_email = f"sharepoint-duplicate-admin-{uuid.uuid4()}@example.com"
    contributor_email = f"sharepoint-duplicate-contributor-{uuid.uuid4()}@example.com"
    partner_name = f"SharePoint Duplicate Partner {uuid.uuid4()}"
    file_url = "https://contoso.sharepoint.com/sites/aws/Shared%20Documents/duplicate.txt"
    settings = get_settings().model_copy(update={"local_upload_storage_dir": str(tmp_path)})

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await configure_sharepoint_integration(session, admin_email)
        await create_active_sharepoint_source(
            session,
            partner_name=partner_name,
            contributor_email=contributor_email,
            file_url=file_url,
        )

    payload = sharepoint_payload(file_url=file_url)
    first_response = await post_sharepoint_payload(payload, settings=settings)
    second_response = await post_sharepoint_payload(payload, settings=settings)

    assert first_response.json()["processed_count"] == 1
    assert second_response.json()["duplicate_count"] == 1

    async with get_session_factory()() as session:
        events = list((await session.execute(select(SourceEvent))).scalars().all())
        updates = list((await session.execute(select(PartnerUpdate))).scalars().all())
        assert len(events) == 1
        assert len(updates) == 1

        await cleanup_test_records(session, [partner_name], [admin_email, contributor_email])
        await session.commit()


@pytest.mark.asyncio
async def test_sharepoint_notification_for_unmapped_file_is_ignored() -> None:
    admin_email = f"sharepoint-unmapped-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await configure_sharepoint_integration(session, admin_email)

    response = await post_sharepoint_payload(
        sharepoint_payload(
            file_url="https://contoso.sharepoint.com/sites/aws/Shared%20Documents/unmapped.txt"
        )
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

    async with get_session_factory()() as session:
        assert list((await session.execute(select(SourceEvent))).scalars().all()) == []
        await cleanup_test_records(session, [], [admin_email])
        await session.commit()


@pytest.mark.asyncio
async def test_sharepoint_rejects_invalid_client_state() -> None:
    admin_email = f"sharepoint-invalid-admin-{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await configure_sharepoint_integration(session, admin_email)

    payload = sharepoint_payload(file_url="https://contoso.sharepoint.com/doc.txt")
    payload["value"][0]["clientState"] = "wrong-client-state"
    response = await post_sharepoint_payload(payload)

    assert response.status_code == 401

    async with get_session_factory()() as session:
        await cleanup_test_records(session, [], [admin_email])
        await session.commit()


async def configure_sharepoint_integration(session: AsyncSession, admin_email: str) -> None:
    repository = IdentityRepository(session)
    admin = repository.add_user_with_local_password(
        email=admin_email,
        display_name="SharePoint Admin",
        password_hash=hash_password("test-password"),
        roles=[RoleType.admin],
    )
    await session.commit()
    service = AdminIntegrationService(session, get_settings())
    await service.update_credentials(
        integration_type=IntegrationType.sharepoint,
        payload=IntegrationCredentialUpdateRequest(
            secrets={
                "tenant_id": "tenant-id",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "client_state": SHAREPOINT_CLIENT_STATE,
            }
        ),
        current_admin=user_to_response(admin),
    )
    await service.test_integration(
        integration_type=IntegrationType.sharepoint,
        current_admin=user_to_response(admin),
    )


async def create_active_sharepoint_source(
    session: AsyncSession,
    *,
    partner_name: str,
    contributor_email: str,
    file_url: str,
) -> ConnectedSource:
    contributor = User(email=contributor_email, display_name="SharePoint Contributor")
    contributor.role_assignments = [UserRoleAssignment(role_type=RoleType.contributor)]
    partner = Partner(
        name=partner_name,
        description="SharePoint partner",
        status=PartnerStatus.active.value,
    )
    session.add_all([contributor, partner])
    await session.flush()
    session.add(
        PartnerContributorAssignment(
            partner_id=partner.partner_id,
            user_id=contributor.user_id,
        )
    )
    await session.commit()

    response = await ContributorConnectedSourceService(session).create_source(
        partner_id=partner.partner_id,
        payload=ConnectedSourceRequest(
            source_type="sharepoint_file",
            source_url=file_url,
        ),
        current_user=user_to_response(contributor),
    )
    result = await session.execute(
        select(ConnectedSource).where(
            ConnectedSource.connected_source_id == response.connected_source_id
        )
    )
    source = result.scalar_one()
    source.status = ConnectedSourceStatus.active.value
    await session.commit()
    return source


def sharepoint_payload(
    *,
    file_url: str,
    extracted_text: str = "SharePoint status update identifies a release risk.",
) -> dict:
    file_bytes = extracted_text.encode()
    return {
        "value": [
            {
                "subscriptionId": "subscription-123",
                "clientState": SHAREPOINT_CLIENT_STATE,
                "changeType": "updated",
                "resource": "drives/drive-id/items/item-id",
                "tenantId": "tenant-id",
                "resourceData": {
                    "id": "item-id",
                    "@odata.type": "#Microsoft.Graph.DriveItem",
                    "webUrl": file_url,
                },
                "downloadedFile": {
                    "name": file_url.rsplit("/", 1)[-1],
                    "contentType": "text/plain",
                    "contentBase64": base64.b64encode(file_bytes).decode(),
                    "extractedText": extracted_text,
                    "webUrl": file_url,
                },
            }
        ]
    }


async def post_sharepoint_payload(
    payload: dict,
    *,
    settings=None,
) -> httpx.Response:
    app = create_app(settings=settings) if settings else create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        return await client.post(
            "/api/webhooks/sharepoint/events",
            json=payload,
        )


async def cleanup_test_records(
    session: AsyncSession,
    partner_names: list[str],
    emails: list[str],
) -> None:
    partner_ids = select_partner_ids(partner_names)
    await session.execute(delete(AgentRun))
    await session.execute(delete(SourcePayload))
    await session.execute(delete(PartnerUpdate))
    await session.execute(delete(SourceEvent))
    await session.execute(delete(StorageObject))
    await session.execute(delete(ConnectedSource))
    await session.execute(
        delete(PartnerContributorAssignment).where(
            PartnerContributorAssignment.partner_id.in_(partner_ids)
        )
    )
    await session.execute(delete(Partner).where(Partner.name.in_(partner_names)))
    await session.execute(delete(IntegrationTestRun))
    await session.execute(delete(IntegrationSecret))
    await session.execute(delete(Integration))
    await session.execute(
        delete(UserSession).where(UserSession.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(
        delete(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(
        delete(UserLocalCredential).where(UserLocalCredential.user_id.in_(select_user_ids(emails)))
    )
    await session.execute(delete(User).where(User.email.in_(emails)))


def select_partner_ids(partner_names: list[str]):
    return select(Partner.partner_id).where(Partner.name.in_(partner_names))


def select_user_ids(emails: list[str]):
    return select(User.user_id).where(User.email.in_(emails))
