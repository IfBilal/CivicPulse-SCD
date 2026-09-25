"""In-memory fakes for the exact subset of `redis.asyncio.Redis` this codebase's cache
and rate-limit code actually calls -- same pattern as Phase 4's `InMemoryTriageCache`,
not a mock of the whole `redis` library. Never a real Redis connection here (CLAUDE.md
HARD rule 15) -- that's what `tests/integration/test_cache_ratelimit.py` is for.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class FakeRedis:
    """Minimal GET/SETEX/SET-NX-PX/DELETE/EVALSHA/SCRIPT-LOAD store with real per-key TTL
    expiry driven off an injectable clock, so tests can fast-forward time without
    `time.sleep()`."""

    _store: dict[str, str] = field(default_factory=dict)
    _expires_at: dict[str, float] = field(default_factory=dict)
    _now_fn: callable[[], float] = field(default=time.time)
    fail_on: set[str] = field(default_factory=set)  # method names to raise on
    calls: list[str] = field(default_factory=list)

    def _now(self) -> float:
        return self._now_fn()

    def _expire_if_due(self, key: str) -> None:
        exp = self._expires_at.get(key)
        if exp is not None and self._now() >= exp:
            self._store.pop(key, None)
            self._expires_at.pop(key, None)

    async def get(self, name: str) -> str | None:
        self.calls.append("get")
        if "get" in self.fail_on:
            raise ConnectionError("simulated redis outage")
        self._expire_if_due(name)
        return self._store.get(name)

    async def setex(self, name: str, time: int, value: str) -> bool:
        self.calls.append("setex")
        if "setex" in self.fail_on:
            raise ConnectionError("simulated redis outage")
        self._store[name] = value
        self._expires_at[name] = self._now() + time
        return True

    async def set(self, name: str, value: str, nx: bool = False, px: int | None = None) -> bool:
        self.calls.append("set")
        if "set" in self.fail_on:
            raise ConnectionError("simulated redis outage")
        self._expire_if_due(name)
        if nx and name in self._store:
            return False
        self._store[name] = value
        if px is not None:
            self._expires_at[name] = self._now() + px / 1000
        return True

    async def delete(self, *names: str) -> int:
        self.calls.append("delete")
        if "delete" in self.fail_on:
            raise ConnectionError("simulated redis outage")
        n = 0
        for name in names:
            if name in self._store:
                del self._store[name]
                self._expires_at.pop(name, None)
                n += 1
        return n

    # -- rate-limiter Lua-script surface -----------------------------------------
    async def script_load(self, script: str) -> str:
        self.calls.append("script_load")
        return "fakesha-" + str(hash(script))

    async def evalsha(self, sha: str, numkeys: int, *keys_and_args: str) -> list[int]:
        """Emulates `fixed_window.lua` atomically: INCR, EXPIRE-if-first, return [n, ttl]."""
        self.calls.append("evalsha")
        if "evalsha" in self.fail_on:
            raise ConnectionError("simulated redis outage")
        key = keys_and_args[0]
        limit_s, window_s = keys_and_args[1], keys_and_args[2]
        window = int(window_s)
        self._expire_if_due(key)
        current = int(self._store.get(key, "0"))
        current += 1
        self._store[key] = str(current)
        if current == 1:
            self._expires_at[key] = self._now() + window
        exp = self._expires_at.get(key, self._now() + window)
        ttl = max(0, int(exp - self._now()))
        _ = limit_s
        return [current, ttl]


class FakeClock:
    """A mutable wall clock for tests -- avoids real `time.sleep()` (CLAUDE.md HARD rule
    15). Pass `.time` as `FakeRedis(_now_fn=clock.time)`."""

    def __init__(self, start: float | None = None) -> None:
        self._t = start if start is not None else time.time()

    def time(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds
