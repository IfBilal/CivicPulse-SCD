"""Middleware order is a contract — `06-BACKEND-CORE.md §3`:
RequestID (outermost) -> AccessLog -> Prometheus -> CORS -> RateLimit (innermost)."""

import pytest
from starlette.middleware.cors import CORSMiddleware

from app.main import create_app
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.prometheus import PrometheusMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware

pytestmark = pytest.mark.unit

_EXPECTED_OUTERMOST_FIRST = [
    RequestIDMiddleware,
    AccessLogMiddleware,
    PrometheusMiddleware,
    CORSMiddleware,
    RateLimitMiddleware,
]


def test_middleware_registered_in_contractual_order() -> None:
    app = create_app()
    # Starlette's `app.user_middleware` lists middleware OUTERMOST-first — the same order
    # requests are dispatched through on the way in.
    actual = [m.cls for m in app.user_middleware]
    assert actual == _EXPECTED_OUTERMOST_FIRST


def test_request_id_is_outermost_so_a_429_still_carries_it() -> None:
    """06-BACKEND-CORE.md §3: 'If the rate limiter rejects at 429, that response still needs
    X-Request-ID.' Proves the ordering has a real, observable effect rather than being
    decorative — RateLimitMiddleware is innermost, so RequestIDMiddleware wraps it and sets
    the header regardless of what an inner middleware does.

    Uses both REAL middleware classes stacked on a minimal Starlette app (not the full
    `create_app()`), with `RateLimitMiddleware` given an injected `RateLimiter(FakeRedis())`
    at `ratelimit_requests=0` so it deterministically rejects the first request — no real
    Redis reachable in this sandbox, and going through the full FastAPI app would also hit
    `TriageService`'s own real-Redis cache lookup deeper in the request (a second, unrelated
    failure point this test isn't about). This still proves the actual ordering claim: two
    real middleware instances, wired in the real outermost/innermost relationship, and the
    429 that RateLimitMiddleware itself produces still carries the header RequestIDMiddleware
    set on the way in."""
    import asyncio

    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from app.middleware.rate_limit import RateLimitMiddleware
    from app.middleware.request_id import RequestIDMiddleware
    from app.providers.ratelimit.limiter import RateLimiter
    from app.settings import settings as real_settings
    from tests.unit.fakes import FakeRedis

    async def _endpoint(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True}, status_code=201)

    settings = real_settings.model_copy(update={"ratelimit_enabled": True, "ratelimit_requests": 0})
    starlette_app = Starlette(routes=[])
    rate_limited = RateLimitMiddleware(starlette_app, settings, limiter=RateLimiter(FakeRedis()))
    outer = RequestIDMiddleware(rate_limited)  # RequestID wraps RateLimit, per the real order

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/complaints",
        "headers": [],
        "client": ("1.2.3.4", 12345),
        "app": starlette_app,
    }
    request = Request(scope)
    response = asyncio.run(outer.dispatch(request, lambda r: rate_limited.dispatch(r, _endpoint)))

    assert response.status_code == 429
    assert "X-Request-ID" in response.headers
    # Not just "a" request id — THE SAME one RequestIDMiddleware set on request.state, proving
    # the ordering effect specifically. `app/errors.py::request_id_of()` falls back to minting
    # its own fresh UUID if `request.state.request_id` was never set (e.g. if RequestID were
    # innermost instead of outermost) — that fallback alone would already satisfy an "X-Request-
    # ID is present" assertion without proving anything about ordering, which is why this
    # checks equality against the value the middleware itself observed, not just presence.
    assert response.headers["X-Request-ID"] == request.state.request_id
