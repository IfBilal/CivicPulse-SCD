from fastapi import APIRouter, Request

from app.domain.limits import RECENT_TRIAGE_MAX
from app.schemas.meta import CacheStats, ProvidersOut, TriageOutcome
from app.settings import settings

router = APIRouter(tags=["meta"])


@router.get("/api/meta/providers", operation_id="get_providers", response_model=ProvidersOut)
async def get_providers(request: Request) -> ProvidersOut:
    ring = list(getattr(request.app.state, "ring", []))[-RECENT_TRIAGE_MAX:]
    # `hits`/`misses`/`hit_rate` are still an honest zero, not a fabricated rate — flagged in
    # the post-merge audit (2026-09-25, docs/AI-USAGE.md) as stale-but-not-trivial: the real
    # counters live on `TriageService.cache_hits`/`cache_misses` (Phase 5), but a fresh
    # `TriageService` is constructed per-request in `app/deps.py::get_complaint_service()` —
    # there is no app-lifetime instance this route can read from, the same "per-request vs.
    # app-lifetime" problem `app.state.ring` already solves for the outcome ring, not yet
    # applied here. `08-AI-TRIAGE.md §6` actually specifies reading these via
    # `REGISTRY.get_sample_value` against real Prometheus counters (shared with `/metrics`) —
    # neither `TriageService` nor this route currently emits Prometheus counters for cache
    # hits/misses, so that's the real fix, not a one-line swap. Left as a genuine gap, not
    # silently claimed fixed.
    cache = CacheStats(hits=0, misses=0, hit_rate=0.0)
    return ProvidersOut(
        active=request.app.state.triage.name,
        configured=settings.triage_provider,
        available=["llm", "ollama", "rules", "simulated"],
        cache=cache,
        recent=[TriageOutcome(**entry) for entry in reversed(ring)],
    )
