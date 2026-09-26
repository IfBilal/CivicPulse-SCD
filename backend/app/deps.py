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


def get_redis(request: Request) -> Redis:  # type: ignore[type-arg]
    # Unsubscripted everywhere in this file, deliberately: `redis.asyncio.client.Redis` isn't
    # actually `Generic` at runtime (only accepts `Redis[str]`-style subscripts under a
    # `TYPE_CHECKING`-only stub). A quoted `"Redis[str]"` annotation worked under
    # fastapi==0.115.*'s signature resolution, but fastapi>=0.130 evaluates string annotations
    # for real — for BOTH parameter and return annotations (`inspect.signature(...,
    # eval_str=True)`) — and `Redis[str]` raises `TypeError: ... is not a generic class` the
    # moment it's actually evaluated. Found while bumping fastapi/starlette for a CVE fix; the
    # `type: ignore[type-arg]` here and at every other `Redis` annotation in this file is mypy
    # strictness genuinely conflicting with a runtime constraint, not a shortcut (docs/AI-USAGE.md,
    # 2026-09-26).
    redis: Redis = request.app.state.redis  # type: ignore[type-arg]
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
    redis: Annotated[Redis, Depends(get_redis)],  # type: ignore[type-arg]
) -> StatsService:
    return StatsService(
        cast("_CacheRedis", redis),
        ComplaintRepository(session),
        cache_key=settings.stats_cache_key,
        ttl_s=settings.stats_cache_ttl_s,
    )
