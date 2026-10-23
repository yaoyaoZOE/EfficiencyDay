import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.work_items import router as work_items_router
from app.core.config import Settings
from app.db.migrations import get_current_revision, get_expected_revision
from app.db.session import create_database_engine, create_session_factory
from app.services.bootstrap import ensure_initial_user

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if not settings.session_cookie_secure:
            logger.warning(
                "EFFICIENCYDAY_SESSION_COOKIE_SECURE=false: insecure HTTP compatibility mode "
                "is enabled. Passwords, session tokens, and application data can be intercepted "
                "over HTTP. Use HTTPS and restore this setting to true for public deployment."
            )
        engine = create_database_engine(settings)
        application.state.engine = engine
        application.state.session_factory = create_session_factory(engine)
        try:
            try:
                current_revision = get_current_revision(engine)
            except SQLAlchemyError:
                logger.exception("Database startup readiness check failed")
            else:
                if current_revision == get_expected_revision():
                    ensure_initial_user(application.state.session_factory, settings)
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="EfficiencyDay API", version="0.1.0", lifespan=lifespan)
    application.state.settings = settings
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(work_items_router, prefix="/api/v1")
    return application


app = create_app()
