"""`TriageService` — the fallback ladder, `08-AI-TRIAGE.md §5`, nearly verbatim.

Order, every call:
1. Cache check (content-hash key). Hit → return immediately, `cached=True`, no provider call.
2. Miss → loop up to `triage_max_retries + 1` attempts (default 1 → at most 2 attempts), each
   wrapped in `asyncio.timeout` against a shared deadline (`triage_total_budget_ms`).
3. Success → post-validate (enum/length/confidence-floor already enforced by `TriageResult`
   construction + the `triage_min_confidence` downgrade), cache it, record metrics, return.
4. Exception classified NON_RETRYABLE (validation/malformed JSON/400-shaped) → break
   immediately, straight to fallback, zero retries (`08-AI-TRIAGE.md §2.5` item 3 / CLAUDE.md
   HARD rule 6 — "never retry a validation failure").
5. Exception classified RETRYABLE (timeout/connect/429-shaped/5xx-shaped) → sleep a jittered
   delay and retry if attempts and time remain, else fall through to fallback.
6. Fallback: `RuleBasedTriage` (cannot raise), `triaged_by="rules:fallback"`, exactly ONE
   WARNING log line (not one per attempt), never cached.

CLAUDE.md HARD rule 5: a triage-provider failure must never become a 500. Every exception this
module can encounter is caught somewhere on the way to the fallback branch — nothing raises past
this class.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic, perf_counter
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.domain.enums import Category, Priority, TriagedBy
from app.providers.triage.base import TriageProvider
from app.providers.triage.cache import TriageCache, content_key
from app.providers.triage.llm import LLMValidationError
from app.providers.triage.ollama import OllamaValidationError
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import (
    SimulatedMalformedResponseError,
    SimulatedRateLimitError,
    SimulatedServerError,
    SimulatedValidationError,
)
from app.schemas.triage import TriageResult

log = logging.getLogger("app.triage")

# Exceptions that mean "try again, the world may have changed": network hiccups, rate limits,
# server-side 5xx. Retrying these is the whole point of the ladder.
RETRYABLE: tuple[type[BaseException], ...] = (
    TimeoutError,  # covers asyncio.TimeoutError / asyncio.timeout's cancellation-derived error
    httpx.TimeoutException,
    httpx.ConnectError,
    SimulatedRateLimitError,  # SimulatedTriage's 429-shaped failure mode
    SimulatedServerError,  # SimulatedTriage's 5xx-shaped failure mode
)

# Exceptions that mean "the request or the response shape was wrong, and will be wrong again":
# schema validation failures, malformed JSON, 4xx-except-429. Retrying these burns budget on a
# deterministic re-failure — CLAUDE.md HARD rule 6.
NON_RETRYABLE: tuple[type[BaseException], ...] = (
    ValidationError,
    LLMValidationError,
    OllamaValidationError,
    SimulatedMalformedResponseError,
    SimulatedValidationError,
    ValueError,  # includes json.JSONDecodeError
)


@dataclass(frozen=True, slots=True)
class TriageOutcome:
    result: TriageResult
    triaged_by: str
    latency_ms: int
    cached: bool


def _is_retryable_http_status(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or 500 <= status < 600
    return False


def classify(exc: BaseException) -> str:
    """Returns "retryable" or "non_retryable". HTTPStatusError and the OpenAI SDK's
    APIStatusError family both need their status code inspected (429/5xx retryable, other 4xx
    not), so neither can live in a plain isinstance tuple.

    `openai.APIStatusError` is checked separately from `RETRYABLE`/`NON_RETRYABLE` because the
    SDK raises distinct concrete subclasses per status family (`RateLimitError` for 429,
    `InternalServerError` for 5xx, `BadRequestError` for 400) that all share `APIStatusError` as
    a base with `.response.status_code` — confirmed against a real Groq call during this
    session: an injection-shaped prompt triggers a live, reproducible `BadRequestError` (400,
    `json_validate_failed`) from Groq's own JSON-mode enforcement, before any content reaches
    `LLMTriage`. That's a genuine NON_RETRYABLE case this classifier must recognise by type, not
    fall into by accident via the unclassified-default branch below (docs/TRIAGE.md, "Failure
    log" section, has the full reproduction)."""
    from openai import APIStatusError as OpenAIAPIStatusError  # local: see module docstring

    if isinstance(exc, OpenAIAPIStatusError):
        status = exc.response.status_code
        return "retryable" if (status == 429 or 500 <= status < 600) else "non_retryable"
    if isinstance(exc, httpx.HTTPStatusError):
        return "retryable" if _is_retryable_http_status(exc) else "non_retryable"
    if isinstance(exc, RETRYABLE):
        return "retryable"
    if isinstance(exc, NON_RETRYABLE):
        return "non_retryable"
    # Anything unclassified (e.g. SimulatedTriage's bare RuntimeError for FailureMode.RAISE, or
    # a genuinely unexpected provider bug) is treated as non-retryable: retrying an unknown
    # failure mode risks burning the whole budget on something that will just fail again, and
    # CLAUDE.md HARD rule 5 requires we reach fallback regardless — non-retryable gets there in
    # one hop instead of two.
    return "non_retryable"


class TriageService:
    def __init__(
        self,
        primary: TriageProvider,
        cache: TriageCache,
        settings: object,
        *,
        fallback: TriageProvider | None = None,
        ring: list[dict[str, object]] | None = None,
    ) -> None:
        self._primary = primary
        self._cache = cache
        self._s = settings
        self._fallback: TriageProvider = fallback or RuleBasedTriage()
        self._cache_hits = 0
        self._cache_misses = 0
        # `ring`, if given, is a shared list living on `app.state` — a fresh TriageService is
        # constructed per request by FastAPI's DI (`app/deps.py`), so an instance-owned ring
        # would reset every request and `/api/meta/providers`' "last 20 outcomes" would never
        # accumulate past one entry. Recording into the caller's own list instead of a private
        # one is what makes the ring survive across requests; every unit test that constructs
        # `TriageService` without a `ring` keeps its original per-instance behavior unchanged.
        self._ring: list[dict[str, object]] = ring if ring is not None else []

    @property
    def cache_hits(self) -> int:
        return self._cache_hits

    @property
    def cache_misses(self) -> int:
        return self._cache_misses

    @property
    def recent(self) -> list[dict[str, object]]:
        """Newest first, capped at `triage_ring_size`."""
        return list(reversed(self._ring[-self._ring_size() :]))

    def _ring_size(self) -> int:
        return int(getattr(self._s, "triage_ring_size", 20))

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - monotonic()
        return max(remaining, 0.001)  # asyncio.timeout requires a positive delay

    def _postvalidate(self, raw: TriageResult) -> TriageResult:
        """Sixth, softer guardrail layer (`08-AI-TRIAGE.md §4.2`): a result below
        `triage_min_confidence` is downgraded to OTHER/NORMAL rather than trusted outright. The
        enum/length constraints are already enforced by `TriageResult`'s own validation at
        construction time, so nothing further to check there."""
        min_confidence = float(getattr(self._s, "triage_min_confidence", 0.35))
        if raw.confidence < min_confidence:
            return TriageResult(
                category=Category.OTHER,
                priority=Priority.NORMAL,
                summary=raw.summary,
                confidence=raw.confidence,
            )
        return raw

    def _record(
        self,
        *,
        complaint_id: UUID | None,
        provider: str,
        latency_ms: int,
        fallback: bool,
        cached: bool,
        error_class: str | None,
    ) -> None:
        entry: dict[str, object] = {
            "complaint_id": complaint_id,
            "provider": provider,
            "latency_ms": latency_ms,
            "fallback": fallback,
            "cached": cached,
            "error_class": error_class,
            "at": datetime.now(UTC),
        }
        self._ring.append(entry)
        max_len = self._ring_size() * 4  # bound memory; `recent` still only ever returns last N
        if len(self._ring) > max_len:
            # In-place trim (slice-assign, not `self._ring = ...[slice]`): when `ring` was
            # passed in by the caller (see __init__), reassigning the attribute would detach
            # this instance from the shared list — a later request's fresh TriageService,
            # constructed with the same `app.state.ring` object, would then record into the
            # untrimmed original while this instance kept trimming its own private copy.
            self._ring[:] = self._ring[-self._ring_size() :]

    async def triage_with_fallback(
        self, *, text: str, location: str, complaint_id: UUID | None = None
    ) -> TriageOutcome:
        # Key on the ACTIVE primary provider's identity, not unconditionally on `settings.
        # llm_model` — a cache keyed on the LLM model string even while running
        # TRIAGE_PROVIDER=simulated/rules would let those results collide with an unrelated
        # model's cached verdicts if the same cache backend were ever shared across provider
        # configurations. For `llm:*` providers this still resolves to `settings.llm_model`,
        # matching §6 exactly (a cached llama-3.1-8b verdict must not be served as gemini-flash).
        model = (
            getattr(self._s, "llm_model", self._primary.name)
            if self._primary.name.startswith("llm:")
            else self._primary.name
        )
        key = content_key(text, location, model)

        hit = await self._cache.get(key)
        if hit is not None:
            self._cache_hits += 1
            self._record(
                complaint_id=complaint_id,
                provider=hit.triaged_by,
                latency_ms=hit.latency_ms,
                fallback=hit.triaged_by == TriagedBy.RULES_FALLBACK,
                cached=True,
                error_class=None,
            )
            return TriageOutcome(
                result=hit.result,
                triaged_by=hit.triaged_by,
                latency_ms=hit.latency_ms,
                cached=True,
            )
        self._cache_misses += 1

        total_budget_s = float(getattr(self._s, "triage_total_budget_ms", 12000)) / 1000
        max_retries = int(getattr(self._s, "triage_max_retries", 1))
        jitter_ms = float(getattr(self._s, "triage_retry_jitter_ms", 250))
        per_attempt_timeout_s = float(getattr(self._s, "triage_timeout_s", 10))

        deadline = monotonic() + total_budget_s
        attempts = 0
        last_exc: BaseException | None = None

        while attempts <= max_retries:
            attempts += 1
            t0 = perf_counter()
            try:
                attempt_timeout = min(per_attempt_timeout_s, self._remaining(deadline))
                async with asyncio.timeout(attempt_timeout):
                    raw = await self._primary.triage(text=text, location=location)
                result = self._postvalidate(raw)
                ms = int((perf_counter() - t0) * 1000)
                await self._cache.set(key, result, self._primary.name, ms)
                self._record(
                    complaint_id=complaint_id,
                    provider=self._primary.name,
                    latency_ms=ms,
                    fallback=False,
                    cached=False,
                    error_class=None,
                )
                return TriageOutcome(
                    result=result, triaged_by=self._primary.name, latency_ms=ms, cached=False
                )
            except Exception as exc:  # the fallback boundary intentionally catches everything
                last_exc = exc
                verdict = classify(exc)
                if verdict == "non_retryable":
                    break
                # retryable
                if attempts > max_retries or monotonic() >= deadline:
                    break
                await asyncio.sleep(random.uniform(0, jitter_ms / 1000))  # noqa: S311 — jitter, not crypto

        # ── FALLBACK ─────────────────────────────────────────────────────────────────────
        t0 = perf_counter()
        result = await self._fallback.triage(text=text, location=location)  # cannot raise
        ms = int((perf_counter() - t0) * 1000)
        error_class = type(last_exc).__name__ if last_exc is not None else "unknown"
        log.warning(
            "triage.fallback",
            extra={
                "extra_fields": {
                    "provider": self._primary.name,
                    "error_class": error_class,
                    "attempts": attempts,
                    "elapsed_ms": ms,
                }
            },
        )
        self._record(
            complaint_id=complaint_id,
            provider=TriagedBy.RULES_FALLBACK,
            latency_ms=ms,
            fallback=True,
            cached=False,
            error_class=error_class,
        )
        return TriageOutcome(
            result=result, triaged_by=TriagedBy.RULES_FALLBACK, latency_ms=ms, cached=False
        )
