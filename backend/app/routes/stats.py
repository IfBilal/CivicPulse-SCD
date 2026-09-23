from fastapi import APIRouter

from app.schemas.stats import StatsOut

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
async def get_stats() -> StatsOut:
    raise NotImplementedError
