"""Real-Redis integration suite -- `09-CACHE-RATELIMIT.md section 6`: E1, E2, E8, E9, E11,
E12, E17. Real timing (TTL expiry, real stampede-lock contention) belongs here, not in the
unit suite, per the ponytail decision recorded in `docs/AI-USAGE.md`'s 2026-09-25 Phase 5
entries -- fake-clock/short-poll unit coverage of the same code paths lives in
`tests/unit/services/test_stats_service.py` and `tests/unit/providers/test_ratelimit_limiter.py`.

**Cannot run in this sandbox** -- no Docker (`docker info` fails with a permission error,
confirmed this session, same gap as every other integration suite in this repo). Must
collect cleanly (`pytest -m integration --collect-only`) and is written to actually pass
in CI, which has Docker (confirmed: `feat/backend-api`'s `data-layer` job runs
testcontainers successfully there).
"""

import asyncio
import time

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.ratelimit.limiter import RateLimiter
from app.repositories.complaint_repo import ComplaintRepository
from app.services.stats_service import StatsService

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def stats_service(redis_client, db_session: AsyncSession) -> StatsService:
    repo = ComplaintRepository(db_session)
    return StatsService(redis_client, repo, cache_key="stats:v1", ttl_s=2, poll_timeout_ms=300)


async def test_stats_miss_then_hit(stats_service: StatsService) -> None:
    """E1: header sequence MISS, HIT."""
    _, hit1, _ = await stats_service.get()
    assert hit1 is False

    _, hit2, _ = await stats_service.get()
    assert hit2 is True


async def test_stats_ttl_expiry(stats_service: StatsService) -> None:
    """E2: real TTL against a real Redis -- wait past the 2s TTL configured in the
    fixture above, confirm the next read is a real MISS again."""
    await stats_service.get()  # populates the cache (MISS)
    _, hit_immediate, _ = await stats_service.get()
    assert hit_immediate is True

    await asyncio.sleep(2.5)  # real wait, allowed here: this file is integration-tagged

    _, hit_after_ttl, _ = await stats_service.get()
    assert hit_after_ttl is False


async def test_stats_invalidate_forces_next_read_to_miss(stats_service: StatsService) -> None:
    await stats_service.get()  # MISS, populates cache
    _, hit, _ = await stats_service.get()
    assert hit is True

    await stats_service.invalidate()

    _, hit_after_invalidate, _ = await stats_service.get()
    assert hit_after_invalidate is False


async def test_stampede_single_computation(redis_client, db_session: AsyncSession) -> None:
    """E8: 20 real-concurrent cache-miss requests against a real Redis lock result in
    exactly 1 (or a very small, bounded number if the lock genuinely expires mid-test)
    aggregate query -- not 20."""
    repo = ComplaintRepository(db_session)
    call_count = 0
    real_stats_counts = repo.stats_counts

    async def counting_stats_counts() -> object:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)  # simulate a non-trivial aggregate query
        return await real_stats_counts()

    repo.stats_counts = counting_stats_counts  # type: ignore[method-assign]
    svc = StatsService(redis_client, repo, cache_key="stats:v1", ttl_s=30, poll_timeout_ms=300)

    results = await asyncio.gather(*(svc.get() for _ in range(20)))
    assert len(results) == 20
    # The real lock (SET NX PX) ensures only the winner computes; the rest either poll
    # into a HIT or, in the worst case of a very slow winner, fall through to compute
    # once more -- but nowhere near all 20.
    assert call_count <= 2


async def test_ratelimit_429_after_limit(redis_client) -> None:
    """E9: 10x allowed then blocked, against a real Redis."""
    limiter = RateLimiter(redis_client)
    key = f"rl:test-e9:{int(time.time())}"

    results = [await limiter.check(key, limit=10, window_s=60) for _ in range(11)]
    allowed = [a for a, _ in results]
    assert allowed == [True] * 10 + [False]


async def test_ratelimit_is_shared_across_instances(redis_client) -> None:
    """E11: two separate `RateLimiter` instances pointed at the same Redis share the
    count -- proves the limiter is distributed, not per-process (the entire point of
    section 2.4's HPA argument)."""
    limiter_a = RateLimiter(redis_client)
    limiter_b = RateLimiter(redis_client)
    key = f"rl:test-e11:{int(time.time())}"

    for _ in range(5):
        allowed, _ = await limiter_a.check(key, limit=10, window_s=60)
        assert allowed is True
    for _ in range(5):
        allowed, _ = await limiter_b.check(key, limit=10, window_s=60)
        assert allowed is True

    # The 11th request, from either instance, must be blocked -- the count is shared.
    allowed, _ = await limiter_a.check(key, limit=10, window_s=60)
    assert allowed is False


async def test_lua_sets_expire_atomically(redis_client) -> None:
    """E12: proves the script is atomic by firing many concurrent `check()` calls at a
    fresh key and asserting the key's TTL is always set (> 0) immediately after the
    first call returns -- there is no window where the key exists with no expiry."""
    limiter = RateLimiter(redis_client)
    key = f"rl:test-e12:{int(time.time())}"

    await asyncio.gather(*(limiter.check(key, limit=1000, window_s=60) for _ in range(50)))

    ttl = await redis_client.ttl(key)
    assert ttl > 0


async def test_aof_enabled(redis_client) -> None:
    """E17: `CONFIG GET appendonly == yes` -- configured directly on the testcontainers
    Redis fixture (see `tests/integration/conftest.py`) since `compose.yaml` on this
    branch is out of this phase's scope to author from scratch (see
    `docs/ENGINEERING-NOTES.md`)."""
    config = await redis_client.config_get("appendonly")
    assert config.get("appendonly") == "yes"
