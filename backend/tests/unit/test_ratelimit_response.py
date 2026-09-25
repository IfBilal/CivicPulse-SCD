"""`rate_limited_response()` shape tests -- `09-CACHE-RATELIMIT.md section 4.2`. E10 body
shape, against the real `ErrorEnvelope`/`error_response()` helper already in this
codebase (`app/errors.py`)."""

import json

import pytest
from starlette.requests import Request

from app.middleware.ratelimit import rate_limited_response

pytestmark = pytest.mark.unit


def _make_request() -> Request:
    scope = {
        "type": "http",
        "headers": [],
        "client": ("10.0.0.1", 1234),
        "method": "POST",
        "path": "/api/complaints",
        "query_string": b"",
    }
    return Request(scope)


def test_response_status_and_headers() -> None:
    resp = rate_limited_response(
        _make_request(), limit=10, window_s=60, retry_after_s=37, now=1757830823.0
    )
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "37"
    assert resp.headers["X-RateLimit-Limit"] == "10"
    assert resp.headers["X-RateLimit-Remaining"] == "0"
    # now + retry_after, an epoch timestamp -- not the same value as Retry-After itself.
    assert resp.headers["X-RateLimit-Reset"] == str(1757830823 + 37)


def test_response_body_shape_matches_error_envelope() -> None:
    resp = rate_limited_response(_make_request(), limit=10, window_s=60, retry_after_s=5)
    body = json.loads(bytes(resp.body))
    assert body["error"]["code"] == "rate_limited"
    assert body["error"]["details"] == {
        "limit": 10,
        "window_seconds": 60,
        "retry_after_seconds": 5,
    }
    assert "request_id" in body["error"]


def test_retry_after_clamped_to_at_least_one() -> None:
    """A `Retry-After: 0` invites an immediate retry -- must never happen even if the
    underlying TTL read as 0."""
    resp = rate_limited_response(_make_request(), limit=10, window_s=60, retry_after_s=0)
    assert resp.headers["Retry-After"] == "1"


def test_retry_after_negative_ttl_still_clamped() -> None:
    resp = rate_limited_response(_make_request(), limit=10, window_s=60, retry_after_s=-3)
    assert resp.headers["Retry-After"] == "1"
