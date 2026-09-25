"""Deterministic keyword-rule classifier — `00-SPEC.md`: "always available, never fails."

This is the fallback of last resort: `TriagedBy.RULES_FALLBACK` is what `POST /api/complaints`
returns when the primary provider raised, timed out, or returned malformed data. It must never
itself raise — every code path below ends in a valid `TriageResult`, including the empty-text
edge case (Pydantic already enforces `TEXT_MIN` upstream, but this function stays defensive).
"""

import re

from app.domain.enums import Category, Priority
from app.domain.limits import SUMMARY_MAX
from app.schemas.triage import TriageResult

# Keyword -> category. Checked in order; first match wins. Ordered most-specific-first so
# "water" doesn't shadow "sewage water" style sanitation complaints.
_CATEGORY_KEYWORDS: list[tuple[Category, tuple[str, ...]]] = [
    (
        Category.SANITATION,
        ("sewage", "sewer", "garbage", "trash", "drain", "waste", "sanitation", "dirty water"),
    ),
    (Category.WATER, ("water", "pipe", "leak", "flood", "burst main", "tap")),
    (
        Category.ELECTRICITY,
        ("electric", "power", "transformer", "wire", "shock", "meter", "voltage"),
    ),
    (Category.STREETLIGHTS, ("streetlight", "street light", "pole light", "lamp post", "lamppost")),
    (Category.ROADS, ("road", "pothole", "street", "footpath", "pavement", "bridge")),
]

# Keyword -> priority. Checked before category so an urgent sanitation complaint about a
# "burst" pipe still reads HIGH even though "burst" also appears in the water list.
_HIGH_PRIORITY_KEYWORDS = (
    "urgent",
    "emergency",
    "danger",
    "fire",
    "shock",
    "flood",
    "burst",
    "collapse",
    "injur",
    "life",
)
_LOW_PRIORITY_KEYWORDS = ("cosmetic", "minor", "eventually", "whenever", "no rush", "sometime")


def _classify_category(text: str) -> Category:
    lowered = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(kw in lowered for kw in keywords):
            return category
    return Category.OTHER


def _classify_priority(text: str) -> Priority:
    lowered = text.lower()
    if any(kw in lowered for kw in _HIGH_PRIORITY_KEYWORDS):
        return Priority.HIGH
    if any(kw in lowered for kw in _LOW_PRIORITY_KEYWORDS):
        return Priority.LOW
    return Priority.NORMAL


def _summarize(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= SUMMARY_MAX:
        return collapsed
    return collapsed[: SUMMARY_MAX - 1].rstrip() + "…"


class RuleBasedTriage:
    """Keyword classifier. Deterministic, synchronous logic wrapped in an async method so it
    satisfies `TriageProvider` without a separate sync/async split."""

    name = "rules"

    async def triage(self, *, text: str, location: str) -> TriageResult:
        return TriageResult(
            category=_classify_category(text),
            priority=_classify_priority(text),
            summary=_summarize(text),
            confidence=1.0,  # deterministic rules — always fully confident in its own output
        )

    async def aclose(self) -> None:
        return None
