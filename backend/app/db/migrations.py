from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

from app.core.config import BACKEND_ROOT


def get_current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def get_expected_revision() -> str:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    return ScriptDirectory.from_config(config).get_current_head()
