from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.local_secrets import decrypt_local_secret
from app.db.models.integration import Integration, IntegrationSecret, IntegrationType


async def get_integration_secret_value(
    db: AsyncSession,
    settings: Settings,
    *,
    integration_type: IntegrationType,
    secret_name: str,
) -> str | None:
    result = await db.execute(
        select(IntegrationSecret)
        .join(Integration, Integration.integration_id == IntegrationSecret.integration_id)
        .where(Integration.integration_type == integration_type.value)
        .where(IntegrationSecret.secret_name == secret_name)
    )
    secret = result.scalar_one_or_none()
    if secret is None:
        return None
    return decrypt_local_secret(
        secret_name=secret.secret_name,
        ciphertext=secret.secret_ciphertext,
        master_key=settings.app_secret_key,
    )
