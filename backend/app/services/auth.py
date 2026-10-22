from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_opaque_token, hash_token, verify_password
from app.core.time import utc_now
from app.db.models import SessionRecord, User


def authenticate_user(
    session: Session,
    username: str,
    password: str,
    settings: Settings | None = None,
) -> tuple[User, SessionRecord, str] | None:
    user = session.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        return None

    current_time = utc_now()
    session_token = create_opaque_token()
    session_record = SessionRecord(
        user_id=user.id,
        token_hash=hash_token(session_token),
        csrf_token=create_opaque_token(),
        created_at=current_time,
        expires_at=current_time
        + timedelta(days=(settings if settings is not None else Settings()).session_ttl_days),
    )
    session.add(session_record)
    session.flush()
    return user, session_record, session_token


def revoke_session(session: Session, session_record: SessionRecord, now: datetime) -> None:
    session_record.revoked_at = now
    session.add(session_record)
