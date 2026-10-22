from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from conftest import make_alembic_config, migrate_database
from sqlalchemy import Column, MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError, StatementError

from app.core.config import Settings
from app.db.models import Base
from app.db.session import create_database_engine
from app.db.types import UTCDateTime


def test_core_migration_preserves_metadata_and_can_be_reapplied(tmp_path: Path) -> None:
    database_path = tmp_path / "core.db"
    migrate_database(database_path, "0001")
    engine = create_database_engine(Settings(database_path=database_path, _env_file=None))
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO app_metadata (key, value) VALUES ('version', 'kept')")
            )

        migrate_database(database_path)
        assert set(inspect(engine).get_table_names()) >= {
            "app_metadata",
            "users",
            "sessions",
            "work_items",
        }
        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT value FROM app_metadata WHERE key = 'version'")
            ) == "kept"

        config = make_alembic_config(database_path)
        command.downgrade(config, "0001")
        assert set(inspect(engine).get_table_names()) == {"alembic_version", "app_metadata"}

        migrate_database(database_path)
        assert set(inspect(engine).get_table_names()) >= {
            "app_metadata",
            "users",
            "sessions",
            "work_items",
        }
        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT value FROM app_metadata WHERE key = 'version'")
            ) == "kept"
    finally:
        engine.dispose()


def test_models_share_the_existing_declarative_base() -> None:
    assert {"app_metadata", "users", "sessions", "work_items"} <= set(Base.metadata.tables)


def test_sqlite_enforces_core_model_constraints(tmp_path: Path) -> None:
    database_path = tmp_path / "constraints.db"
    migrate_database(database_path)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            user_id = connection.scalar(
                text(
                    "INSERT INTO users (username, password_hash, created_at) "
                    "VALUES ('alice', 'password-hash', '2026-10-22 00:00:00') RETURNING id"
                )
            )
            work_item_id = connection.scalar(
                text(
                    "INSERT INTO work_items (user_id, title, created_at, updated_at) "
                    "VALUES (:user_id, 'First item', '2026-10-22 00:00:00', "
                    "'2026-10-22 00:00:00') RETURNING id"
                ),
                {"user_id": user_id},
            )
            assert connection.scalar(
                text("SELECT status FROM work_items WHERE id = :id"),
                {"id": work_item_id},
            ) == "pending"
            assert connection.scalar(
                text("SELECT version FROM work_items WHERE id = :id"),
                {"id": work_item_id},
            ) == 1

        invalid_statements = [
            (
                "INSERT INTO users (username, password_hash, created_at) "
                "VALUES ('alice', 'duplicate', '2026-10-22 00:00:00')",
                {},
            ),
            (
                "INSERT INTO work_items (user_id, title, status, created_at, updated_at) "
                "VALUES (:user_id, 'Bad status', 'unknown', "
                "'2026-10-22 00:00:00', '2026-10-22 00:00:00')",
                {"user_id": user_id},
            ),
            (
                "INSERT INTO work_items (user_id, title, version, created_at, updated_at) "
                "VALUES (:user_id, 'Bad version', 0, "
                "'2026-10-22 00:00:00', '2026-10-22 00:00:00')",
                {"user_id": user_id},
            ),
            (
                "INSERT INTO work_items (user_id, title, color_key, created_at, updated_at) "
                "VALUES (:user_id, 'Bad color', 'cyan', "
                "'2026-10-22 00:00:00', '2026-10-22 00:00:00')",
                {"user_id": user_id},
            ),
            (
                "INSERT INTO work_items "
                "(user_id, title, status, completed_on, created_at, updated_at) "
                "VALUES (:user_id, 'Incomplete state', 'pending', '2026-10-22', "
                "'2026-10-22 00:00:00', '2026-10-22 00:00:00')",
                {"user_id": user_id},
            ),
            (
                "INSERT INTO work_items (user_id, title, status, created_at, updated_at) "
                "VALUES (:user_id, 'Missing completion date', 'completed', "
                "'2026-10-22 00:00:00', '2026-10-22 00:00:00')",
                {"user_id": user_id},
            ),
        ]
        for statement, parameters in invalid_statements:
            with pytest.raises(IntegrityError):
                with engine.begin() as connection:
                    connection.execute(text(statement), parameters)
    finally:
        engine.dispose()


@pytest.mark.parametrize("column", ["urgency", "importance"])
def test_sqlite_enforces_boolean_values(tmp_path: Path, column: str) -> None:
    database_path = tmp_path / f"{column}.db"
    migrate_database(database_path)
    engine = create_database_engine(Settings(database_path=database_path, _env_file=None))
    try:
        with engine.begin() as connection:
            user_id = connection.scalar(
                text(
                    "INSERT INTO users (username, password_hash, created_at) "
                    "VALUES ('alice', 'password-hash', '2026-10-22 00:00:00') RETURNING id"
                )
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        f"INSERT INTO work_items (user_id, title, {column}, "
                        "created_at, updated_at) "
                        "VALUES (:user_id, 'Invalid boolean', 2, "
                        "'2026-10-22 00:00:00', '2026-10-22 00:00:00')"
                    ),
                    {"user_id": user_id},
                )
    finally:
        engine.dispose()


def test_user_deletion_cascades_to_sessions_and_work_items(tmp_path: Path) -> None:
    database_path = tmp_path / "cascade.db"
    migrate_database(database_path)
    engine = create_database_engine(Settings(database_path=database_path, _env_file=None))
    try:
        with engine.begin() as connection:
            user_id = connection.scalar(
                text(
                    "INSERT INTO users (username, password_hash, created_at) "
                    "VALUES ('alice', 'password-hash', '2026-10-22 00:00:00') RETURNING id"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO sessions "
                    "(user_id, token_hash, csrf_token, created_at, expires_at) "
                    "VALUES (:user_id, 'token-hash', 'csrf-token', "
                    "'2026-10-22 00:00:00', '2026-10-29 00:00:00')"
                ),
                {"user_id": user_id},
            )
            connection.execute(
                text(
                    "INSERT INTO work_items (user_id, title, created_at, updated_at) "
                    "VALUES (:user_id, 'First item', '2026-10-22 00:00:00', "
                    "'2026-10-22 00:00:00')"
                ),
                {"user_id": user_id},
            )
            connection.execute(
                text("DELETE FROM users WHERE id = :user_id"),
                {"user_id": user_id},
            )
            assert connection.scalar(text("SELECT count(*) FROM sessions")) == 0
            assert connection.scalar(text("SELECT count(*) FROM work_items")) == 0
    finally:
        engine.dispose()


def test_utc_datetime_round_trips_as_aware_utc(tmp_path: Path) -> None:
    database_path = tmp_path / "timestamp.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    instant = datetime(2026, 10, 22, 9, 30, tzinfo=timezone(timedelta(hours=-5)))
    timestamps = Table(
        "timestamps", MetaData(), Column("value", UTCDateTime(), nullable=False)
    )
    try:
        timestamps.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(timestamps.insert().values(value=instant))

        with engine.connect() as connection:
            loaded = connection.scalar(select(timestamps.c.value))
        assert loaded == instant.astimezone(UTC)
        assert loaded.tzinfo is UTC
    finally:
        engine.dispose()


def test_utc_datetime_rejects_naive_values(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'naive.db').as_posix()}")
    timestamps = Table(
        "timestamps", MetaData(), Column("value", UTCDateTime(), nullable=False)
    )
    try:
        timestamps.metadata.create_all(engine)
        with pytest.raises(StatementError, match="timezone-aware"):
            with engine.begin() as connection:
                connection.execute(
                    timestamps.insert().values(value=datetime(2026, 10, 22, 9, 30))
                )
    finally:
        engine.dispose()
