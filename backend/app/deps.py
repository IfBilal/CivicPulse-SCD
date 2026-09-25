"""Dependency injection — `06-BACKEND-CORE.md §4`. Routes depend on services only; never on
`AsyncSession` directly (CLAUDE.md §3, `make lint-layers` greps routes for `session`)."""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Annotated, cast

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.providers.triage.base import TriageProvider
from app.providers.triage.cache import RedisTriageCache
from app.repositories.complaint_repo import ComplaintRepository
from app.services.complaint_service import ComplaintService
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService
from app.settings import settings

if TYPE_CHECKING:
    from app.services.stats_service import _CacheRedis


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_redis(request: Request) -> "Redis[str]":
    redis: Redis[str] = request.app.state.redis
    return redis


def get_triage(request: Request) -> TriageProvider:
    provider: TriageProvider = request.app.state.triage
    return provider


def get_complaint_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    triage: Annotated[TriageProvider, Depends(get_triage)],
    request: Request,
) -> ComplaintService:
    repo = ComplaintRepository(session)
    cache = RedisTriageCache(request.app.state.redis, ttl_s=settings.triage_cache_ttl_s)
    triage_service = TriageService(
        triage, cache, settings, ring=getattr(request.app.state, "ring", None)
    )
    # cast: `redis.asyncio.Redis`'s real `set()` has more keyword params (ex/xx/keepttl/...)
    # than `StatsService`'s narrow `_CacheRedis` Protocol declares, which mypy's structural
    # Protocol check rejects even though every actual call this service makes is safe — same
    # tension as `providers/triage/llm.py`'s `AsyncOpenAI` construction, same fix.
    stats_service = StatsService(
        cast("_CacheRedis", request.app.state.redis),
        repo,
        cache_key=settings.stats_cache_key,
        ttl_s=settings.stats_cache_ttl_s,
    )
    return ComplaintService(repo=repo, triage=triage_service, stats=stats_service)


def get_stats_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated["Redis[str]", Depends(get_redis)],
) -> StatsService:
    return StatsService(
        cast("_CacheRedis", redis),
        ComplaintRepository(session),
        cache_key=settings.stats_cache_key,
        ttl_s=settings.stats_cache_ttl_s,
    )
