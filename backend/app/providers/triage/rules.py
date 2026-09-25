"""`RuleBasedTriage` — `08-AI-TRIAGE.md §3.1`. The floor the whole system stands on.

The contract is total: **this may not raise, for any input, ever.** No I/O, no regex
catastrophic backtracking, no unbounded loops. Every string operation here is O(n) in input
length with no nested scans over user-controlled text.

Urdu-influenced English (`pani`, `bijli`, `kachra`, `khudda`, `kunda`, `sarak`) is a first-class
requirement, not decoration — the seed corpus and the dashboard demo are written in it, and the
buy-vs-host comparison in ADR-0001 is meaningless if the keyword baseline is only evaluated on
textbook English.
"""

import re

from app.domain.enums import Category, Priority
from app.domain.limits import SUMMARY_MAX
from app.schemas.triage import TriageResult

# category → (term, weight). Weight is specificity: multi-word/technical terms score higher
# than generic single words, so "power" (generic) doesn't out-vote "transformer" (specific).
CATEGORY_TERMS: dict[Category, tuple[str, ...]] = {
    Category.WATER: (
        "water",
        "pani",
        "burst",
        "main",
        "leak",
        "tank",
        "supply",
        "pipeline",
        "sewer line",
        "boring",
    ),
    Category.ELECTRICITY: (
        "electric",
        "bijli",
        "power",
        "transformer",
        "load shedding",
        "wire",
        "meter",
        "kunda",
        "tripping",
    ),
    Category.SANITATION: (
        "garbage",
        "kachra",
        "sewerage",
        "drain",
        "gutter",
        "sanitation",
        "waste",
        "smell",
        "choked",
    ),
    Category.ROADS: (
        "road",
        "sarak",
        "pothole",
        "khudda",
        "footpath",
        "manhole",
        "speed breaker",
        "tarcoal",
    ),
    Category.STREETLIGHTS: (
        "streetlight",
        "street light",
        "pole",
        "lamp",
        "fused",
        "dark",
        "bulb",
        "light of pole",
    ),
}

URGENCY_TERMS = (
    "flood",
    "flooding",
    "burst",
    "fire",
    "live wire",
    "current",
    "electrocut",
    "overflow",
    "collapse",
    "injur",
    "accident",
    "hospital",
    "child",
    "urgent",
    "emergency",
    "sinking",
)

# Multi-word terms get a specificity boost over single words — purely a tie-break signal,
# never large enough to let a single generic word beat several specific ones.
_MULTIWORD_WEIGHT = 2
_SINGLEWORD_WEIGHT = 1

_ESCALATION_MARKERS = ("since", "days", "night")

# Strip zero-width chars (U+200B-200D, U+FEFF) and bidi control chars (U+202A-202E, U+2066-2069).
_STRIP_CHARS_RE = re.compile(
    "[​-‍﻿‪-‮⁦-⁩]" "|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"  # C0 control chars except \t\n
)
_WHITESPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _normalise(text: str) -> str:
    """Casefold, strip zero-width/bidi/control chars, collapse whitespace. Bounded, no
    backtracking."""
    stripped = _STRIP_CHARS_RE.sub("", text)
    folded = stripped.casefold()
    return _WHITESPACE_RE.sub(" ", folded).strip()


def _word_set(normalised: str) -> set[str]:
    return set(_WORD_RE.findall(normalised))


def _contains_term(normalised: str, words: set[str], term: str) -> bool:
    """Whole-word match. Multi-word terms match as a substring on the normalised text (bounded,
    fixed-length needle, no backtracking); single-word terms match against the word set."""
    if " " in term:
        return term in normalised
    return term in words


def _score_categories(normalised: str) -> tuple[Category, int]:
    words = _word_set(normalised)
    scores: dict[Category, int] = dict.fromkeys(CATEGORY_TERMS, 0)
    matched_total = 0
    for category, terms in CATEGORY_TERMS.items():
        for term in terms:
            if _contains_term(normalised, words, term):
                weight = _MULTIWORD_WEIGHT if " " in term else _SINGLEWORD_WEIGHT
                scores[category] += weight
                matched_total += 1

    best_category = Category.OTHER
    best_score = 0
    for category, score in scores.items():
        if score > best_score:
            best_score = score
            best_category = category
    if best_score == 0:
        return Category.OTHER, matched_total
    # Tie check: if another category matches the same top score, it's ambiguous → OTHER.
    ties = [c for c, s in scores.items() if s == best_score]
    if len(ties) > 1:
        return Category.OTHER, matched_total
    return best_category, matched_total


def _has_urgency_term(normalised: str, words: set[str]) -> bool:
    return any(_contains_term(normalised, words, term) for term in URGENCY_TERMS)


def _has_escalation_marker(normalised: str) -> bool:
    return any(marker in normalised for marker in _ESCALATION_MARKERS)


def _classify_priority(normalised: str, words: set[str], category: Category) -> Priority:
    if _has_urgency_term(normalised, words):
        return Priority.HIGH
    if category in (Category.WATER, Category.ELECTRICITY) and _has_escalation_marker(normalised):
        return Priority.HIGH
    if category in (Category.STREETLIGHTS, Category.OTHER):
        return Priority.LOW
    return Priority.NORMAL


def _summarise(text: str) -> str:
    """First sentence, whitespace-collapsed, hard-truncated to 137 chars + '…'."""
    collapsed = _WHITESPACE_RE.sub(" ", text).strip()
    if not collapsed:
        return ""
    parts = _SENTENCE_SPLIT_RE.split(collapsed, maxsplit=1)
    first = parts[0] if parts else collapsed
    if len(first) > SUMMARY_MAX - 3:
        return first[: SUMMARY_MAX - 3].rstrip() + "…"
    return first


class RuleBasedTriage:
    """Keyword-rule fallback. `name` doubles as `triaged_by` when used as the primary provider
    (`TRIAGE_PROVIDER=rules`); `TriageService` overrides it to `rules:fallback` when this runs
    as the fallback path of another provider's failed attempt."""

    name = "rules"

    async def triage(self, *, text: str, location: str) -> TriageResult:
        del location  # rules don't use location; kept for interface parity
        try:
            normalised = _normalise(text)
            words = _word_set(normalised)
            category, matched = _score_categories(normalised)
            priority = _classify_priority(normalised, words, category)
            summary = _summarise(text)
            confidence = min(0.6, 0.15 * matched)
            return TriageResult(
                category=category,
                priority=priority,
                summary=summary,
                confidence=confidence,
            )
        except Exception:
            # The contract is total — this may NEVER raise. If something genuinely
            # unanticipated happens above, degrade to the most conservative possible
            # classification rather than propagate.
            return TriageResult(
                category=Category.OTHER,
                priority=Priority.NORMAL,
                summary="",
                confidence=0.0,
            )

    async def aclose(self) -> None:
        return None
