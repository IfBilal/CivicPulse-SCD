"""CLAUDE.md §4: "the fallback test is the single most important test in the codebase — write
it first in its file." A provider that always raises must still produce a 201-shaped result
with `triaged_by == rules:fallback`, never an exception past the service boundary.

Written against Phase 3's original `TriageService(primary=...)`/`SimulatedTriage(mode=...)`
shapes; updated at the Phase 3 + Phase 4 merge (2026-09-25) to Phase 4's real constructors
(`TriageService(primary, cache, settings, ...)`, `SimulatedTriage(seed=, failure_mode=)`) —
same pattern as `tests/unit/providers/triage/test_factory.py`'s equivalent fix.
"""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.domain.enums import TriagedBy
from app.domain.errors import InvalidTransition, NotFound
from app.providers.triage.cache import InMemoryTriageCache
from app.providers.triage.simulated import FailureMode, SimulatedTriage
from app.services.complaint_service import ComplaintService
from app.services.triage_service import TriageService

pytestmark = pytest.mark.unit


@dataclass
class _TestSettings:
    """Minimal settings stand-in — same field set `tests/unit/services/test_triage_service.py`
    uses, short timeout/budget so nothing here waits real wall-clock time (CLAUDE.md HARD
    rule 15)."""

    triage_timeout_s: float = 0.2
    triage_total_budget_ms: int = 400
    triage_max_retries: int = 1
    triage_retry_jitter_ms: int = 250
    triage_cache_ttl_s: int = 86400
    triage_min_confidence: float = 0.0  # don't downgrade test fixtures' low-confidence output
    triage_ring_size: int = 20


def _triage_service(primary: object) -> TriageService:
    return TriageService(primary, InMemoryTriageCache(), _TestSettings())


class _FakeRepo:
    """In-memory stand-in for `ComplaintRepository` — enough surface for the service tests,
    with no SQLAlchemy/DB involved (CLAUDE.md HARD rule 15: no real network in a test)."""

    def __init__(self) -> None:
        self.rows: dict = {}
        self.created_kwargs: list[dict] = []

    async def create(self, **kwargs):
        self.created_kwargs.append(kwargs)
        row = _Row(**kwargs)
        self.rows[row.id] = row
        return row

    async def get(self, cid):
        return self.rows.get(cid)

    async def transition(self, cid, expected, new):
        row = self.rows.get(cid)
        if row is None or row.status != expected:
            return None
        row.status = new
        return row


class _Row:
    def __init__(self, **kwargs) -> None:
        self.id = uuid4()
        self.status = "open"
        for k, v in kwargs.items():
            setattr(self, k, v)


async def test_fallback_emits_201_shaped_result_when_primary_always_raises() -> None:
    """CLAUDE.md HARD rule 5: a provider failure must never raise past this boundary — the
    caller (the route) always gets back a valid row it can turn into a 201."""
    primary = SimulatedTriage(failure_mode=FailureMode.RAISE)
    triage_service = _triage_service(primary)
    repo = _FakeRepo()
    svc = ComplaintService(repo=repo, triage=triage_service)

    row = await svc.create(
        text="water leaking everywhere on street 5", location="G-9, Islamabad", contact=None
    )

    assert row.triaged_by == TriagedBy.RULES_FALLBACK
    assert repo.created_kwargs[0]["triaged_by"] == TriagedBy.RULES_FALLBACK


async def test_primary_success_is_not_marked_as_fallback() -> None:
    primary = SimulatedTriage(failure_mode=FailureMode.NONE)
    triage_service = _triage_service(primary)
    repo = _FakeRepo()
    svc = ComplaintService(repo=repo, triage=triage_service)

    row = await svc.create(text="minor pothole near the market", location="F-7", contact=None)

    assert row.triaged_by == TriagedBy.SIMULATED


async def test_malformed_provider_output_falls_back_without_retry() -> None:
    """`SimulatedTriage(failure_mode=MALFORMED)` raises at the provider boundary — proving the
    fallback boundary catches it and reaches `rules:fallback`, no exception escapes. The "zero
    retries" half of CLAUDE.md HARD rule 6 is proven directly by `classify()`'s
    `NON_RETRYABLE` classification in `tests/unit/services/test_triage_service.py`; this test
    asserts what this file can prove: exactly one provider invocation happened before falling
    back, at the `ComplaintService` boundary rather than the `TriageService` one."""
    calls = 0

    class _CountingMalformed(SimulatedTriage):
        name = "simulated"

        async def triage(self, *, text: str, location: str):
            nonlocal calls
            calls += 1
            return await super().triage(text=text, location=location)

    primary = _CountingMalformed(failure_mode=FailureMode.MALFORMED)
    triage_service = _triage_service(primary)
    repo = _FakeRepo()
    svc = ComplaintService(repo=repo, triage=triage_service)

    row = await svc.create(text="sewage overflow near the school", location="I-8", contact=None)

    assert row.triaged_by == TriagedBy.RULES_FALLBACK
    assert calls == 1  # zero retries — one call, straight to fallback


async def test_get_missing_complaint_raises_not_found() -> None:
    repo = _FakeRepo()
    svc = ComplaintService(repo=repo, triage=_triage_service(SimulatedTriage()))
    with pytest.raises(NotFound):
        await svc.get(uuid4())


async def test_change_status_disallowed_transition_raises_invalid_transition() -> None:
    repo = _FakeRepo()
    svc = ComplaintService(repo=repo, triage=_triage_service(SimulatedTriage()))
    row = await svc.create(text="broken streetlight pole 9", location="F-6", contact=None)
    row.status = "resolved"  # terminal — nothing is allowed from here

    with pytest.raises(InvalidTransition) as exc_info:
        await svc.change_status(row.id, "open")
    assert exc_info.value.src == "resolved"


async def test_change_status_lost_race_reports_actual_current_state() -> None:
    """`07-BACKEND-API.md §4`: when the conditional UPDATE loses the race, the 409 must name
    the ACTUAL current state, not the stale one the caller thought it had."""
    repo = _FakeRepo()
    svc = ComplaintService(repo=repo, triage=_triage_service(SimulatedTriage()))
    row = await svc.create(text="road has a big pothole near market", location="F-6", contact=None)

    # Simulate a concurrent transition: repo.get() still returns "open" the first time (the
    # service's initial read), but by the time transition() runs, someone else already moved
    # the row to "resolved" — the conditional UPDATE's WHERE clause won't match "open" anymore.
    original_get = repo.get
    call_count = 0

    async def racy_get(cid):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            row.status = "resolved"
        return await original_get(cid)

    async def racy_transition(cid, expected, new):
        return None  # always loses the race

    repo.get = racy_get
    repo.transition = racy_transition

    with pytest.raises(InvalidTransition) as exc_info:
        await svc.change_status(row.id, "in_progress")
    assert exc_info.value.src == "resolved"  # the ACTUAL state, not "open"
