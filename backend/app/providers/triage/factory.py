"""`08-AI-TRIAGE.md §2`. `TRIAGE_PROVIDER` selects which `TriageProvider` the app wires up.
`.env.example` ships `TRIAGE_PROVIDER=simulated` — a fresh clone runs with no key, no network.
"""

from app.providers.triage.base import TriageProvider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import FailureMode, SimulatedTriage
from app.settings import Settings


def build_triage_provider(s: Settings) -> TriageProvider:
    # No `case _`: `Settings.triage_provider` is `Literal["llm","ollama","rules","simulated"]`
    # (06-BACKEND-CORE.md §1, merged from Phase 3), so an unrecognised value is already a
    # Pydantic ValidationError at settings-construction time, before this function ever runs —
    # a typo'd TRIAGE_PROVIDER crashes at boot, same as every other Settings field
    # (`extra="forbid"`'s whole point). mypy can prove this match is exhaustive without a
    # default arm.
    match s.triage_provider:
        case "llm":
            return LLMTriage(s)
        case "ollama":
            return OllamaTriage(s)
        case "rules":
            return RuleBasedTriage()
        case "simulated":
            return SimulatedTriage(
                seed=s.simulated_seed,
                failure_mode=FailureMode(s.simulated_failure_mode),
            )
