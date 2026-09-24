"""`05-DATA-LAYER.md §3.1`. URL comes from `settings.database_url`, never `alembic.ini`, so the
same migration runs against compose, CI and Kubernetes with no file edits.

Uses a sync engine (psycopg3 supports both dialects under `postgresql+psycopg://`) so migrations
don't need an event loop — the app's own engine stays async, this one doesn't have to be.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.db.base import Base
from app.db.models import Complaint  # noqa: F401 - import registers the table on Base.metadata
from app.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """`make openapi`-style: writes SQL to stdout without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=False,  # Postgres doesn't need batch mode; that's a SQLite crutch
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
