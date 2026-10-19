from sqlite3 import Connection

from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.pool import ConnectionPoolEntry

from app.core.config import Settings


def configure_sqlite(connection: Connection, _record: ConnectionPoolEntry) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=FULL")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def create_database_engine(settings: Settings) -> Engine:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        URL.create("sqlite", database=str(settings.database_path)),
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", configure_sqlite)
    return engine
