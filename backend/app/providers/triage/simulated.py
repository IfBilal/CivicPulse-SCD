"""`SimulatedTriage` — `08-AI-TRIAGE.md §3.2`. Deterministic fake with configurable failure
injection. **CI, always** (`.env.example`'s default `TRIAGE_PROVIDER=simulated`) — this is what
lets a fresh clone run with no key, no network, and a fully green, repeatable test suite.

Determinism: `rng = random.Random(seed ^ zlib.crc32(text.encode()))` — same input, same output,
on every machine, forever. No network, no clock read for the RNG seed itself.

Each `FailureMode` exercises exactly one branch of `TriageService`'s fallback ladder (§5):
`RAISE` is a bare, non-timeout, non-HTTP-shaped exception (documented below as NON_RETRYABLE-
shaped, since a generic `RuntimeError` is not one of the RETRYABLE exception types the ladder
recognises — this is deliberate: it proves the ladder's fallback boundary catches *anything*,
not just the exceptions it explicitly classifies).
"""

import asyncio
import random
import zlib
from enum import StrEnum

from app.domain.enums import Category, Priority
from app.schemas.triage import TriageResult


class FailureMode(StrEnum):
    NONE = "none"
    RAISE = "raise"
    TIMEOUT = "timeout"
    MALFORMED = "malformed"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    BAD_ENUM = "bad_enum"
    OVERLONG_SUMMARY = "overlong_summary"
    LOW_CONFIDENCE = "low_confidence"
    INJECTION_OBEY = "injection_obey"


class SimulatedRateLimitError(Exception):
    """Shaped like a 429 — `TriageService.RETRYABLE` recognises this type."""


class SimulatedServerError(Exception):
    """Shaped like a 5xx — `TriageService.RETRYABLE` recognises this type."""


class SimulatedMalformedResponseError(Exception):
    """Shaped like a JSON decode failure on the raw provider response —
    `TriageService.NON_RETRYABLE` recognises this type. No retry: the request was fine, the
    provider's output wasn't, and retrying a deterministic malformed response wastes budget."""


class SimulatedValidationError(Exception):
    """Raised when the (fake) provider's structurally-valid-JSON output fails
    `TriageResult` validation (bad enum, overlong summary, or any other schema mismatch) —
    `TriageService.NON_RETRYABLE` recognises this type."""


_SUMMARY_WORDS = (
    "a",
    "citizen",
    "complaint",
    "about",
    "the",
    "local",
    "civic",
    "situation",
    "reported",
    "for",
    "review",
)


class SimulatedTriage:
    """Deterministic fake `TriageProvider`. Never touches the network or the clock."""

    name = "simulated"

    def __init__(self, seed: int = 1337, failure_mode: FailureMode = FailureMode.NONE) -> None:
        self._seed = seed
        self._failure_mode = failure_mode

    def _rng_for(self, text: str) -> random.Random:
        # Deterministic test fixture, not a security primitive — non-cryptographic PRNG is the
        # correct choice here (§3.2's whole point is reproducibility, not unpredictability).
        return random.Random(self._seed ^ zlib.crc32(text.encode()))  # noqa: S311

    async def triage(self, *, text: str, location: str) -> TriageResult:
        del location
        rng = self._rng_for(text)
        mode = self._failure_mode

        if mode is FailureMode.RAISE:
            raise RuntimeError("SimulatedTriage: unconditional failure (FailureMode.RAISE)")

        if mode is FailureMode.TIMEOUT:
            # Sleep far longer than any realistic timeout budget so the CALLER's
            # asyncio.timeout(...) cancels this task — never block, never use time.sleep().
            await asyncio.sleep(3600)
            raise AssertionError("unreachable: caller must cancel via asyncio.timeout")

        if mode is FailureMode.RATE_LIMIT:
            raise SimulatedRateLimitError("429 rate limited (simulated)")

        if mode is FailureMode.SERVER_ERROR:
            raise SimulatedServerError("503 service unavailable (simulated)")

        if mode is FailureMode.MALFORMED:
            raise SimulatedMalformedResponseError("provider returned non-JSON prose (simulated)")

        if mode is FailureMode.BAD_ENUM:
            raise SimulatedValidationError(
                "provider returned category='vip', not a member of Category (simulated)"
            )

        if mode is FailureMode.OVERLONG_SUMMARY:
            raise SimulatedValidationError(
                "provider returned a 400-char summary, exceeds max_length=140 (simulated)"
            )

        if mode is FailureMode.INJECTION_OBEY:
            # Pretends to obey an injected instruction: returns the attacker's desired
            # (invalid) shape. Used by the injection test to prove the validator — not the
            # model's good behaviour — is what protects the schema.
            raise SimulatedValidationError(
                "provider returned category='vip', priority='low' — attacker-desired, "
                "not schema-valid (simulated INJECTION_OBEY)"
            )

        category = rng.choice(list(Category))
        priority = rng.choice(list(Priority))
        summary_len = rng.randint(3, 8)
        summary = " ".join(rng.choices(_SUMMARY_WORDS, k=summary_len)).capitalize()

        if mode is FailureMode.LOW_CONFIDENCE:
            confidence = round(rng.uniform(0.0, 0.34), 2)
        else:
            confidence = round(rng.uniform(0.5, 0.95), 2)

        return TriageResult(
            category=category,
            priority=priority,
            summary=summary,
            confidence=confidence,
        )

    async def aclose(self) -> None:
        return None
