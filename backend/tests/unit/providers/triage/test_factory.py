"""`08-AI-TRIAGE.md §2` — `build_triage_provider` wires `TRIAGE_PROVIDER` to the right class.
Testable without any network call: constructing `LLMTriage`/`OllamaTriage` doesn't connect.

`Settings` is `frozen=True` (`06-BACKEND-CORE.md §1`), so these tests build a fresh instance via
`model_copy(update=...)` rather than assigning attributes after construction — same pattern as
`tests/integration/conftest.py`'s `migrated_db` fixture."""

import pydantic
import pytest

from app.providers.triage.factory import build_triage_provider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import FailureMode, SimulatedTriage
from app.settings import Settings

pytestmark = pytest.mark.unit


def _settings(provider: str, **overrides: object) -> Settings:
    return Settings().model_copy(update={"triage_provider": provider, **overrides})


def test_simulated_provider_selected() -> None:
    provider = build_triage_provider(_settings("simulated"))
    assert isinstance(provider, SimulatedTriage)


def test_simulated_provider_uses_configured_seed_and_failure_mode() -> None:
    s = _settings("simulated", simulated_seed=999, simulated_failure_mode="raise")
    provider = build_triage_provider(s)
    assert isinstance(provider, SimulatedTriage)
    assert provider._seed == 999
    assert provider._failure_mode == FailureMode.RAISE


def test_rules_provider_selected() -> None:
    provider = build_triage_provider(_settings("rules"))
    assert isinstance(provider, RuleBasedTriage)


def test_llm_provider_selected() -> None:
    provider = build_triage_provider(_settings("llm"))
    assert isinstance(provider, LLMTriage)


def test_ollama_provider_selected() -> None:
    provider = build_triage_provider(_settings("ollama"))
    assert isinstance(provider, OllamaTriage)


def test_unknown_provider_value_rejected_at_settings_construction() -> None:
    """`triage_provider` is `Literal["llm","ollama","rules","simulated"]` — an unrecognised
    value is a `ValidationError` when `Settings` is built, before `build_triage_provider` is
    ever called. This supersedes an earlier fail-closed-to-rules design (see
    docs/ENGINEERING-NOTES.md, "Provider default on an unrecognised TRIAGE_PROVIDER value",
    2026-09-25 update): a config typo now crashes at boot, consistent with every other
    `Settings` field's `extra="forbid"`/`frozen=True` posture, rather than silently degrading."""
    with pytest.raises(pydantic.ValidationError):
        Settings(triage_provider="nonsense-value")  # type: ignore[arg-type]
