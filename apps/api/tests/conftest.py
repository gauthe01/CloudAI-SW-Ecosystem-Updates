import asyncio
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import asyncpg
import pytest
import pytest_asyncio
from alembic.config import Config

from alembic import command

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/"
    "cloud_ai_software_ecosystem_updates_test",
)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    asyncio.run(ensure_test_database_exists(TEST_DATABASE_URL))
    migrate_test_database()


@pytest_asyncio.fixture(autouse=True)
async def close_db_between_tests():
    from app.db.session import close_db

    yield
    await close_db()


async def ensure_test_database_exists(database_url: str) -> None:
    parsed = urlparse(database_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    database_name = parsed.path.lstrip("/")
    if not database_name:
        raise RuntimeError("Test database URL must include a database name.")

    connection = await asyncpg.connect(
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        database="postgres",
    )
    try:
        exists = await connection.fetchval(
            "select 1 from pg_database where datname = $1",
            database_name,
        )
        if not exists:
            await connection.execute(
                f"create database {quote_identifier(database_name)}"  # noqa: S608
            )
    finally:
        await connection.close()


def migrate_test_database() -> None:
    api_dir = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(api_dir / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(api_dir / "alembic"))
    command.upgrade(alembic_config, "head")


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
