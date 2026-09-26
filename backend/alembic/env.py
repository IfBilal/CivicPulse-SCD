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
    # `disable_existing_loggers` defaults to True in stdlib `fileConfig` — it walks every
    # logger that already exists at this moment (e.g. `app.triage`, `logging.getLogger("app.
    # triage")` at `triage_service.py` import time, long before this module runs) and sets
    # `.disabled = True` on any of them not explicitly named in alembic.ini's `[loggers]`
    # section. In-process (this module runs via `command.upgrade()`, called directly by
    # `tests/integration/conftest.py::migrated_db`, not a subprocess), that disables `app.
    # triage` for the rest of the test PROCESS — real root cause of a CI-only failure where
    # `tests/unit/services/test_triage_service.py`'s and `tests/unit/test_logging_config.py`'s
    # "exactly one WARNING" tests asserted 0 captured records only when the integration suite
    # (which needs real Docker/Postgres, unreproducible in a sandbox without it) ran alembic
    # migrations earlier in the same unfiltered `pytest` process (confirmed via a temporary
    # diagnostic printing `logging.getLogger("app.triage").disabled` — True — in CI; see
    # docs/AI-USAGE.md, 2026-09-26).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

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
