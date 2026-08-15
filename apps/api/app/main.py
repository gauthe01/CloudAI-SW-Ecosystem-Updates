from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import close_db
from app.domains.access_requests.router import admin_router as admin_access_requests_router
from app.domains.access_requests.router import public_router as public_access_requests_router
from app.domains.admin.connected_sources.router import router as admin_connected_sources_router
from app.domains.admin.integrations.router import router as admin_integrations_router
from app.domains.admin.knowledge_uploads.router import router as admin_knowledge_uploads_router
from app.domains.admin.partners.router import router as admin_partners_router
from app.domains.admin.topic_updates.router import router as admin_topic_updates_router
from app.domains.admin.users.router import router as admin_users_router
from app.domains.contributor.connected_sources.router import (
    router as contributor_connected_sources_router,
)
from app.domains.contributor.metadata.router import router as contributor_metadata_router
from app.domains.contributor.partners.router import router as contributor_partners_router
from app.domains.contributor.updates.router import router as contributor_updates_router
from app.domains.contributor.uploads.router import router as contributor_uploads_router
from app.domains.health.router import router as health_router
from app.domains.identity.router import router as identity_router
from app.domains.presenter.router import router as presenter_router
from app.domains.webhooks.confluence.router import router as confluence_webhooks_router
from app.domains.webhooks.github.router import router as github_webhooks_router
from app.domains.webhooks.jira.router import router as jira_webhooks_router
from app.domains.webhooks.sharepoint.router import router as sharepoint_webhooks_router
from app.domains.webhooks.slack.router import router as slack_webhooks_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("api_starting", extra={"app_name": settings.app_name, "env": settings.app_env})
    yield
    await close_db()
    logger.info("api_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        docs_url="/api/docs" if settings.enable_api_docs else None,
        redoc_url="/api/redoc" if settings.enable_api_docs else None,
        openapi_url="/api/openapi.json" if settings.enable_api_docs else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.dependency_overrides[get_settings] = lambda: settings

    app.include_router(admin_access_requests_router)
    app.include_router(admin_connected_sources_router)
    app.include_router(admin_integrations_router)
    app.include_router(admin_knowledge_uploads_router)
    app.include_router(admin_partners_router)
    app.include_router(admin_topic_updates_router)
    app.include_router(admin_users_router)
    app.include_router(contributor_connected_sources_router)
    app.include_router(contributor_metadata_router)
    app.include_router(contributor_partners_router)
    app.include_router(contributor_uploads_router)
    app.include_router(contributor_updates_router)
    app.include_router(health_router)
    app.include_router(identity_router)
    app.include_router(presenter_router)
    app.include_router(public_access_requests_router)
    app.include_router(confluence_webhooks_router)
    app.include_router(github_webhooks_router)
    app.include_router(jira_webhooks_router)
    app.include_router(sharepoint_webhooks_router)
    app.include_router(slack_webhooks_router)
    return app


app = create_app()
