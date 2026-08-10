import argparse
import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import close_db, get_session_factory
from app.domains.source_events.service import SourceEventQueueService

logger = get_logger(__name__)


async def run_once() -> None:
    settings = get_settings()
    async with get_session_factory()() as session:
        result = await SourceEventQueueService(session).process_next_event()
    logger.info(
        "worker_run_once",
        extra={
            "app_name": settings.app_name,
            "env": settings.app_env,
            "processed": result.processed,
            "status": result.status,
            "worker_message": result.message,
        },
    )


async def run_forever(poll_seconds: float) -> None:
    settings = get_settings()
    logger.info(
        "worker_starting",
        extra={"app_name": settings.app_name, "env": settings.app_env},
    )
    try:
        while True:
            await run_once()
            await asyncio.sleep(poll_seconds)
    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cloud AI Software Ecosystem Updates worker")
    parser.add_argument("--once", action="store_true", help="Run one worker tick and exit.")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    if args.once:
        asyncio.run(run_once())
        return

    asyncio.run(run_forever(args.poll_seconds))


if __name__ == "__main__":
    main()
