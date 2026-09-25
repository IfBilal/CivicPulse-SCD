"""`06-BACKEND-CORE.md §3.3`: `allow_origins=["*"]` is never used."""

import pytest
from starlette.middleware.cors import CORSMiddleware

from app.main import create_app

pytestmark = pytest.mark.unit


def test_cors_wildcard_rejected() -> None:
    app = create_app()
    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    origins = cors.kwargs["allow_origins"]
    assert "*" not in origins


def test_cors_credentials_disabled() -> None:
    app = create_app()
    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    assert cors.kwargs["allow_credentials"] is False


def test_cors_exposes_cache_and_request_id_headers() -> None:
    app = create_app()
    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    exposed = cors.kwargs["expose_headers"]
    assert "X-Cache" in exposed
    assert "X-Request-ID" in exposed
    assert "Retry-After" in exposed
