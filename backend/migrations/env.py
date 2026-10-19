from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import Settings
from app.db.models import Base
from app.db.session import create_database_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
override_url = config.get_main_option("sqlalchemy.url")

if context.is_offline_mode():
    from sqlalchemy import URL

    url = override_url or URL.create("sqlite", database=str(Settings().database_path))
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = (
        create_engine(override_url, poolclass=pool.NullPool)
        if override_url
        else create_database_engine(Settings())
    )
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
