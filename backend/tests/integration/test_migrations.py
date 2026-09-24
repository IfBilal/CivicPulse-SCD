"""D1, D2 — `05-DATA-LAYER.md §8`. Runs against its own container, separate from `db_session`,
because these tests need to upgrade/downgrade/upgrade the schema itself."""

import pytest
from sqlalchemy import create_engine
from testcontainers.postgres import PostgresContainer

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from app.db.base import Base
from app.db.models import Complaint  # noqa: F401 - registers the table on Base.metadata

pytestmark = pytest.mark.integration

_BACKEND_ROOT = __file__.rsplit("/backend/", 1)[0] + "/backend"


def _alembic_config(url: str) -> Config:
    cfg = Config(f"{_BACKEND_ROOT}/alembic.ini")
    cfg.set_main_option("script_location", f"{_BACKEND_ROOT}/alembic")
    cfg.set_main_option("sqlalchemy.url", url)
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
