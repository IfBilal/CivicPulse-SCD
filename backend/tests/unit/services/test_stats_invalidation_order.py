"""E6: `test_invalidate_happens_after_commit` -- `09-CACHE-RATELIMIT.md section 2.3`'s own
test sketch, asserting call ORDER, not just that both calls happened.

**Deferred wiring, disclosed:** `ComplaintService.create()`/`change_status()` do not exist
on this branch yet -- Phase 3's write path (`feat/backend-api`) hasn't merged. There is no
real "commit-then-invalidate" call site to test end-to-end yet. What this test proves
instead: `StatsService.invalidate()` is a `DEL`-only operation entirely decoupled from the
DB session, so whichever branch adds `ComplaintService` can safely call
`session.commit()` then `await stats_service.invalidate()` in that literal order without
`invalidate()` itself doing anything commit-adjacent that could race. The ordering
assertion is written against a minimal stand-in write-path function
(`_create_complaint_then_invalidate`) that mirrors the exact two-step shape
`ComplaintService.create()` will have, so the test is falsifiable: reversing the two
lines below turns it red.
"""

import pytest

from tests.unit.fakes import FakeRedis

pytestmark = pytest.mark.unit


class _RecordingSession:
    """Stand-in for the real `AsyncSession` -- records when `commit()` is called."""

    def __init__(self, seen: list[str]) -> None:
        self._seen = seen

    async def commit(self) -> None:
        self._seen.append("commit")


class _RecordingStatsService:
    """Stand-in for `StatsService` -- records when `invalidate()` is called, without a
    real Redis round trip."""

    def __init__(self, seen: list[str]) -> None:
        self._seen = seen

    async def invalidate(self) -> None:
        self._seen.append("del")


async def _create_complaint_then_invalidate(
    session: _RecordingSession, stats: _RecordingStatsService
) -> None:
    """Mirrors the exact shape `ComplaintService.create()` must have per section 2.3:
    COMMIT, then DEL -- never the reverse, and never DEL inside the transaction."""
    await session.commit()
    await stats.invalidate()


async def test_invalidate_happens_after_commit() -> None:
    seen: list[str] = []
    session = _RecordingSession(seen)
    stats = _RecordingStatsService(seen)

    await _create_complaint_then_invalidate(session, stats)

    assert seen.index("commit") < seen.index("del")


async def test_invalidate_reversed_order_is_detected_as_wrong() -> None:
    """Falsifiability check (CLAUDE.md HARD rule 14): confirms the ordering assertion
    above would actually fail if a future `ComplaintService` got the order backwards."""
    seen: list[str] = []
    session = _RecordingSession(seen)
    stats = _RecordingStatsService(seen)

    # Deliberately wrong order, to prove the assertion style catches it.
    await stats.invalidate()
    await session.commit()

    with pytest.raises(AssertionError):
        assert seen.index("commit") < seen.index("del")


async def test_invalidate_is_del_only_no_side_effect_on_session() -> None:
    """`StatsService.invalidate()` touches only Redis -- it never touches the DB session,
    so calling it after `commit()` cannot reopen or interfere with the transaction."""
    redis = FakeRedis()
    from app.repositories.complaint_repo import ComplaintRepository
    from app.services.stats_service import StatsService

    svc = StatsService(redis, repo=None, cache_key="stats:v1", ttl_s=30)  # type: ignore[arg-type]
    await redis.setex("stats:v1", 30, "{}")
    await svc.invalidate()
    assert await redis.get("stats:v1") is None
    _ = ComplaintRepository  # imported only to document the real repo type StatsService expects
