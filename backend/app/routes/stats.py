from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.deps import get_stats_service
from app.schemas.stats import StatsOut
from app.services.stats_service import StatsService

router = APIRouter(tags=["stats"])

_STATS_HEADERS = {
    "X-Cache": {"schema": {"type": "string", "enum": ["HIT", "MISS"]}},
    "Cache-Control": {"schema": {"type": "string"}},
}


@router.get(
    "/api/stats",
    operation_id="get_stats",
    response_model=StatsOut,
    responses={200: {"headers": _STATS_HEADERS}},
)
async def get_stats(
    response: Response, svc: Annotated[StatsService, Depends(get_stats_service)]
) -> StatsOut:
    payload, hit, age = await svc.get()
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    return payload.model_copy(update={"cache_age_seconds": age})
