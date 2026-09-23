"""Liveness, readiness, metrics. `/health` must never gain a DB dependency (00-SPEC §2.2)."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.routes._responses import errors
from app.schemas.health import HealthOut, ReadyOut

router = APIRouter(tags=["ops"])


@router.get("/health", operation_id="health", response_model=HealthOut)
async def health() -> HealthOut:
    raise NotImplementedError


@router.get("/ready", operation_id="ready", response_model=ReadyOut, responses=errors(503))
async def ready() -> ReadyOut:
    raise NotImplementedError


# Prometheus text format, not JSON — kept out of the typed client (04-CONTRACTS.md §6.9).
@router.get(
    "/metrics", operation_id="metrics", response_class=PlainTextResponse, include_in_schema=False
)
async def metrics() -> str:
    raise NotImplementedError
