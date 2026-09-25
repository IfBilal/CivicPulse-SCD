"""`build_triage_provider(settings)` — dispatches on `settings.triage_provider`.

`rules` and `simulated` are real Phase 3 implementations. `llm`/`ollama` are explicitly Phase 4
scope (see `docs/AI-USAGE.md`'s 2026-09-25 ponytail record) — raising `NotImplementedError`
here means a misconfigured `.env` fails loudly at startup instead of silently misrouting to a
provider that doesn't exist yet.
"""

from app.providers.triage.base import TriageProvider
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage
from app.settings import Settings


def build_triage_provider(settings: Settings) -> TriageProvider:
    if settings.triage_provider == "rules":
        return RuleBasedTriage()
    if settings.triage_provider == "simulated":
        return SimulatedTriage()
    if settings.triage_provider == "llm":
        raise NotImplementedError(
            "TRIAGE_PROVIDER=llm is Phase 4 scope (08-AI-TRIAGE.md) — not built yet."
        )
    if settings.triage_provider == "ollama":
        raise NotImplementedError(
            "TRIAGE_PROVIDER=ollama is Phase 4 scope (08-AI-TRIAGE.md) — not built yet."
        )
    raise ValueError(f"unknown triage_provider: {settings.triage_provider!r}")
