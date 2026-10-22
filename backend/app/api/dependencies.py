import hmac
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_token
from app.core.time import utc_now
from app.db.models import SessionRecord, User
from app.db.session import get_db

SESSION_COOKIE_NAME = "efficiencyday_session"


def get_current_session(request: Request, db: Session = Depends(get_db)) -> SessionRecord:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    session_record = db.scalar(
        select(SessionRecord).where(
            SessionRecord.token_hash == hash_token(token),
            SessionRecord.revoked_at.is_(None),
            SessionRecord.expires_at > utc_now(),
        )
    )
    if session_record is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return session_record


def get_current_user(
    current_session: SessionRecord = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, current_session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user


def _origin_tuple(value: str, *, allow_root_path: bool = False) -> tuple[str, str, int] | None:
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in (("", "/") if allow_root_path else ("",))
        ):
            return None
        scheme = parsed.scheme.lower()
        port = parsed.port
    except ValueError:
        return None

    if port is None:
        port = 443 if scheme == "https" else 80
    return scheme, parsed.hostname.lower(), port


def require_csrf(
    request: Request,
    current_session: SessionRecord = Depends(get_current_session),
) -> None:
    expected_origin = _origin_tuple(str(request.base_url), allow_root_path=True)
    actual_origin = _origin_tuple(request.headers.get("origin", ""))
    supplied_token = request.headers.get("x-csrf-token", "")
    if (
        expected_origin is None
        or actual_origin != expected_origin
        or not supplied_token
        or not hmac.compare_digest(
            current_session.csrf_token.encode("utf-8"), supplied_token.encode("utf-8")
        )
    ):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")
