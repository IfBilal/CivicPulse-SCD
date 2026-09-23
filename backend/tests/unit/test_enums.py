import pytest

from app.domain.enums import Category, Priority, Status, TriagedBy

pytestmark = pytest.mark.unit


def test_category_matches_spec() -> None:
    # 00-SPEC.md §2.3 verbatim
    assert [c.value for c in Category] == [
        "water",
        "electricity",
        "sanitation",
        "roads",
        "streetlights",
        "other",
    ]


def test_priority_matches_spec() -> None:
    assert [p.value for p in Priority] == ["high", "normal", "low"]


def test_status_matches_spec() -> None:
    assert [s.value for s in Status] == ["open", "in_progress", "resolved", "rejected"]


def test_triaged_by_is_spec_plus_documented_a4_superset_only() -> None:
    spec = {"llm:groq", "llm:ollama", "rules", "rules:fallback"}
    a4_superset = {"llm:gemini", "simulated"}
    assert {t.value for t in TriagedBy} == spec | a4_superset


def test_strenum_compares_equal_to_wire_string() -> None:
    assert Category.WATER == "water"
