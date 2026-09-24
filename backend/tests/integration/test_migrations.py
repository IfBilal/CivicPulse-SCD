"""D1, D2 — `05-DATA-LAYER.md §8`. Each test runs against its own dedicated container (not the
shared `postgres_url` from `conftest.py`) because both tests do destructive schema operations
(`downgrade base`, a diff against a fresh `upgrade head`) that would corrupt `db_session`'s
migrated-once assumption if run against the shared container.

`alembic/env.py` reads its connection URL from `app.settings.settings.database_url` by design
(`05-DATA-LAYER.md §3.1`). `settings` is a module-level singleton, instantiated once at
whichever import happens first in the pytest process — setting the `DATABASE_URL` env var here
is too late, since pytest already imported every collected test module (including ones that
transitively import `app.settings`) during collection. Mutate the singleton directly instead.
"""

import pytest
from sqlalchemy import create_engine
from testcontainers.postgres import PostgresContainer

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from app.db.base import Base
from app.db.models import Complaint  # noqa: F401 - registers the table on Base.metadata
from app.settings import settings

pytestmark = pytest.mark.integration

_BACKEND_ROOT = __file__.rsplit("/backend/", 1)[0] + "/backend"


def _alembic_config(url: str) -> Config:
    settings.database_url = url
    cfg = Config(f"{_BACKEND_ROOT}/alembic.ini")
    cfg.set_main_option("script_location", f"{_BACKEND_ROOT}/alembic")
    return cfg


def test_migration_round_trip() -> None:
    """D1: upgrade head -> downgrade base -> upgrade head, clean both ways (DROP TYPE included).
    Regressed by leaving out any `DROP TYPE` in `downgrade()` — the second `upgrade` would then
    fail with 'type "category_enum" already exists'."""
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        cfg = _alembic_config(url)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")  # must not raise


def test_autogenerate_is_empty() -> None:
    """D2: the hand-written migration and the ORM model agree completely. Any drift here means
    `models.py` and `0001_initial.py` were edited independently and disagree."""
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        cfg = _alembic_config(url)
        command.upgrade(cfg, "head")

        sync_url = url
        engine = create_engine(sync_url)
        with engine.connect() as connection:
            ctx = MigrationContext.configure(connection)
            diff = compare_metadata(ctx, Base.metadata)
        engine.dispose()

        assert diff == [], f"model/migration drift detected: {diff}"
