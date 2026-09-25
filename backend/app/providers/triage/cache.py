"""Content-hash cache — `08-AI-TRIAGE.md §6`. Lives under `providers/` (not `services/`) because
it wraps Redis, a third-party wire format, matching this codebase's layer discipline (`CLAUDE.md
§3`: `providers/` → httpx, redis, third-party wire).

Design points, each deliberate:
- Hash input is normalised `text` **and** `location` — same words, different street must produce
  different keys (priority context differs by neighbourhood).
- Normalisation is NFKC + casefold + whitespace-collapse **only**. Do NOT strip punctuation or
  stopwords: "water is coming" and "water is not coming" must not collide. Over-normalising a
  cache key is a correctness bug that looks like a performance win.
- `v1` prefix is a manual generation counter — bump it to invalidate every cached triage after a
  prompt change.
- The model string is in the key so a cached `llama-3.1-8b` verdict is never served as a
  `gemini-flash` verdict (which would make `triaged_by` lie).
- TTL 86400s (24h).
- Fallbacks (`rules:fallback`) are NEVER cached — caching a transient provider outage for 24h
  would freeze degraded service into a full day. Only successful primary results are cached.
"""

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel

from app.schemas.triage import TriageResult

_WHITESPACE_RE = re.compile(r"\s+")


def _normalise_for_key(s: str) -> str:
    nfkc = unicodedata.normalize("NFKC", s).casefold().strip()
    return _WHITESPACE_RE.sub(" ", nfkc)


def content_key(text: str, location: str, model: str) -> str:
    digest_input = f"{_normalise_for_key(text)}\x1f{_normalise_for_key(location)}"
    digest = hashlib.sha256(digest_input.encode()).hexdigest()
    return f"triage:v1:{model}:{digest}"


class CachedTriage(BaseModel):
    result: TriageResult
    triaged_by: str
    latency_ms: int
    cached_at: datetime


class TriageCache(Protocol):
    """Structural interface — Redis-backed and in-memory-fake implementations both satisfy this
    without inheriting from anything, matching `08-AI-TRIAGE.md §1`'s Protocol-over-inheritance
    lesson."""

    async def get(self, key: str) -> CachedTriage | None: ...

    async def set(
        self, key: str, result: TriageResult, triaged_by: str, latency_ms: int
    ) -> None: ...


class InMemoryTriageCache:
    """Dict-backed fake for unit tests. No network, no real TTL expiry beyond a simple
    wall-clock check — deterministic and fast, matching CLAUDE.md HARD rule 15."""

    def __init__(self, ttl_s: int = 86400) -> None:
        self._ttl_s = ttl_s
        self._store: dict[str, CachedTriage] = {}

    async def get(self, key: str) -> CachedTriage | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        age_s = (datetime.now(UTC) - entry.cached_at).total_seconds()
        if age_s > self._ttl_s:
            del self._store[key]
            return None
        return entry

    async def set(self, key: str, result: TriageResult, triaged_by: str, latency_ms: int) -> None:
        self._store[key] = CachedTriage(
            result=result,
            triaged_by=triaged_by,
            latency_ms=latency_ms,
            cached_at=datetime.now(UTC),
        )


class RedisTriageCache:
    """Real Redis-backed implementation. Only ever exercised by an integration test tagged
    `pytest.mark.integration` (needs a live Redis) — untestable in this sandbox (no Docker,
    same disclosed gap as every other integration test this session); unit tests use
    `InMemoryTriageCache` instead, never this class, per CLAUDE.md HARD rule 15."""

    def __init__(self, redis_client: "_RedisLike", ttl_s: int = 86400) -> None:
        self._redis = redis_client
        self._ttl_s = ttl_s

    async def get(self, key: str) -> CachedTriage | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return CachedTriage.model_validate_json(raw)

    async def set(self, key: str, result: TriageResult, triaged_by: str, latency_ms: int) -> None:
        entry = CachedTriage(
            result=result,
            triaged_by=triaged_by,
            latency_ms=latency_ms,
            cached_at=datetime.now(UTC),
        )
        await self._redis.set(key, entry.model_dump_json(), ex=self._ttl_s)


class _RedisLike(Protocol):
    """The minimal slice of `redis.asyncio.Redis`'s interface this module depends on — keeps the
    dependency structural rather than importing the real `redis` package's types into this
    module's public surface."""

    async def get(self, name: str) -> bytes | str | None: ...

    async def set(self, name: str, value: str, ex: int | None = None) -> object: ...
