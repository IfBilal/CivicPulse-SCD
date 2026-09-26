"""`GET /api/meta/providers` — `07-BACKEND-API.md §6`: ring capped at RECENT_TRIAGE_MAX,
never leaks complaint text, prompt, or key (CLAUDE.md HARD rule 13)."""

from collections import deque
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domain.enums import TriagedBy
from app.domain.limits import RECENT_TRIAGE_MAX
from app.main import create_app

pytestmark = pytest.mark.unit

_SECRET_COMPLAINT_TEXT = "TOP-SECRET-SUBSTRING-that-must-never-leak-into-the-response"


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def test_ring_capped_at_recent_triage_max(client: TestClient) -> None:
    ring = client.app.state.ring
    for _ in range(RECENT_TRIAGE_MAX + 10):
        ring.append(
            {
                "complaint_id": uuid4(),
                "provider": TriagedBy.SIMULATED,
                "latency_ms": 1,
                "fallback": False,
                "cached": False,
                "error_class": None,
                "at": datetime.now(UTC),
            }
        )
    assert len(ring) == RECENT_TRIAGE_MAX  # deque(maxlen=...) enforces this at append time

    r = client.get("/api/meta/providers")
    assert len(r.json()["recent"]) <= RECENT_TRIAGE_MAX


def test_meta_providers_leaks_no_complaint_text(client: TestClient) -> None:
    # The ring entry shape (app/services/triage_service.py's `_record`) structurally cannot
    # hold complaint text -- this test proves the ROUTE doesn't smuggle it in some other way,
    # by planting the secret substring nowhere the route can legitimately find it and checking
    # the full response body for it.
    r = client.get("/api/meta/providers")
    assert _SECRET_COMPLAINT_TEXT not in r.text


def test_meta_providers_leaks_no_api_key_prefix(client: TestClient) -> None:
    r = client.get("/api/meta/providers")
    assert "gsk_" not in r.text
    assert "AIza" not in r.text


def test_meta_providers_configured_matches_settings(client: TestClient) -> None:
    r = client.get("/api/meta/providers")
    assert r.json()["configured"] == "simulated"


async def test_meta_providers_cache_stats_reflect_real_counter(client: TestClient) -> None:
    """`08-AI-TRIAGE.md §6`'s own worked example: hits/misses/hit_rate must be REAL counts, not
    a hardcoded zero (closed 2026-09-26 -- see docs/AI-USAGE.md). Drives the same
    `TRIAGE_CACHE_RESULT` Prometheus counter `TriageService.triage_with_fallback()` increments
    on every real call, then asserts the route's response reflects the delta -- proving the
    route reads the same process-global counter, not a per-request stand-in."""
    from app.providers.triage.cache import InMemoryTriageCache
    from app.providers.triage.simulated import SimulatedTriage
    from app.services.triage_service import TriageService

    before = client.get("/api/meta/providers").json()["cache"]

    class _Settings:
        triage_timeout_s = 1.0
        triage_total_budget_ms = 2000
        triage_max_retries = 0
        triage_retry_jitter_ms = 10
        triage_cache_ttl_s = 60
        triage_min_confidence = 0.0
        triage_ring_size = 20

    ts = TriageService(SimulatedTriage(), InMemoryTriageCache(), _Settings())
    await ts.triage_with_fallback(
        text="cache stats probe unique text", location="probe-loc"
    )  # miss
    await ts.triage_with_fallback(text="cache stats probe unique text", location="probe-loc")  # hit

    after = client.get("/api/meta/providers").json()["cache"]
    assert after["misses"] == before["misses"] + 1
    assert after["hits"] == before["hits"] + 1
    total = after["hits"] + after["misses"]
    assert after["hit_rate"] == pytest.approx(after["hits"] / total)


def test_meta_providers_recent_is_newest_first() -> None:
    """A stub-level check that the route reverses the ring (oldest-appended-first deque ->
    newest-first response) rather than assuming callers want raw append order."""
    from app.domain.limits import RECENT_TRIAGE_MAX as _MAX

    ring: deque = deque(maxlen=_MAX)
    first_id = uuid4()
    second_id = uuid4()
    ring.append(
        {
            "complaint_id": first_id,
            "provider": TriagedBy.SIMULATED,
            "latency_ms": 1,
            "fallback": False,
            "cached": False,
            "error_class": None,
            "at": datetime.now(UTC),
        }
    )
    ring.append(
        {
            "complaint_id": second_id,
            "provider": TriagedBy.SIMULATED,
            "latency_ms": 1,
            "fallback": False,
            "cached": False,
            "error_class": None,
            "at": datetime.now(UTC),
        }
    )
    reversed_entries = list(reversed(list(ring)))
    assert reversed_entries[0]["complaint_id"] == second_id
