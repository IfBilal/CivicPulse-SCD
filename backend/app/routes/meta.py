from fastapi import APIRouter, Request

from app.domain.limits import RECENT_TRIAGE_MAX
from app.schemas.meta import CacheStats, ProvidersOut, TriageOutcome
from app.settings import settings

router = APIRouter(tags=["meta"])


@router.get("/api/meta/providers", operation_id="get_providers", response_model=ProvidersOut)
async def get_providers(request: Request) -> ProvidersOut:
    ring = list(getattr(request.app.state, "ring", []))[-RECENT_TRIAGE_MAX:]
    # Redis triage cache (hits/misses) is Phase 5 scope (09-CACHE-RATELIMIT.md) — no counters
    # exist yet to read, so this reports the honest zero state rather than fabricating a rate.
    cache = CacheStats(hits=0, misses=0, hit_rate=0.0)
    return ProvidersOut(
        active=request.app.state.triage.name,
        configured=settings.triage_provider,
        available=["rules", "simulated"],
        cache=cache,
        recent=[TriageOutcome(**entry) for entry in reversed(ring)],
    )
