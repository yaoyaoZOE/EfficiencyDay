from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import (
    SESSION_COOKIE_NAME,
    get_current_session,
    get_current_user,
    require_csrf,
    require_public_origin,
)
from app.core.time import utc_now
from app.db.models import SessionRecord, User
from app.db.session import get_db
from app.schemas.auth import AuthStatusResponse, CurrentUserResponse, LoginRequest
from app.services.auth import authenticate_user, revoke_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=AuthStatusResponse,
    dependencies=[Depends(require_public_origin)],
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    result = authenticate_user(
        db,
        payload.username,
        payload.password,
        settings=request.app.state.settings,
    )
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    _, _, token = result
    db.commit()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return AuthStatusResponse()


@router.get("/me", response_model=CurrentUserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    current_session: SessionRecord = Depends(get_current_session),
) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        timezone=current_user.timezone,
        csrf_token=current_session.csrf_token,
    )


@router.post("/logout", response_model=AuthStatusResponse, dependencies=[Depends(require_csrf)])
def logout(
    response: Response,
    current_session: SessionRecord = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> AuthStatusResponse:
    revoke_session(db, current_session, utc_now())
    db.commit()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return AuthStatusResponse()
