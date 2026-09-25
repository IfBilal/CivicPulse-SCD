"""Read-through cache for `GET /api/stats` -- `09-CACHE-RATELIMIT.md section 2`.

`X-Cache` semantics, stated precisely (section 2.1, `docs/ENGINEERING-NOTES.md` has the
same text): `HIT` = this response body was read from Redis, not recomputed -- including
the stampede-lock-wait-then-read case. `MISS` = this request executed the aggregate
query. Redis failures degrade to a miss/best-effort per the table in section 3 -- never
a 500 (CLAUDE.md HARD rule 5's sibling rule for the cache path).

**Wiring status, updated at the Phase 5 merge into `dev` (2026-09-25):** written when
`app/routes/stats.py` was still a Phase 1 stub and `ComplaintService` didn't exist on this
branch (Phase 3, `feat/backend-api`, hadn't merged yet) -- both now exist in `dev`. This
service was complete and unit-tested against a fake Redis client from the start; whether
the real route sets `X-Cache`/`Cache-Control` from it and whether `ComplaintService` calls
`invalidate()` after a write commit are `app/deps.py`/route-layer wiring questions, not
this file's own scope -- check those call sites directly rather than trusting this
docstring's history.
"""

import asyncio
import datetime
import logging
import time
from collections.abc import Callable
from typing import Any, Protocol, cast

from app.repositories.complaint_repo import ComplaintRepository
from app.schemas.stats import StatsOut

logger = logging.getLogger(__name__)

_LOCK_KEY = "lock:stats"
_LOCK_TTL_MS = 3000
_DEFAULT_POLL_TIMEOUT_MS = 300
_DEFAULT_POLL_INTERVAL_MS = 20


class _CacheRedis(Protocol):
    """The minimal subset of `redis.asyncio.Redis` this service calls -- lets tests
    supply an in-memory fake instead of mocking the whole `redis` library, same pattern
    as Phase 4's `InMemoryTriageCache`. Return types are `Any`, not the real client's
    precise unions -- `_safe_get` casts back to `str | bytes | None` at its one call site.

    The real `redis.asyncio.Redis.set()` has more keyword params than this Protocol
    declares (`ex`/`xx`/`keepttl`/...), which mypy's structural check on Protocol methods
    rejects even though every actual call this service makes (`get(key)`,
    `setex(key, ttl, json_str)`, `set(key, "1", nx=True, px=ms)`, `delete(key)`) is safe.
    Callers construct this service with `cast("_CacheRedis", real_client)`
    (`app/deps.py`) rather than this Protocol trying to structurally match the full real
    signature -- same tension and same fix as `providers/triage/llm.py`'s `AsyncOpenAI`
    construction."""

    async def get(self, name: str) -> Any: ...
    async def setex(self, name: str, time: int, value: str) -> Any: ...
    async def set(self, name: str, value: str, nx: bool = False, px: int | None = None) -> Any: ...
    async def delete(self, *names: str) -> Any: ...


_WARN_INTERVAL_S = 60


class StatsService:
    def __init__(
        self,
        redis_client: _CacheRedis,
        repo: ComplaintRepository,
        *,
        cache_key: str = "stats:v1",
        ttl_s: int = 30,
        poll_timeout_ms: int = _DEFAULT_POLL_TIMEOUT_MS,
        poll_interval_ms: int = _DEFAULT_POLL_INTERVAL_MS,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self._redis = redis_client
        self._repo = repo
        self._key = cache_key
        self._ttl_s = ttl_s
        self._poll_timeout_ms = poll_timeout_ms
        self._poll_interval_ms = poll_interval_ms
        self._now_fn = now_fn
        self._last_get_warning_at: float = 0.0

    async def get(self) -> tuple[StatsOut, bool, int]:
        """Returns `(payload, is_hit, cache_age_seconds)`."""
        raw = await self._safe_get()
        if raw is not None:
            payload = StatsOut.model_validate_json(raw)
            age = self._age_of(payload)
            return payload, True, age

        acquired = await self._safe_acquire_lock()
        if not acquired:
            # Someone else is computing. Poll briefly, then fall through -- never block
            # a citizen on a lock (section 2.4).
            filled = await self._await_fill()
            if filled is not None:
                payload = StatsOut.model_validate_json(filled)
                return payload, True, 0

        payload = await self._compute()
        await self._safe_setex(payload.model_dump_json())
        return payload, False, 0

    async def invalidate(self) -> None:
        """`DEL stats:v1` -- call AFTER commit, never before (section 2.3): invalidating
        inside the transaction lets a concurrent read repopulate the cache with
        pre-commit data, which then lives a full TTL. Swallows Redis errors (section 3's
        table: DEL failure -> log WARNING, continue -- this is precisely the
        lost-invalidation case the TTL exists to bound)."""
        try:
            await self._redis.delete(self._key)
        except Exception:
            logger.warning("stats cache invalidation failed; TTL will bound staleness")

    def _age_of(self, payload: StatsOut) -> int:
        return int(self._now_fn() - payload.generated_at.timestamp())

    async def _compute(self) -> StatsOut:
        total, by_category, by_priority, by_status = await self._repo.stats_counts()
        return StatsOut(
            total=total,
            by_category=by_category,
            by_priority=by_priority,
            by_status=by_status,
            generated_at=datetime.datetime.fromtimestamp(self._now_fn(), tz=datetime.UTC),
            cache_age_seconds=0,
        )

    async def _safe_get(self) -> str | bytes | None:
        try:
            # cast: `_CacheRedis.get` returns `Any` (the Protocol is deliberately loose so
            # both the real redis-py client and test fakes satisfy it structurally -- see
            # the class docstring); the real runtime contract for `GET` on a string key is
            # `str | bytes | None`, which this cast makes explicit at the one call site.
            return cast("str | bytes | None", await self._redis.get(self._key))
        except Exception:
            # section 3's table: log WARNING once per 60s, not once per call -- a
            # sustained outage would otherwise spam the log once per poll iteration too
            # (the stampede-lock-loser path calls _safe_get in a tight loop).
            now = self._now_fn()
            if now - self._last_get_warning_at >= _WARN_INTERVAL_S:
                logger.warning("stats cache GET failed; degrading to miss")
                self._last_get_warning_at = now
            return None

    async def _safe_setex(self, payload_json: str) -> None:
        try:
            await self._redis.setex(self._key, self._ttl_s, payload_json)
        except Exception:
            logger.warning("stats cache SETEX failed; serving computed payload anyway")

    async def _safe_acquire_lock(self) -> bool:
        try:
            result = await self._redis.set(_LOCK_KEY, "1", nx=True, px=_LOCK_TTL_MS)
            return bool(result)
        except Exception:
            logger.warning("stats stampede lock acquisition failed; computing directly")
            # Redis is unavailable for the lock too -- just compute; the GET above
            # already established Redis is unreachable, so this is consistent with
            # "degrade to a cache miss."
            return True

    async def _await_fill(self) -> str | bytes | None:
        elapsed_ms = 0
        while elapsed_ms < self._poll_timeout_ms:
            await asyncio.sleep(self._poll_interval_ms / 1000)
            elapsed_ms += self._poll_interval_ms
            raw = await self._safe_get()
            if raw is not None:
                return raw
        return None
