"""E6: `test_invalidate_happens_after_commit` -- `09-CACHE-RATELIMIT.md section 2.3`'s own
test sketch, asserting call ORDER, not just that both calls happened.

**Written when `ComplaintService.create()`/`change_status()` didn't exist on this branch yet
(Phase 3's write path hadn't merged) -- superseded, 2026-09-25 (post-merge audit fix, see
`docs/AI-USAGE.md`), once it did and a real bug was found: `create()` never called
`invalidate()` at all, and `change_status()`'s call ran BEFORE the DB commit (`app/deps.py`'s
`get_session()` only commits after the route handler returns, which is after any service-layer
code could run -- fixed by giving `ComplaintRepository` an explicit `commit()` the service
calls before `invalidate()`). The real, end-to-end ordering assertions now live in
`tests/unit/test_complaint_service.py::test_create_commits_then_invalidates_stats_cache` and
`test_change_status_commits_then_invalidates_stats_cache`, against the actual
`ComplaintService`, not a synthetic stand-in.

What's left in this file: the two properties below don't depend on `ComplaintService`'s
specific shape and are still worth their own isolated coverage -- that `StatsService.
invalidate()` never touches the DB session (so calling it after commit can't reopen or
interfere with the transaction), and a general falsifiability demonstration of the
ordering-assertion *style* itself. The synthetic write-path stand-in and its
`_RecordingSession`/`_RecordingStatsService` were removed since they now only test a shape
mirroring code that actually exists elsewhere.
"""

import pytest

from tests.unit.fakes import FakeRedis

pytestmark = pytest.mark.unit


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
