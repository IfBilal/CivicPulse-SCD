"""Phase 3 slice of the triage orchestration boundary — CLAUDE.md HARD rule 5, the single
thing this assignment is testing: a provider failure must never become a 500.

The full timeout/retry/budget/cache machinery (`08-AI-TRIAGE.md`) is Phase 4 scope (see the
ponytail record in `docs/AI-USAGE.md`, 2026-09-25). What Phase 3 proves and this class
implements: **primary provider raises, for any reason -> caught here -> fall back to
`RuleBasedTriage` -> caller gets a valid `TriageOutcome`, never an exception.** Retry counting,
jittered backoff, the 12s total budget, and the Redis triage cache are added on top of this in
Phase 4 without changing this class's public shape (`ENGINEERING-NOTES.md` "Phase 3 —
SimulatedTriage's malformed mode" explains why no-retry-on-validation-failure isn't provable
here yet).
"""

import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.enums import TriagedBy
from app.providers.triage.base import TriageProvider
from app.providers.triage.rules import RuleBasedTriage
from app.schemas.triage import TriageResult

log = logging.getLogger(__name__)

# Maps a provider's `.name` to the TriagedBy value persisted on the row. Falls back to
# TriagedBy.RULES_FALLBACK for anything unrecognised, which should never happen in practice —
# the KeyError-shaped default keeps this function total rather than raising.
_PROVIDER_TO_TRIAGED_BY: dict[str, TriagedBy] = {
    "rules": TriagedBy.RULES,
    "simulated": TriagedBy.SIMULATED,
}


@dataclass(frozen=True, slots=True)
class TriageOutcome:
    result: TriageResult
    triaged_by: TriagedBy
    latency_ms: int
    fallback: bool
    cached: bool = False
    error_class: str | None = None


class TriageService:
    """Wraps a primary `TriageProvider` with a `RuleBasedTriage` fallback. `ring`, if given, is
    `app.state.ring` — a bounded deque of observability entries (CLAUDE.md HARD rule 13: no
    complaint text, no prompt, no key)."""

    def __init__(
        self,
        primary: TriageProvider,
        fallback: RuleBasedTriage | None = None,
        ring: Any = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback or RuleBasedTriage()
        self._ring = ring

    async def triage_with_fallback(
        self, *, complaint_id: UUID, text: str, location: str
    ) -> TriageOutcome:
        start = time.monotonic()
        try:
            result = await self._primary.triage(text=text, location=location)
        except Exception as exc:  # CLAUDE.md HARD rule 5: catch everything, fall back, never 500
            elapsed_ms = int((time.monotonic() - start) * 1000)
            fallback_result = await self._fallback.triage(text=text, location=location)
            # The ONE mandated WARNING per fallback (06-BACKEND-CORE.md §3.2) — exactly one,
            # never one per retry attempt (Phase 4 will add retries above this boundary).
            log.warning(
                "triage.fallback",
                extra={
                    "extra_fields": {
                        "complaint_id": str(complaint_id),
                        "provider": self._primary.name,
                        "error_class": type(exc).__name__,
                        "attempts": 1,
                        "elapsed_ms": elapsed_ms,
                        "fallback_to": "rules",
                    }
                },
            )
            self._record(
                complaint_id=complaint_id,
                provider=TriagedBy.RULES_FALLBACK,
                latency_ms=elapsed_ms,
                fallback=True,
                cached=False,
                error_class=type(exc).__name__,
            )
            return TriageOutcome(
                result=fallback_result,
                triaged_by=TriagedBy.RULES_FALLBACK,
                latency_ms=elapsed_ms,
                fallback=True,
                error_class=type(exc).__name__,
            )

        elapsed_ms = int((time.monotonic() - start) * 1000)
        triaged_by = _PROVIDER_TO_TRIAGED_BY.get(self._primary.name, TriagedBy.RULES_FALLBACK)
        self._record(
            complaint_id=complaint_id,
            provider=triaged_by,
            latency_ms=elapsed_ms,
            fallback=False,
            cached=False,
            error_class=None,
        )
        return TriageOutcome(
            result=result, triaged_by=triaged_by, latency_ms=elapsed_ms, fallback=False
        )

    def _record(
        self,
        *,
        complaint_id: UUID,
        provider: TriagedBy,
        latency_ms: int,
        fallback: bool,
        cached: bool,
        error_class: str | None,
    ) -> None:
        if self._ring is None:
            return
        from datetime import UTC, datetime

        # Ring entries carry exactly the fields CLAUDE.md HARD rule 13 allows — never
        # complaint text, a prompt, or a key.
        self._ring.append(
            {
                "complaint_id": complaint_id,
                "provider": provider,
                "latency_ms": latency_ms,
                "fallback": fallback,
                "cached": cached,
                "error_class": error_class,
                "at": datetime.now(UTC),
            }
        )
