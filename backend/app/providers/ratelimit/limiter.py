"""Distributed fixed-window rate limiter -- `09-CACHE-RATELIMIT.md section 4`.

Keyed by client IP, backed by one atomic Lua script (`lua/fixed_window.lua`) loaded via
`SCRIPT LOAD` and invoked with `EVALSHA` (the Redis atomic-script-execution primitive --
not the Python builtin). Never two Python-side round trips (`INCR` then `EXPIRE`) -- a
pod killed between them leaves a key with no TTL, permanently banning that IP under an
HPA that kills pods on every scale-down (section 4.1).

This module is `providers/` -- it only imports `redis`, nothing from `services/` or
`repositories/` (CLAUDE.md section 3, `lint-layers`).
"""

from pathlib import Path
from typing import Protocol

_LUA_PATH = Path(__file__).parent / "lua" / "fixed_window.lua"
FIXED_WINDOW_SCRIPT = _LUA_PATH.read_text()


class _ScriptCapableRedis(Protocol):
    """The minimal subset of `redis.asyncio.Redis` this class actually calls -- lets tests
    supply a fake instead of mocking the whole `redis` library."""

    async def script_load(self, script: str) -> str: ...
    async def evalsha(self, sha: str, numkeys: int, *keys_and_args: str) -> object: ...


class RateLimiter:
    """`check()` returns `(allowed, retry_after_seconds)`. `retry_after_seconds` is the
    key's remaining TTL, clamped to >= 1 (a `Retry-After: 0` invites an immediate retry)."""

    def __init__(self, redis_client: _ScriptCapableRedis) -> None:
        self._redis = redis_client
        self._sha: str | None = None

    async def _ensure_script_loaded(self) -> str:
        if self._sha is None:
            self._sha = await self._redis.script_load(FIXED_WINDOW_SCRIPT)
        return self._sha

    async def check(self, key: str, limit: int, window_s: int) -> tuple[bool, int]:
        """One atomic INCR+EXPIRE+TTL against `key`, run server-side via the loaded Redis
        script. Does NOT catch Redis errors -- the fail-open decision (section 4.5)
        belongs to the caller (middleware), which knows whether "Redis is down" should
        mean "allow the request"."""
        sha = await self._ensure_script_loaded()
        try:
            raw = await self._redis.evalsha(sha, 1, key, str(limit), str(window_s))
        except Exception:  # NOSCRIPT after a Redis restart flushed the script cache
            self._sha = None
            sha = await self._ensure_script_loaded()
            raw = await self._redis.evalsha(sha, 1, key, str(limit), str(window_s))
        pair = list(raw)  # type: ignore[call-overload]
        count_raw, ttl_raw = pair[0], pair[1]
        retry_after = max(1, int(ttl_raw))
        return int(count_raw) <= int(limit), retry_after
