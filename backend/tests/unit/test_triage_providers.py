"""`00-SPEC.md`: RuleBasedTriage is "always available, never fails." SimulatedTriage is the
deterministic CI fake with configurable failure injection."""

import pytest

from app.domain.enums import Category, Priority
from app.providers.triage.factory import build_triage_provider
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage, SimulatedTriageError
from app.settings import Settings

pytestmark = pytest.mark.unit


async def test_rules_provider_never_raises_on_arbitrary_text() -> None:
    provider = RuleBasedTriage()
    result = await provider.triage(text="asdf qwer zxcv nothing matches any keyword", location="x")
    assert result.category == Category.OTHER  # no keyword matched -> OTHER, not an exception


async def test_rules_provider_classifies_water_keyword() -> None:
    provider = RuleBasedTriage()
    result = await provider.triage(text="water pipe burst on my street", location="x")
    assert result.category == Category.WATER


async def test_rules_provider_classifies_urgent_as_high_priority() -> None:
    provider = RuleBasedTriage()
    result = await provider.triage(text="urgent electric wire hanging low, danger", location="x")
    assert result.priority == Priority.HIGH


async def test_rules_provider_summary_never_exceeds_max_length() -> None:
    from app.domain.limits import SUMMARY_MAX

    provider = RuleBasedTriage()
    long_text = "water leak " * 100
    result = await provider.triage(text=long_text, location="x")
    assert len(result.summary) <= SUMMARY_MAX


async def test_rules_provider_confidence_always_one() -> None:
    provider = RuleBasedTriage()
    result = await provider.triage(text="road pothole near F-7", location="x")
    assert result.confidence == 1.0


async def test_simulated_provider_is_deterministic_for_same_text() -> None:
    provider = SimulatedTriage(mode="ok")
    r1 = await provider.triage(text="same complaint text", location="x")
    r2 = await provider.triage(text="same complaint text", location="x")
    assert r1.category == r2.category
    assert r1.priority == r2.priority
    assert r1.confidence == r2.confidence


async def test_simulated_provider_differs_for_different_text() -> None:
    provider = SimulatedTriage(mode="ok")
    r1 = await provider.triage(text="alpha alpha alpha", location="x")
    r2 = await provider.triage(text="totally different content here", location="x")
    # not guaranteed to differ on every field, but the hash-derived category or priority
    # should not always coincide across arbitrary distinct inputs -- check confidence, which
    # has the widest range and is astronomically unlikely to collide by chance for these inputs
    assert r1.confidence != r2.confidence


async def test_simulated_always_raise_mode_raises() -> None:
    provider = SimulatedTriage(mode="always_raise")
    with pytest.raises(SimulatedTriageError):
        await provider.triage(text="x", location="y")


async def test_simulated_malformed_mode_raises() -> None:
    provider = SimulatedTriage(mode="malformed")
    with pytest.raises(SimulatedTriageError):
        await provider.triage(text="x", location="y")


def test_factory_builds_rules_provider() -> None:
    settings = Settings(triage_provider="rules")
    provider = build_triage_provider(settings)
    assert provider.name == "rules"


def test_factory_builds_simulated_provider() -> None:
    settings = Settings(triage_provider="simulated")
    provider = build_triage_provider(settings)
    assert provider.name == "simulated"


def test_factory_llm_raises_not_implemented_naming_phase_4() -> None:
    settings = Settings(triage_provider="llm", llm_api_key="gsk_dummy_key_for_validation_only")
    with pytest.raises(NotImplementedError, match="Phase 4"):
        build_triage_provider(settings)


def test_factory_ollama_raises_not_implemented_naming_phase_4() -> None:
    settings = Settings(triage_provider="ollama")
    with pytest.raises(NotImplementedError, match="Phase 4"):
        build_triage_provider(settings)
