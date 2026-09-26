"""F24: `test_all_four_providers_satisfy_protocol` — structural conformance, not inheritance.
`08-AI-TRIAGE.md §1`: "the system depends on a shape, not on an inheritance hierarchy.\" """

import httpx
import pytest

from app.providers.triage.base import TriageProvider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage
from app.settings import Settings

pytestmark = pytest.mark.unit


class _FakeOpenAIClient:
    class _Completions:
        async def create(self, **kwargs: object) -> object:
            raise NotImplementedError

    class _Chat:
        def __init__(self) -> None:
            self.completions = _FakeOpenAIClient._Completions()

    def __init__(self) -> None:
        self.chat = self._Chat()

    async def close(self) -> None:
        return None


def test_rule_based_triage_satisfies_protocol() -> None:
    assert isinstance(RuleBasedTriage(), TriageProvider)


def test_simulated_triage_satisfies_protocol() -> None:
    assert isinstance(SimulatedTriage(), TriageProvider)


def test_llm_triage_satisfies_protocol() -> None:
    settings = Settings()
    provider = LLMTriage(settings, client=_FakeOpenAIClient())
    assert isinstance(provider, TriageProvider)


def test_ollama_triage_satisfies_protocol() -> None:
    settings = Settings()
    fake_client = httpx.AsyncClient(base_url="http://ollama-does-not-exist.invalid")
    provider = OllamaTriage(settings, client=fake_client)
    assert isinstance(provider, TriageProvider)


def test_all_four_providers_satisfy_protocol() -> None:
    settings = Settings()
    fake_httpx_client = httpx.AsyncClient(base_url="http://ollama-does-not-exist.invalid")
    providers: list[object] = [
        RuleBasedTriage(),
        SimulatedTriage(),
        LLMTriage(settings, client=_FakeOpenAIClient()),
        OllamaTriage(settings, client=fake_httpx_client),
    ]
    for provider in providers:
        assert isinstance(provider, TriageProvider), f"{provider!r} does not satisfy TriageProvider"
        assert isinstance(provider.name, str)  # type: ignore[attr-defined]
        assert provider.name  # type: ignore[attr-defined]


def test_protocol_membership_is_falsifiable() -> None:
    """CLAUDE.md HARD rule 14: confirm the protocol check WOULD fail for a non-conforming type."""

    class NotAProvider:
        pass

    assert not isinstance(NotAProvider(), TriageProvider)
