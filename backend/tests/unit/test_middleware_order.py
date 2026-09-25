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
    the header regardless of what an inner middleware does."""
    from fastapi.testclient import TestClient

    import app.main as main_module

    original = main_module.settings
    main_module.settings = original.model_copy(
        update={"ratelimit_enabled": True, "ratelimit_requests": 0}
    )
    try:
        app = create_app()
    finally:
        main_module.settings = original

    client = TestClient(app)
    r = client.post("/api/complaints", json={"text": "x" * 20, "location": "somewhere"})
    assert r.status_code == 429
    assert "X-Request-ID" in r.headers
