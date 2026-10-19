from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import Settings
from app.db.session import create_database_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.engine = create_database_engine(settings)
        try:
            yield
        finally:
            application.state.engine.dispose()

    application = FastAPI(title="EfficiencyDay API", version="0.1.0", lifespan=lifespan)
    application.include_router(health_router, prefix="/api/v1")
    return application


app = create_app()
