from pathlib import Path

from alembic import command
from conftest import make_alembic_config, migrate_database
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


def test_liveness_does_not_require_migrated_database(tmp_path: Path) -> None:
    from app.core.config import Settings
    from app.main import create_app

    settings = Settings(database_path=tmp_path / "test.db", _env_file=None)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "efficiencyday-api"}


def test_readiness_rejects_unmigrated_database(tmp_path: Path) -> None:
    from app.core.config import Settings
    from app.main import create_app

    settings = Settings(database_path=tmp_path / "test.db", _env_file=None)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database migrations are not up to date."


def test_readiness_checks_migration_and_database_settings(tmp_path: Path) -> None:
    from app.core.config import Settings
    from app.db.session import create_database_engine
    from app.main import create_app

    database_path = tmp_path / "test.db"
    migrate_database(database_path)
    settings = Settings(
        database_path=database_path,
        initial_username="health-user",
        initial_password="health-password",
        _env_file=None,
    )
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            assert connection.scalar(text("PRAGMA journal_mode")) == "wal"
            assert connection.scalar(text("PRAGMA synchronous")) == 2
        with TestClient(create_app(settings)) as client:
            response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok"}
    finally:
        engine.dispose()


def test_readiness_rejects_unavailable_database(tmp_path: Path) -> None:
    from app.core.config import Settings
    from app.main import create_app

    settings = Settings(database_path=tmp_path, _env_file=None)
    with TestClient(create_app(settings)) as client:
        live_response = client.get("/api/v1/health/live")
        response = client.get("/api/v1/health/ready")
    assert live_response.status_code == 200
    assert response.status_code == 503
    assert response.json()["detail"] == "Database is unavailable."


def test_readiness_rejects_unknown_migration(tmp_path: Path) -> None:
    from app.core.config import Settings
    from app.main import create_app

    database_path = tmp_path / "test.db"
    migrate_database(database_path)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = 'unknown'"))
    finally:
        engine.dispose()
    with TestClient(create_app(Settings(database_path=database_path, _env_file=None))) as client:
        assert client.get("/api/v1/health/ready").status_code == 503


def test_initial_migration_round_trip(tmp_path: Path) -> None:
    from sqlalchemy import inspect

    database_path = tmp_path / "test.db"
    migrate_database(database_path)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        assert "app_metadata" in inspect(engine).get_table_names()
        config = make_alembic_config(database_path)
        command.downgrade(config, "base")
        assert "app_metadata" not in inspect(engine).get_table_names()
        migrate_database(database_path)
        assert "app_metadata" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
