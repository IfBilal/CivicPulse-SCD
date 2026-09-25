"""Shared Postgres fixture — `05-DATA-LAYER.md §8`: testcontainers, never SQLite. SQLite has no
native enums, no `gen_random_uuid()`, no `timestamptz`; a green SQLite suite here would be a
false signal against a system that only ever runs on real Postgres.

Isolation strategy: one container for the whole session (cheap to boot once, expensive per
test), migrated once, then `TRUNCATE ... RESTART IDENTITY` before every test. Simpler and more
obviously correct than a savepoint-rollback scheme, and it still isolates tests that call
`session.commit()` internally (e.g. the seed idempotency tests), since truncation runs before
the next test even starts.
"""

from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
import redis.asyncio as redis_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

import app.settings as settings_module
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
    from this Config object. Setting the `DATABASE_URL` env var alone is not enough: `settings`
    is a module-level singleton (`app/settings.py`), instantiated once at whichever import
    happens first — and pytest imports every collected test module (including ones that
    transitively import `app.settings`, e.g. via `app.cli.seed`) during collection, before any
    fixture runs. By the time this fixture executes, the singleton may already hold the
    fallback default.

    `Settings` is `frozen=True` (Phase 3, `06-BACKEND-CORE.md §1` — no module may mutate config
    after boot, which is what makes `/api/meta/providers.configured` trustworthy), so this can
    no longer assign a field on the existing instance. Instead it swaps the `app.settings`
    module's `settings` attribute for a `model_copy()` carrying the container's URL.
    `alembic/env.py` does `from app.settings import settings` and reads `settings.database_url`
    at import time, so it picks up whatever object that module attribute points to at the
    moment `command.upgrade()` below triggers that import — a fresh frozen instance works
    exactly as well as a mutated one would have.
    """
    settings_module.settings = settings_module.settings.model_copy(
        update={"database_url": postgres_url}
    )
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


# ── Redis — mirrors the Postgres fixture pattern above exactly: one container for the
# whole session, a fresh client per test, `FLUSHDB` before each test instead of a fresh
# container (cheap to boot once, expensive per test — same rationale as the Postgres
# TRUNCATE-before-each-test strategy). AOF is enabled here directly (rather than only via
# `compose.yaml`) so E17 (`test_aof_enabled`) is meaningful even if `compose.yaml` isn't
# on this branch — see `docs/ENGINEERING-NOTES.md`.
@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer("redis:7.4.1-alpine") as rc:
        rc.get_client().config_set("appendonly", "yes")
        host = rc.get_container_host_ip()
        port = rc.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest_asyncio.fixture
async def redis_client(redis_url: str) -> AsyncGenerator[redis_asyncio.Redis, None]:
    client = redis_asyncio.Redis.from_url(redis_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()
