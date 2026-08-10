from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.local_secrets import encrypt_local_secret, fingerprint_secret
from app.db.models.integration import (
    Integration,
    IntegrationSecret,
    IntegrationStatus,
    IntegrationTestRun,
    IntegrationTestStatus,
    IntegrationType,
)
from app.domains.admin.integrations.schemas import (
    IntegrationCredentialUpdateRequest,
    IntegrationFieldResponse,
    IntegrationResponse,
    IntegrationTestRunResponse,
)
from app.domains.identity.schemas import UserResponse


@dataclass(frozen=True)
class IntegrationFieldDefinition:
    name: str
    label: str
    input_type: str = "password"
    required: bool = True


@dataclass(frozen=True)
class IntegrationDefinition:
    integration_type: IntegrationType
    display_name: str
    description: str
    webhook_path: str | None
    fields: tuple[IntegrationFieldDefinition, ...]


INTEGRATION_DEFINITIONS: tuple[IntegrationDefinition, ...] = (
    IntegrationDefinition(
        integration_type=IntegrationType.slack,
        display_name="Slack",
        description="Workspace-level Slack app credentials for event ingestion.",
        webhook_path="/api/webhooks/slack/events",
        fields=(
            IntegrationFieldDefinition("signing_secret", "Signing Secret"),
            IntegrationFieldDefinition("bot_token", "Bot Token"),
        ),
    ),
    IntegrationDefinition(
        integration_type=IntegrationType.jira,
        display_name="Jira",
        description="Global Jira credentials for approved ticket-level connected sources.",
        webhook_path="/api/webhooks/jira/events",
        fields=(
            IntegrationFieldDefinition("base_url", "Base URL", "text"),
            IntegrationFieldDefinition("service_token", "Service Token"),
            IntegrationFieldDefinition("webhook_secret", "Webhook Secret"),
        ),
    ),
    IntegrationDefinition(
        integration_type=IntegrationType.sharepoint,
        display_name="SharePoint / Microsoft Graph",
        description="Microsoft Graph app credentials for approved SharePoint file sources.",
        webhook_path=None,
        fields=(
            IntegrationFieldDefinition("tenant_id", "Tenant ID", "text"),
            IntegrationFieldDefinition("client_id", "Client ID", "text"),
            IntegrationFieldDefinition("client_secret", "Client Secret"),
            IntegrationFieldDefinition("client_state", "Client State"),
        ),
    ),
    IntegrationDefinition(
        integration_type=IntegrationType.confluence,
        display_name="Confluence",
        description="Global Confluence access for approved page-level sources.",
        webhook_path="/api/webhooks/confluence/events",
        fields=(
            IntegrationFieldDefinition("base_url", "Base URL", "text"),
            IntegrationFieldDefinition("service_token", "Service Token"),
            IntegrationFieldDefinition("webhook_secret", "Webhook Secret"),
        ),
    ),
    IntegrationDefinition(
        integration_type=IntegrationType.github,
        display_name="GitHub",
        description=(
            "GitHub app credentials for approved repository, issue, and pull request sources."
        ),
        webhook_path="/api/webhooks/github/events",
        fields=(
            IntegrationFieldDefinition("app_id", "App ID", "text"),
            IntegrationFieldDefinition("private_key", "Private Key"),
            IntegrationFieldDefinition("webhook_secret", "Webhook Secret"),
        ),
    ),
)

DEFINITIONS_BY_TYPE = {
    definition.integration_type: definition for definition in INTEGRATION_DEFINITIONS
}


class AdminIntegrationService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def list_integrations(self) -> list[IntegrationResponse]:
        integrations = await self._ensure_integrations()
        return [await self._to_response(integration) for integration in integrations]

    async def update_credentials(
        self,
        *,
        integration_type: IntegrationType,
        payload: IntegrationCredentialUpdateRequest,
        current_admin: UserResponse,
    ) -> IntegrationResponse:
        definition = definition_for_type(integration_type)
        integration = await self._get_or_create_integration(integration_type)
        allowed_names = {field.name for field in definition.fields}
        unknown_names = sorted(set(payload.secrets) - allowed_names)
        if unknown_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown credential field: {', '.join(unknown_names)}.",
            )

        now = datetime.now(UTC)
        existing_secrets = await self._load_secret_map(integration.integration_id)
        for secret_name, raw_value in payload.secrets.items():
            cleaned_value = raw_value.strip()
            if not cleaned_value:
                continue
            secret = existing_secrets.get(secret_name)
            fingerprint = fingerprint_secret(
                secret_name=secret_name,
                value=cleaned_value,
                master_key=self.settings.app_secret_key,
            )
            ciphertext = encrypt_local_secret(
                secret_name=secret_name,
                value=cleaned_value,
                master_key=self.settings.app_secret_key,
            )
            if secret is None:
                secret = IntegrationSecret(
                    integration_id=integration.integration_id,
                    secret_name=secret_name,
                    secret_ciphertext=ciphertext,
                    value_fingerprint=fingerprint,
                    updated_by=current_admin.user_id,
                    updated_at=now,
                )
                self.db.add(secret)
                existing_secrets[secret_name] = secret
            else:
                secret.secret_ciphertext = ciphertext
                secret.value_fingerprint = fingerprint
                secret.updated_by = current_admin.user_id
                secret.updated_at = now

        configured = self._required_fields_configured(definition, existing_secrets)
        integration.status = (
            IntegrationStatus.configured.value
            if configured
            else IntegrationStatus.not_configured.value
        )
        integration.enabled_at = None
        integration.disabled_at = None
        integration.last_tested_at = None
        integration.last_test_status = None
        integration.last_error_summary = None
        integration.updated_at = now
        await self.db.commit()
        return await self._to_response(integration)

    async def test_integration(
        self,
        *,
        integration_type: IntegrationType,
        current_admin: UserResponse,
    ) -> IntegrationResponse:
        definition = definition_for_type(integration_type)
        integration = await self._get_or_create_integration(integration_type)
        existing_secrets = await self._load_secret_map(integration.integration_id)
        now = datetime.now(UTC)
        missing_fields = [
            field.label
            for field in definition.fields
            if field.required and field.name not in existing_secrets
        ]

        if missing_fields:
            result_summary = f"Missing required configuration: {', '.join(missing_fields)}."
            test_status = IntegrationTestStatus.failed
            integration.status = IntegrationStatus.not_configured.value
            integration.last_error_summary = result_summary
        else:
            result_summary = (
                "Local readiness check passed. Live external API validation is pending IT "
                "credentials and webhook access."
            )
            test_status = IntegrationTestStatus.succeeded
            integration.status = IntegrationStatus.enabled.value
            integration.enabled_at = now
            integration.disabled_at = None
            integration.last_error_summary = None

        test_run = IntegrationTestRun(
            integration_id=integration.integration_id,
            status=test_status.value,
            run_by=current_admin.user_id,
            started_at=now,
            finished_at=now,
            result_summary=result_summary,
        )
        self.db.add(test_run)
        integration.last_tested_at = now
        integration.last_test_status = test_status.value
        integration.updated_at = now
        await self.db.commit()
        return await self._to_response(integration)

    async def enable_integration(
        self,
        *,
        integration_type: IntegrationType,
    ) -> IntegrationResponse:
        definition = definition_for_type(integration_type)
        integration = await self._get_or_create_integration(integration_type)
        existing_secrets = await self._load_secret_map(integration.integration_id)
        if not self._required_fields_configured(definition, existing_secrets):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="All required credentials must be configured before enabling.",
            )
        if integration.last_test_status != IntegrationTestStatus.succeeded.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Run a successful readiness test before enabling this integration.",
            )
        now = datetime.now(UTC)
        integration.status = IntegrationStatus.enabled.value
        integration.enabled_at = now
        integration.disabled_at = None
        integration.updated_at = now
        await self.db.commit()
        return await self._to_response(integration)

    async def disable_integration(
        self,
        *,
        integration_type: IntegrationType,
    ) -> IntegrationResponse:
        integration = await self._get_or_create_integration(integration_type)
        now = datetime.now(UTC)
        integration.status = IntegrationStatus.disabled.value
        integration.disabled_at = now
        integration.enabled_at = None
        integration.updated_at = now
        await self.db.commit()
        return await self._to_response(integration)

    async def _ensure_integrations(self) -> list[Integration]:
        result = await self.db.execute(select(Integration))
        integrations_by_type = {
            IntegrationType(integration.integration_type): integration
            for integration in result.scalars().all()
        }
        now = datetime.now(UTC)
        for definition in INTEGRATION_DEFINITIONS:
            if definition.integration_type not in integrations_by_type:
                integration = Integration(
                    integration_type=definition.integration_type.value,
                    status=IntegrationStatus.not_configured.value,
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(integration)
                integrations_by_type[definition.integration_type] = integration
        await self.db.commit()
        return [
            integrations_by_type[definition.integration_type]
            for definition in INTEGRATION_DEFINITIONS
        ]

    async def _get_or_create_integration(self, integration_type: IntegrationType) -> Integration:
        result = await self.db.execute(
            select(Integration).where(Integration.integration_type == integration_type.value)
        )
        integration = result.scalar_one_or_none()
        if integration is not None:
            return integration
        now = datetime.now(UTC)
        integration = Integration(
            integration_type=integration_type.value,
            status=IntegrationStatus.not_configured.value,
            created_at=now,
            updated_at=now,
        )
        self.db.add(integration)
        await self.db.flush()
        return integration

    async def _load_secret_map(
        self,
        integration_id,
    ) -> dict[str, IntegrationSecret]:
        result = await self.db.execute(
            select(IntegrationSecret).where(IntegrationSecret.integration_id == integration_id)
        )
        return {secret.secret_name: secret for secret in result.scalars().all()}

    async def _load_recent_test_runs(
        self,
        integration_id,
    ) -> list[IntegrationTestRun]:
        result = await self.db.execute(
            select(IntegrationTestRun)
            .where(IntegrationTestRun.integration_id == integration_id)
            .order_by(IntegrationTestRun.started_at.desc())
            .limit(3)
        )
        return list(result.scalars().all())

    async def _to_response(self, integration: Integration) -> IntegrationResponse:
        integration_type = IntegrationType(integration.integration_type)
        definition = definition_for_type(integration_type)
        secrets = await self._load_secret_map(integration.integration_id)
        recent_test_runs = await self._load_recent_test_runs(integration.integration_id)
        fields = [
            IntegrationFieldResponse(
                name=field.name,
                label=field.label,
                input_type=field.input_type,
                required=field.required,
                configured=field.name in secrets,
                last_updated_at=secrets[field.name].updated_at if field.name in secrets else None,
            )
            for field in definition.fields
        ]
        configured_count = sum(1 for field in fields if field.required and field.configured)
        required_count = sum(1 for field in fields if field.required)
        return IntegrationResponse(
            integration_id=str(integration.integration_id),
            integration_type=integration_type,
            display_name=definition.display_name,
            description=definition.description,
            status=IntegrationStatus(integration.status),
            required_configured_count=configured_count,
            required_field_count=required_count,
            webhook_url=self._webhook_url(definition),
            fields=fields,
            last_tested_at=integration.last_tested_at,
            last_test_status=(
                IntegrationTestStatus(integration.last_test_status)
                if integration.last_test_status
                else None
            ),
            last_error_summary=integration.last_error_summary,
            enabled_at=integration.enabled_at,
            disabled_at=integration.disabled_at,
            recent_test_runs=[
                IntegrationTestRunResponse(
                    test_run_id=str(test_run.test_run_id),
                    status=IntegrationTestStatus(test_run.status),
                    started_at=test_run.started_at,
                    finished_at=test_run.finished_at,
                    result_summary=test_run.result_summary,
                )
                for test_run in recent_test_runs
            ],
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )

    def _webhook_url(self, definition: IntegrationDefinition) -> str | None:
        if definition.webhook_path is None:
            return None
        return f"{self.settings.api_base_url.rstrip('/')}{definition.webhook_path}"

    def _required_fields_configured(
        self,
        definition: IntegrationDefinition,
        secrets: dict[str, IntegrationSecret],
    ) -> bool:
        return all(field.name in secrets for field in definition.fields if field.required)


def definition_for_type(integration_type: IntegrationType) -> IntegrationDefinition:
    try:
        return DEFINITIONS_BY_TYPE[integration_type]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration type is not supported.",
        ) from exc
