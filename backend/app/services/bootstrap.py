from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import User


def ensure_initial_user(session_factory: sessionmaker[Session], settings: Settings) -> None:
    with session_factory.begin() as session:
        if session.scalar(select(User).limit(1)) is not None:
            return

        username = settings.initial_username
        password = settings.initial_password
        if (
            username is None
            or not username.strip()
            or password is None
            or not password.get_secret_value().strip()
        ):
            raise RuntimeError("initial user credentials are required for an empty database")

        session.add(
            User(
                username=username,
                password_hash=PasswordHasher().hash(password.get_secret_value()),
                timezone="Asia/Shanghai",
            )
        )
