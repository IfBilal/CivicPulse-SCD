"""`06-BACKEND-CORE.md §3`: RateLimitMiddleware is scoped to `POST /api/complaints` only.
GET requests, and requests when disabled, are never limited."""

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.deps import get_complaint_service
from app.main import create_app

pytestmark = pytest.mark.unit

VALID = {"text": "burst water main on Street 12", "location": "G-9/1, Islamabad"}


class _FakeComplaintService:
    async def create(self, *, text: str, location: str, contact: str | None):
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.domain.enums import Category, Priority, Status, TriagedBy

        class _Row:
            pass

        row = _Row()
        row.id = uuid4()
        row.text = text
        row.location = location
        row.reporter_contact = contact
        row.category = Category.WATER
        row.priority = Priority.NORMAL
        row.status = Status.OPEN
        row.ai_summary = "s"
        row.triaged_by = TriagedBy.SIMULATED
        row.triage_latency_ms = 1
        row.triage_confidence = 0.9
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)
        return row

    async def list(self, **kwargs):
        return [], 0


def _app_with_settings(**overrides) -> "TestClient":
    original = main_module.settings
    main_module.settings = original.model_copy(update=overrides)
    try:
        app = create_app()
    finally:
        main_module.settings = original
    app.dependency_overrides[get_complaint_service] = lambda: _FakeComplaintService()
    return app


def test_over_limit_post_complaints_returns_429() -> None:
    app = _app_with_settings(ratelimit_enabled=True, ratelimit_requests=1, ratelimit_window_s=60)
    with TestClient(app) as client:
        first = client.post("/api/complaints", json=VALID)
        second = client.post("/api/complaints", json=VALID)
    assert first.status_code == 201
    assert second.status_code == 429
    assert "Retry-After" in second.headers


def test_get_complaints_is_never_rate_limited() -> None:
    """The limiter is scoped to POST /api/complaints only — GET on the same resource must not
    be throttled even with a limit of 0."""
    app = _app_with_settings(ratelimit_enabled=True, ratelimit_requests=0)
    with TestClient(app) as client:
        for _ in range(3):
            r = client.get("/api/complaints")
            assert r.status_code != 429


def test_disabled_rate_limit_never_returns_429() -> None:
    # limit=0 would normally reject the very first request — disabling the flag entirely must
    # skip the check regardless of the configured limit.
    app = _app_with_settings(ratelimit_enabled=False, ratelimit_requests=0)
    with TestClient(app) as client:
        r = client.post("/api/complaints", json=VALID)
    assert r.status_code == 201
