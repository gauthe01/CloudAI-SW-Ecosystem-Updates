import argparse
import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import close_db, get_session_factory
from app.domains.source_sync.service import SourceSyncService

logger = get_logger(__name__)


async def run_once() -> None:
    settings = get_settings()
    async with get_session_factory()() as session:
        result = await SourceSyncService(session, settings).run_due_sources()
    logger.info(
        "source_sync_run_once",
        extra={
            "app_name": settings.app_name,
            "env": settings.app_env,
            "processed": result.processed,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "skipped": result.skipped,
            "fetched": result.fetched,
            "queued": result.queued,
            "duplicates": result.duplicates,
            "ignored": result.ignored,
        },
    )


async def run_forever(poll_seconds: float) -> None:
    settings = get_settings()
    logger.info(
        "source_sync_worker_starting",
        extra={"app_name": settings.app_name, "env": settings.app_env},
    )
    try:
        while True:
            await run_once()
            await asyncio.sleep(poll_seconds)
    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cloud AI Software Ecosystem Updates source sync worker"
    )
    parser.add_argument("--once", action="store_true", help="Run one source sync tick and exit.")
    parser.add_argument("--poll-seconds", type=float, default=None)
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    if args.once:
        asyncio.run(run_once())
        return

    asyncio.run(run_forever(args.poll_seconds or settings.source_sync_poll_seconds))


if __name__ == "__main__":
    main()
