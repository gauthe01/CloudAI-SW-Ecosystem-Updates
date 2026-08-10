from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    version: str


class ReadinessResponse(HealthResponse):
    database: str


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.app_env,
        version="0.1.0",
    )


@router.get("/api/health/ready", response_model=ReadinessResponse)
async def readiness() -> ReadinessResponse:
    settings = get_settings()
    database_status = "ok"

    async with get_engine().connect() as connection:
        await connection.execute(text("select 1"))

    return ReadinessResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.app_env,
        version="0.1.0",
        database=database_status,
    )
