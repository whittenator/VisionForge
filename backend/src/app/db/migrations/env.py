from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging when logging sections exist.
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)  # may raise if no logging sections present
    except Exception:
        # Safe to ignore; Alembic logging config is optional for runtime migrations
        pass

# Add your model's MetaData object here for 'autogenerate' support
# from app.db.base import Base
# target_metadata = Base.metadata
target_metadata = None

# Override URL from environment: prefer DATABASE_URL, else derive from POSTGRES_* vars
database_url = os.getenv("DATABASE_URL")
if not database_url:
    database_url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER','visionforge')}:{os.getenv('POSTGRES_PASSWORD','change-me')}@"
        f"{os.getenv('POSTGRES_HOST','localhost')}:{os.getenv('POSTGRES_PORT','5432')}/{os.getenv('POSTGRES_DB','visionforge')}"
    )
config.set_main_option("sqlalchemy.url", database_url)

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
