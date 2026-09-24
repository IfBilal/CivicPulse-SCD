"""Shared Postgres fixture — `05-DATA-LAYER.md §8`: testcontainers, never SQLite. SQLite has no
native enums, no `gen_random_uuid()`, no `timestamptz`; a green SQLite suite here would be a
false signal against a system that only ever runs on real Postgres.

Isolation strategy: one container for the whole session (cheap to boot once, expensive per
test), migrated once, then `TRUNCATE ... RESTART IDENTITY` before every test. Simpler and more
obviously correct than a savepoint-rollback scheme, and it still isolates tests that call
`session.commit()` internally (e.g. the seed idempotency tests), since truncation runs before
the next test even starts.
"""

import os
from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.integration

_BACKEND_ROOT = __file__.rsplit("/backend/", 1)[0] + "/backend"


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine") as pg:
        # testcontainers gives a psycopg2 URL; the app + Alembic both use psycopg3.
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        yield url


@pytest.fixture(scope="session")
def migrated_db(postgres_url: str) -> Iterator[str]:
    """`alembic upgrade head` against the live container, once per test session.

    `alembic/env.py` reads its URL from `app.settings.settings.database_url` by design, not
    from this Config object — `set_main_option("sqlalchemy.url", ...)` here only affects what
    `alembic.ini` would have supplied, which `env.py` overwrites unconditionally. The container
    URL has to reach it via `DATABASE_URL`.
    """
    os.environ["DATABASE_URL"] = postgres_url
    cfg = Config(f"{_BACKEND_ROOT}/alembic.ini")
    cfg.set_main_option("script_location", f"{_BACKEND_ROOT}/alembic")
    command.upgrade(cfg, "head")
    yield postgres_url


@pytest_asyncio.fixture
async def db_session(migrated_db: str) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(migrated_db)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(text("TRUNCATE complaints RESTART IDENTITY CASCADE"))
        await session.commit()
        yield session
    await engine.dispose()
