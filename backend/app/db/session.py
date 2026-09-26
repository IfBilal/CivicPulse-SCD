"""Async engine + session factory — `05-DATA-LAYER.md §1`.

Pool arithmetic: pool_size + max_overflow per pod, times max HPA replicas, must stay under
Postgres's max_connections. Defaults here (10+5=15) assume the §1 note's fix #1 — revisit
together before Phase 7's load test if maxReplicas grows past 6.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_s,
    pool_pre_ping=True,  # survives a Postgres restart / k8s pod delete without a 500
    pool_recycle=1800,
    echo=False,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:  # wired to DI in Phase 3
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_connection() -> None:
    """`SELECT 1` — used only by `/ready` (`06-BACKEND-CORE.md §5`). Lives here, not in
    `routes/ops.py`, so `make lint-layers`'s "no SQL under routes/" grep stays meaningful."""
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
