"""`StatsService` unit tests against a fake Redis -- never a real Redis connection here
(CLAUDE.md HARD rule 15). Covers the test matrix in `09-CACHE-RATELIMIT.md section 6`:
E3, E4/E5 (invalidation call sites -- see test_invalidate.py), E6, E7, E8.
"""

import asyncio
import datetime
from unittest.mock import AsyncMock

import pytest

from app.domain.enums import Category, Priority, Status
from app.schemas.stats import StatsOut
from app.services.stats_service import StatsService
from tests.unit.fakes import FakeClock, FakeRedis

pytestmark = pytest.mark.unit


def _fake_repo(total: int = 5) -> AsyncMock:
    repo = AsyncMock()
    repo.stats_counts.return_value = (
        total,
        dict.fromkeys(Category, 0),
        dict.fromkeys(Priority, 0),
        dict.fromkeys(Status, 0),
    )
    return repo


async def test_stats_miss_then_hit() -> None:
    """E1 equivalent at unit level: first call computes (MISS), second reads Redis (HIT)."""
    redis = FakeRedis()
    repo = _fake_repo()
    svc = StatsService(redis, repo, cache_key="stats:v1", ttl_s=30)

    _, hit1, age1 = await svc.get()
    assert hit1 is False
    assert age1 == 0
    repo.stats_counts.assert_awaited_once()

    _, hit2, age2 = await svc.get()
    assert hit2 is True
    assert age2 >= 0
    # Still only called once -- the second call was served from cache, not recomputed.
    repo.stats_counts.assert_awaited_once()


async def test_cache_age_seconds() -> None:
    """E3: 0 on MISS, ~elapsed on HIT."""
    clock = FakeClock()
    redis = FakeRedis(_now_fn=clock.time)
    repo = _fake_repo()
    svc = StatsService(redis, repo, cache_key="stats:v1", ttl_s=30, now_fn=clock.time)

    _, _, age_miss = await svc.get()
    assert age_miss == 0

    clock.advance(12)
    payload, hit, age_hit = await svc.get()
    assert hit is True
    assert age_hit == pytest.approx(12, abs=1)


async def test_stats_ttl_expiry_unit_level() -> None:
    """Fake-clock equivalent of E2 (real TTL timing belongs in the Redis-testcontainers
    suite per the ponytail decision in AI-USAGE.md) -- advancing past the TTL causes a
    real recompute, not a stale hit."""
    clock = FakeClock()
    redis = FakeRedis(_now_fn=clock.time)
    repo = _fake_repo()
    svc = StatsService(redis, repo, cache_key="stats:v1", ttl_s=30)

    await svc.get()
    clock.advance(31)
    _, hit, _ = await svc.get()
    assert hit is False
    assert repo.stats_counts.await_count == 2


async def test_stats_degrades_to_miss_when_redis_down() -> None:
    """E7: Redis GET/SETEX both fail -> still returns a valid payload as a MISS, never
    raises past this boundary."""
    redis = FakeRedis(fail_on={"get", "setex", "set"})
    repo = _fake_repo()
    svc = StatsService(redis, repo, cache_key="stats:v1", ttl_s=30)

    payload, hit, age = await svc.get()
    assert isinstance(payload, StatsOut)
    assert hit is False
    assert age == 0
    repo.stats_counts.assert_awaited_once()


async def test_invalidate_swallows_redis_errors() -> None:
    """section 3's table: DEL failure -> log WARNING, continue -- never raises."""
    redis = FakeRedis(fail_on={"delete"})
    repo = _fake_repo()
    svc = StatsService(redis, repo, cache_key="stats:v1", ttl_s=30)

    await svc.invalidate()  # must not raise


async def test_invalidate_calls_delete_on_the_configured_key() -> None:
    redis = FakeRedis()
    await redis.setex("stats:v1", 30, "{}")
    repo = _fake_repo()
    svc = StatsService(redis, repo, cache_key="stats:v1", ttl_s=30)

    await svc.invalidate()
    assert await redis.get("stats:v1") is None


async def test_stampede_single_computation() -> None:
    """E8, unit-scoped: N concurrent cache-miss requests result in exactly 1 aggregate
    query, using a short test-scoped poll interval (ponytail decision, AI-USAGE.md) so
    this runs in well under a second of real wall time. Full real-lock timing is
    reserved for the Redis-testcontainers suite."""
    redis = FakeRedis()
    repo = _fake_repo()
    # Make the repo query slow enough that concurrent callers really do race for the
    # lock, but the poll interval is still tiny (milliseconds), not 300ms real time.
    real_stats_counts = repo.stats_counts

    async def slow_stats_counts() -> object:
        await asyncio.sleep(0.05)
        return await real_stats_counts()

    repo.stats_counts = slow_stats_counts  # type: ignore[method-assign]
    svc = StatsService(
        redis,
        repo,
        cache_key="stats:v1",
        ttl_s=30,
        poll_timeout_ms=300,
        poll_interval_ms=5,
    )

    results = await asyncio.gather(*(svc.get() for _ in range(20)))
    hits = sum(1 for _, is_hit, _ in results if is_hit)
    misses = sum(1 for _, is_hit, _ in results if not is_hit)
    assert hits + misses == 20
    # Confirms this would fail without the lock: without stampede protection every
    # concurrent miss would call stats_counts, i.e. 20 calls, not close to 1.
    assert real_stats_counts.await_count <= 2  # winner + at worst one fallback-through


async def test_stampede_lock_loser_polls_then_hits() -> None:
    """Directly exercises the poll-then-read path: pre-seed the lock so `get()` treats
    itself as the loser, populate the key mid-poll, and confirm it's read as a HIT
    without ever calling the repository."""
    redis = FakeRedis()
    await redis.set("lock:stats", "1", nx=True, px=3000)  # someone else holds the lock
    repo = _fake_repo()
    svc = StatsService(
        redis, repo, cache_key="stats:v1", ttl_s=30, poll_timeout_ms=100, poll_interval_ms=5
    )

    async def fill_soon() -> None:
        await asyncio.sleep(0.01)
        payload = StatsOut(
            total=1,
            by_category=dict.fromkeys(Category, 0),
            by_priority=dict.fromkeys(Priority, 0),
            by_status=dict.fromkeys(Status, 0),
            generated_at=datetime.datetime.now(datetime.UTC),
            cache_age_seconds=0,
        )
        await redis.setex("stats:v1", 30, payload.model_dump_json())

    filler = asyncio.create_task(fill_soon())
    _, hit, age = await svc.get()
    await filler
    assert hit is True
    assert age == 0
    repo.stats_counts.assert_not_awaited()


async def test_stampede_lock_loser_falls_through_after_timeout() -> None:
    """If the poll times out with the key still empty, fall through to computing anyway
    -- never block a citizen on a lock (section 2.4)."""
    redis = FakeRedis()
    await redis.set("lock:stats", "1", nx=True, px=3000)  # lock never released in-test
    repo = _fake_repo()
    svc = StatsService(
        redis, repo, cache_key="stats:v1", ttl_s=30, poll_timeout_ms=20, poll_interval_ms=5
    )

    _, hit, _ = await svc.get()
    assert hit is False
    repo.stats_counts.assert_awaited_once()
