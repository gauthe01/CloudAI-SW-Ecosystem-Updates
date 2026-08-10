import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import close_db, get_session_factory
from app.domains.identity.service import AuthService

logger = get_logger(__name__)


async def bootstrap() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    async with get_session_factory()() as session:
        user = await AuthService(session, settings).bootstrap_local_admin()
        if user is None:
            logger.info("bootstrap_admin_skipped")
            return
        logger.info("bootstrap_admin_ready", extra={"email": user.email})

    await close_db()


if __name__ == "__main__":
    asyncio.run(bootstrap())
