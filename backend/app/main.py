"""App factory + lifespan. This file contains NO business logic and NO DDL
(`06-BACKEND-CORE.md §2`) — `alembic upgrade head` runs in `make up`/CI/the k8s initContainer,
deliberately never here."""

import asyncio
import time
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.db.session import engine
from app.errors import register_error_handlers
from app.logging_config import configure_logging
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.prometheus import PrometheusMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.providers.triage.factory import build_triage_provider
from app.routes import complaints, meta, ops, stats
from app.settings import settings

_REQUEST_ID_HEADER = {
    "description": "Echoed from the request, or generated (UUIDv4) if absent/invalid",
    "schema": {"type": "string", "format": "uuid"},
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings)
    app.state.ready = False
    app.state.started_at = time.monotonic()
    app.state.redis = Redis.from_url(
        str(settings.redis_url),
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
        health_check_interval=30,
    )
    app.state.triage = build_triage_provider(settings)
    app.state.ring = deque(maxlen=settings.triage_ring_size)
    app.state.ready = True
    yield
    app.state.ready = False  # (1) flip readiness FIRST — /ready starts returning 503
    await asyncio.sleep(settings.prestop_drain_s)  # (2) let in-flight requests drain
    await app.state.triage.aclose()
    await app.state.redis.aclose()  # type: ignore[attr-defined]  # types-redis stub lag; exists at runtime
    await engine.dispose()  # (3) close pool connections last


def register_middleware(app: FastAPI) -> None:
    """Registered outermost-first; Starlette runs them outermost-first on the way in,
    innermost-first on the way out (`06-BACKEND-CORE.md §3`). `add_middleware` prepends to the
    stack, so the LAST call here ends up OUTERMOST — register in reverse of the desired order."""
    app.add_middleware(RateLimitMiddleware, settings=settings)  # innermost
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.cors_allow_origins],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Cache", "X-Request-ID", "Retry-After"],
        max_age=600,
    )
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)  # outermost


def register_routers(app: FastAPI) -> None:
    for module in (complaints, stats, meta, ops):
        app.include_router(module.router)


def create_app() -> FastAPI:
    app = FastAPI(
        title="CivicPulse API",
        version=settings.version,
        lifespan=lifespan,
        # Relative, never absolute — an absolute URL smuggles an environment into the schema
        # and breaks build-once-deploy-many (ADR-0002, 04-CONTRACTS.md §6.10).
        servers=[{"url": "/"}],
    )
    register_error_handlers(app)
    register_middleware(app)
    register_routers(app)
    app.openapi = lambda: _contract_openapi(app)  # type: ignore[method-assign]
    return app


def _contract_openapi(app: FastAPI) -> dict[str, Any]:
    """FastAPI's schema, minus its phantom 422s, plus X-Request-ID on every response."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = FastAPI.openapi(app)
    for path_item in schema["paths"].values():
        for op in path_item.values():
            op["responses"].pop("422", None)
            for resp in op["responses"].values():
                resp.setdefault("headers", {})["X-Request-ID"] = _REQUEST_ID_HEADER
    for name in ("HTTPValidationError", "ValidationError"):
        schema.get("components", {}).get("schemas", {}).pop(name, None)
    app.openapi_schema = schema
    return schema


app = create_app()
