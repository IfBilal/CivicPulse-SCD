from fastapi import APIRouter, Request

from app.domain.limits import RECENT_TRIAGE_MAX
from app.schemas.meta import ProvidersOut, TriageOutcome
from app.services.triage_service import cache_stats
from app.settings import settings

router = APIRouter(tags=["meta"])


@router.get("/api/meta/providers", operation_id="get_providers", response_model=ProvidersOut)
async def get_providers(request: Request) -> ProvidersOut:
    ring = list(getattr(request.app.state, "ring", []))[-RECENT_TRIAGE_MAX:]
    cache = cache_stats()
    return ProvidersOut(
        active=request.app.state.triage.name,
        configured=settings.triage_provider,
        available=["llm", "ollama", "rules", "simulated"],
        cache=cache,
        recent=[TriageOutcome(**entry) for entry in reversed(ring)],
    )
