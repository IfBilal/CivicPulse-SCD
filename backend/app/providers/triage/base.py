"""`TriageProvider` Protocol — the one seam the whole assignment is testing (CLAUDE.md §0).

Any provider — real LLM, Ollama, rule-based, or a test fake — implements this shape. The
service layer depends on the Protocol, never on a concrete provider class, so swapping the
classifier is a DI change, not a rewrite.
"""

from typing import Protocol

from app.schemas.triage import TriageResult


class TriageProvider(Protocol):
    name: str

    async def triage(self, *, text: str, location: str) -> TriageResult:
        """Raise on any failure — timeout, bad JSON, wrong enum, provider down. The caller
        (`TriageService`, Phase 4) decides retry/fallback; a provider never fallback internally."""
        ...

    async def aclose(self) -> None:
        """Release any held resources (HTTP client, connection pool). No-op for pure providers."""
        ...
