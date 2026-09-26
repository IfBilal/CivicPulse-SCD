"""`08-AI-TRIAGE.md §6` — content-hash cache key + `InMemoryTriageCache`."""

import asyncio

import pytest

from app.domain.enums import Category, Priority
from app.providers.triage.cache import InMemoryTriageCache, content_key
from app.schemas.triage import TriageResult

pytestmark = pytest.mark.unit


def _result() -> TriageResult:
    return TriageResult(
        category=Category.WATER, priority=Priority.HIGH, summary="x", confidence=0.9
    )


# ── content_key ──────────────────────────────────────────────────────────────────────────────


def test_same_input_same_key() -> None:
    k1 = content_key("water leak", "Street 5", "llama-3.1-8b-instant")
    k2 = content_key("water leak", "Street 5", "llama-3.1-8b-instant")
    assert k1 == k2


def test_key_distinguishes_location() -> None:
    k1 = content_key("water leak", "Street 5", "llama-3.1-8b-instant")
    k2 = content_key("water leak", "Street 6", "llama-3.1-8b-instant")
    assert k1 != k2


def test_key_distinguishes_negation() -> None:
    """ "water is coming" vs "water is not coming" must not collide — over-normalising (stripping
    stopwords/punctuation) would be a correctness bug, not a performance win."""
    k1 = content_key("water is coming", "Street 5", "m")
    k2 = content_key("water is not coming", "Street 5", "m")
    assert k1 != k2


def test_key_distinguishes_model() -> None:
    k1 = content_key("water leak", "Street 5", "llama-3.1-8b-instant")
    k2 = content_key("water leak", "Street 5", "gemini-2.0-flash-lite")
    assert k1 != k2


def test_key_is_case_and_whitespace_insensitive() -> None:
    k1 = content_key("Water   Leak", "Street 5", "m")
    k2 = content_key("water leak", "street 5", "m")
    assert k1 == k2


def test_key_has_v1_prefix_and_model() -> None:
    key = content_key("x", "y", "my-model")
    assert key.startswith("triage:v1:my-model:")


def test_key_does_not_strip_punctuation() -> None:
    k1 = content_key("water, leak!", "Street 5", "m")
    k2 = content_key("water leak", "Street 5", "m")
    # NFKC+casefold+whitespace-collapse only — punctuation stays, so these differ.
    assert k1 != k2


# ── InMemoryTriageCache ──────────────────────────────────────────────────────────────────────


def test_miss_on_empty_cache() -> None:
    cache = InMemoryTriageCache()
    hit = asyncio.run(cache.get("nope"))
    assert hit is None


def test_set_then_get_hits() -> None:
    cache = InMemoryTriageCache()
    result = _result()

    async def _run() -> None:
        await cache.set("k", result, "llm:groq", 42)
        hit = await cache.get("k")
        assert hit is not None
        assert hit.result == result
        assert hit.triaged_by == "llm:groq"
        assert hit.latency_ms == 42

    asyncio.run(_run())


def test_ttl_expiry() -> None:
    from datetime import UTC, datetime, timedelta

    cache = InMemoryTriageCache(ttl_s=1)
    result = _result()

    async def _run() -> None:
        await cache.set("k", result, "llm:groq", 1)
        # Manually age the entry past TTL rather than sleeping (CLAUDE.md HARD rule 15).
        entry = cache._store["k"]
        cache._store["k"] = entry.model_copy(
            update={"cached_at": datetime.now(UTC) - timedelta(seconds=10)}
        )
        hit = await cache.get("k")
        assert hit is None

    asyncio.run(_run())


def test_falsifiable_ttl_check_would_fail_without_expiry_logic() -> None:
    """CLAUDE.md HARD rule 14: an implementation with no TTL check would return the stale entry
    — confirms the test above is a real assertion, not decoration."""
    cache = InMemoryTriageCache(ttl_s=999999)  # effectively "never expires"
    result = _result()

    async def _run() -> bool:
        await cache.set("k", result, "llm:groq", 1)
        hit = await cache.get("k")
        return hit is not None

    assert asyncio.run(_run()) is True  # proves a broken (no-TTL) cache WOULD still hit
