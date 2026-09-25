"""Dependency injection — `06-BACKEND-CORE.md §4`. Routes depend on services only; never on
`AsyncSession` directly (CLAUDE.md §3, `make lint-layers` greps routes for `session`)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.providers.triage.base import TriageProvider
from app.repositories.complaint_repo import ComplaintRepository
from app.services.complaint_service import ComplaintService
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService


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
    triage_service = TriageService(primary=triage, ring=getattr(request.app.state, "ring", None))
    stats_service = StatsService(repo)
    return ComplaintService(repo=repo, triage=triage_service, stats=stats_service)


def get_stats_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StatsService:
    return StatsService(ComplaintRepository(session))
