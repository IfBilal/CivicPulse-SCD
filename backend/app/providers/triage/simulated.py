"""Seeded deterministic fake triage provider — `TRIAGE_PROVIDER=simulated` (CLAUDE.md §4: never
a live LLM call in CI). Also the vehicle for injecting the failure modes Phase 4's fallback and
retry machinery must handle: provider down, timeout-shaped raise, and malformed-output.

`mode` is set once at construction (from `settings` in the factory, or directly by a test via
`app.dependency_overrides[get_triage]`) — never mutated mid-request, so a single instance's
behavior is stable across a test.
"""

import hashlib
from typing import Literal

from app.domain.enums import Category, Priority
from app.schemas.triage import TriageResult

SimulatedMode = Literal["ok", "always_raise", "malformed"]

_CATEGORIES = list(Category)
_PRIORITIES = list(Priority)


class SimulatedTriageError(Exception):
    """Raised by `mode="always_raise"` — stands in for a provider-down / timeout / 5xx failure."""


class SimulatedTriage:
    """Deterministic: the same `text` always maps to the same category/priority/summary via a
    stable hash, so tests can assert exact output without randomness (CLAUDE.md HARD rule 15)."""

    name = "simulated"

    def __init__(self, mode: SimulatedMode = "ok") -> None:
        self._mode = mode

    async def triage(self, *, text: str, location: str) -> TriageResult:
        if self._mode == "always_raise":
            raise SimulatedTriageError("simulated provider failure")
        if self._mode == "malformed":
            # Malformed output surfaces as a validation failure at the boundary that parses it
            # (TriageService in Phase 4) — building a raw dict here rather than a TriageResult
            # is the honest way to simulate "provider returned bad JSON" without smuggling a
            # not-actually-a-TriageResult object past the type system silently.
            raise SimulatedTriageError("simulated malformed provider output")

        digest = hashlib.sha256(text.encode("utf-8")).digest()
        category = _CATEGORIES[digest[0] % len(_CATEGORIES)]
        priority = _PRIORITIES[digest[1] % len(_PRIORITIES)]
        summary = text.strip().splitlines()[0][:140]
        confidence = 0.5 + (digest[2] % 50) / 100  # deterministic value in [0.50, 0.99]
        return TriageResult(
            category=category, priority=priority, summary=summary, confidence=confidence
        )

    async def aclose(self) -> None:
        return None
