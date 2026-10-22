import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.db.migrations import get_current_revision, get_expected_revision

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["efficiencyday-api"] = "efficiencyday-api"


class ReadyResponse(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"


@router.get("/live", response_model=LiveResponse)
def liveness() -> LiveResponse:
    return LiveResponse()


@router.get("/ready", response_model=ReadyResponse, responses={503: {"description": "Not ready"}})
def readiness(request: Request) -> ReadyResponse:
    expected_revision = get_expected_revision()
    try:
        revision = get_current_revision(request.app.state.engine)
    except SQLAlchemyError as exc:
        logger.exception("Database readiness check failed")
        raise HTTPException(status_code=503, detail="Database is unavailable.") from exc
    if revision != expected_revision:
        logger.error(
            "Database revision mismatch: expected=%s actual=%s", expected_revision, revision
        )
        raise HTTPException(status_code=503, detail="Database migrations are not up to date.")
    return ReadyResponse()
