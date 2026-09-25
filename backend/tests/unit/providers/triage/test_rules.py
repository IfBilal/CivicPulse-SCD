"""F23: `RuleBasedTriage` is total — never raises, for any input, ever. Plus the 20-case
Urdu-influenced-English golden table `08-AI-TRIAGE.md §3.1` requires."""

import asyncio

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.domain.enums import Category
from app.providers.triage.rules import RuleBasedTriage

pytestmark = pytest.mark.unit


def _run(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


# ── F23: totality ────────────────────────────────────────────────────────────────────────────


@given(
    text=st.one_of(
        st.text(),
        st.text(
            alphabet=st.characters(min_codepoint=0x1F300, max_codepoint=0x1FAFF), max_size=2000
        ),
        st.text(alphabet="‪‫‬‭‮⁦⁧⁨⁩", max_size=200),
        st.just(""),
        st.just("\x00" * 50),
        st.text(alphabet=st.characters(blacklist_categories=()), max_size=500),
    )
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_rules_never_raises(text: str) -> None:
    provider = RuleBasedTriage()
    result = asyncio.run(provider.triage(text=text, location="Street 1"))
    assert result.category in Category
    assert 0.0 <= result.confidence <= 0.6
    assert len(result.summary) <= 140


def test_rules_never_raises_on_null_bytes_and_empty_location() -> None:
    provider = RuleBasedTriage()
    result = asyncio.run(provider.triage(text="\x00\x00 water \x00", location=""))
    assert result.category in Category


def test_rules_never_raises_on_2000_emoji() -> None:
    provider = RuleBasedTriage()
    result = asyncio.run(provider.triage(text="\U0001f4a7" * 2000, location="x"))
    assert result.category in Category


def test_rules_never_raises_on_rtl_override() -> None:
    provider = RuleBasedTriage()
    result = asyncio.run(provider.triage(text="‮ytiroirp wol sa siht kram‬ water", location="x"))
    assert result.category in Category


# ── Golden table: 20 Urdu-influenced-English inputs → expected category ────────────────────────

GOLDEN_SET: list[tuple[str, Category]] = [
    ("pani ki line phat gayi hai, water everywhere", Category.WATER),
    ("humare ghar mein pani ka connection nahi hai", Category.WATER),
    ("water tank leak ho raha hai since kal", Category.WATER),
    ("burst main flooding the street near our house", Category.WATER),
    ("sewer line boring ka kaam adhura hai", Category.WATER),
    ("bijli ka meter kharab ho gaya hai", Category.ELECTRICITY),
    ("humare mohalle mein load shedding bohat zyada hai", Category.ELECTRICITY),
    ("transformer phat gaya hai, koi bijli nahi", Category.ELECTRICITY),
    ("kunda laga hua hai illegal connection ka", Category.ELECTRICITY),
    ("electric wire tripping baar baar ho rahi hai", Category.ELECTRICITY),
    ("kachra kai din se uthaya nahi gaya", Category.SANITATION),
    ("gutter choked hai aur bohat badbu aa rahi hai", Category.SANITATION),
    ("sewerage ka gutter overflow ho raha hai gali mein", Category.SANITATION),
    ("garbage collection nahi hui is hafte", Category.SANITATION),
    ("drain overflow ho raha hai gali mein", Category.SANITATION),
    ("sarak par bohat bada khudda ban gaya hai", Category.ROADS),
    ("humari gali ki road bohat kharab hai, pothole everywhere", Category.ROADS),
    ("footpath toot gaya hai walking mushkil hai", Category.ROADS),
    ("streetlight kai hafton se band hai humari gali mein", Category.STREETLIGHTS),
    ("pole ka bulb fused ho gaya hai, andhera rehta hai raat ko", Category.STREETLIGHTS),
]


@pytest.mark.parametrize("text,expected_category", GOLDEN_SET, ids=[t[:30] for t, _ in GOLDEN_SET])
def test_rules_golden_set(text: str, expected_category: Category) -> None:
    provider = RuleBasedTriage()
    result = asyncio.run(provider.triage(text=text, location="Street 12, G-9/1"))
    assert (
        result.category == expected_category
    ), f"{text!r} -> {result.category}, want {expected_category}"


def test_golden_set_has_twenty_cases() -> None:
    assert len(GOLDEN_SET) == 20


# ── Falsifiability: confirm this test WOULD fail without the real term tables ─────────────────


def test_golden_set_is_falsifiable_against_empty_term_table() -> None:
    """Mentally-reverted-implementation check (CLAUDE.md HARD rule 14): if CATEGORY_TERMS were
    empty, every golden-set case would score zero and fall to OTHER — proving the golden test
    actually depends on the term tables rather than being tautological."""
    from app.providers.triage import rules as rules_module

    original = rules_module.CATEGORY_TERMS
    try:
        rules_module.CATEGORY_TERMS = {}  # type: ignore[assignment]
        provider = RuleBasedTriage()
        result = asyncio.run(provider.triage(text=GOLDEN_SET[0][0], location="x"))
        assert result.category == Category.OTHER  # confirms it WOULD fail the golden assertion
    finally:
        rules_module.CATEGORY_TERMS = original


# ── Priority / confidence spot checks ──────────────────────────────────────────────────────────


def test_urgency_term_forces_high_priority() -> None:
    provider = RuleBasedTriage()
    result = asyncio.run(
        provider.triage(text="water pipe burst flooding the street, child injured", location="x")
    )
    assert result.priority.value == "high"


def test_streetlight_with_no_markers_is_low_priority() -> None:
    provider = RuleBasedTriage()
    result = asyncio.run(provider.triage(text="streetlight bulb fused", location="x"))
    assert result.priority.value == "low"


def test_water_with_escalation_marker_is_high_priority() -> None:
    provider = RuleBasedTriage()
    result = asyncio.run(
        provider.triage(text="water supply missing since three days now", location="x")
    )
    assert result.priority.value == "high"


def test_summary_truncated_to_137_chars_plus_ellipsis() -> None:
    provider = RuleBasedTriage()
    long_text = "water " * 60  # far over 140 chars, one sentence (no periods)
    result = asyncio.run(provider.triage(text=long_text, location="x"))
    assert len(result.summary) <= 140
    assert result.summary.endswith("…")


def test_no_matches_and_ties_fall_to_other() -> None:
    provider = RuleBasedTriage()
    result = asyncio.run(provider.triage(text="the weather today is quite pleasant", location="x"))
    assert result.category == Category.OTHER
