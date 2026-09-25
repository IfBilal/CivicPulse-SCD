"""Liveness, readiness, metrics. `/health` must never gain a DB dependency (00-SPEC §2.2) —
`test_health_module_imports` (tests/unit) AST-scans this module for forbidden imports, so don't
import anything from `app.db` or `app.providers` at module scope here, even transitively."""

import asyncio
import os
import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.domain.errors import NotReady
from app.routes._responses import errors
from app.schemas.health import HealthOut, ReadyOut

router = APIRouter(tags=["ops"])

_CHECK_TIMEOUT_S = 2.0


@router.get("/health", operation_id="health", response_model=HealthOut)
async def health(request: Request) -> HealthOut:
    return HealthOut(
        status="ok",
        version=request.app.version,
        pid=os.getpid(),
        uptime_seconds=int(time.monotonic() - request.app.state.started_at),
    )


@router.get("/ready", operation_id="ready", response_model=ReadyOut, responses=errors(503))
async def ready(request: Request) -> ReadyOut:
    # No try/except here (CLAUDE.md §3) — NotReady is raised and the registered handler in
    # app/errors.py is the only place that turns it into the 04-CONTRACTS.md §6.8 envelope.
    if not request.app.state.ready:
        checks = {"lifecycle": "shutting_down"}
        raise NotReady(checks=checks, failed=["lifecycle"])

    pg_result, redis_result = await asyncio.gather(
        _check_postgres(), _check_redis(request), return_exceptions=True
    )
    checks = {
        "postgres": "ok" if pg_result is None else f"error: {type(pg_result).__name__}",
        "redis": "ok" if redis_result is None else f"error: {type(redis_result).__name__}",
    }
    failed = [name for name, status in checks.items() if status != "ok"]
    if failed:
        raise NotReady(checks=checks, failed=failed)
    return ReadyOut(status="ok", checks=checks)


async def _check_postgres() -> None:
    from app.db import check_connection

    async with asyncio.timeout(_CHECK_TIMEOUT_S):
        await check_connection()


async def _check_redis(request: Request) -> None:
    async with asyncio.timeout(_CHECK_TIMEOUT_S):
        await request.app.state.redis.ping()


# Prometheus text format, not JSON — kept out of the typed client (04-CONTRACTS.md §6.9).
@router.get(
    "/metrics", operation_id="metrics", response_class=PlainTextResponse, include_in_schema=False
)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
