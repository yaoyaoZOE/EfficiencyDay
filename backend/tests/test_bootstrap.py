from pathlib import Path

import pytest
from conftest import migrate_database
from sqlalchemy import URL, create_engine, select

from app.core.config import Settings
from app.db.models import User


def _session_factory(database_path: Path):
    migrate_database(database_path)
    from app.db.session import create_session_factory

    engine = create_engine(URL.create("sqlite", database=str(database_path)))
    return engine, create_session_factory(engine)


def test_initial_user_is_created_once_for_migrated_empty_database(tmp_path: Path) -> None:
    from app.services.bootstrap import ensure_initial_user

    engine, session_factory = _session_factory(tmp_path / "test.db")
    try:
        settings = Settings(
            initial_username="admin",
            initial_password="first-password",
            _env_file=None,
        )
        ensure_initial_user(session_factory, settings)

        with session_factory() as session:
            user = session.scalar(select(User))
            assert user is not None
            assert user.username == "admin"
            assert user.timezone == "Asia/Shanghai"
            password_hash = user.password_hash
            assert password_hash != "first-password"

        ensure_initial_user(
            session_factory,
            Settings(
                initial_username="replacement",
                initial_password="replacement-password",
                _env_file=None,
            ),
        )
        with session_factory() as session:
            users = session.scalars(select(User)).all()
            assert len(users) == 1
            assert users[0].password_hash == password_hash
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("username", "password"),
    [
        (None, None),
        ("", "password"),
        ("   ", "password"),
        ("admin", None),
        ("admin", ""),
        ("admin", "   "),
    ],
)
def test_empty_database_requires_nonblank_bootstrap_credentials(
    tmp_path: Path, username: str | None, password: str | None
) -> None:
    from app.services.bootstrap import ensure_initial_user

    engine, session_factory = _session_factory(tmp_path / "test.db")
    try:
        settings = Settings(
            initial_username=username,
            initial_password=password,
            _env_file=None,
        )
        with pytest.raises(RuntimeError, match="initial user credentials"):
            ensure_initial_user(session_factory, settings)
    finally:
        engine.dispose()


def test_existing_user_does_not_require_bootstrap_credentials(tmp_path: Path) -> None:
    from app.services.bootstrap import ensure_initial_user

    engine, session_factory = _session_factory(tmp_path / "test.db")
    try:
        with session_factory.begin() as session:
            session.add(User(username="existing", password_hash="existing-hash"))

        ensure_initial_user(session_factory, Settings(_env_file=None))

        with session_factory() as session:
            users = session.scalars(select(User)).all()
            assert [(user.username, user.password_hash) for user in users] == [
                ("existing", "existing-hash")
            ]
    finally:
        engine.dispose()
