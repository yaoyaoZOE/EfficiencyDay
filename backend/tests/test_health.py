from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migrate(database_path: Path) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    command.upgrade(config, "head")


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
    migrate(database_path)
    settings = Settings(database_path=database_path, _env_file=None)
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
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database is unavailable."


def test_readiness_rejects_unknown_migration(tmp_path: Path) -> None:
    from app.core.config import Settings
    from app.main import create_app

    database_path = tmp_path / "test.db"
    migrate(database_path)
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
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        assert "app_metadata" in inspect(engine).get_table_names()
        command.downgrade(config, "base")
        assert "app_metadata" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        assert "app_metadata" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
