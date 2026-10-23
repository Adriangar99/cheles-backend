from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app import models as legacy_orm
from app.categorization.infrastructure import orm as categorization_orm
from app.config import get_settings
from app.db import Base
from app.identity.infrastructure import orm as identity_orm
from app.transactions.infrastructure import orm as transactions_orm

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    # Keep the app's own loggers working when migrations run inside an already configured process
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Importing every ORM module registers its tables on Base.metadata
ORM_MODULES = (legacy_orm, categorization_orm, identity_orm, transactions_orm)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # A caller (e.g. the migrate command) may hand over an open connection
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
