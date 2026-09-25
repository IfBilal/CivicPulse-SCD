"""`08-AI-TRIAGE.md §1`, verbatim + the documented deviation.

**Deviation declared (ADR-0001):** the spec writes `def triage(...)` synchronous; here it is
`async` because a blocking 10s HTTP call inside an async FastAPI worker serialises every
concurrent request under the event loop — the alternative (`run_in_threadpool`) was rejected
because it multiplies threads per pod and makes the timeout non-cancellable. The *shape* of the
contract — one method, `(text, location) -> TriageResult` — is unchanged. `aclose()` is added so
the lifespan can release the connection pool on SIGTERM.

Calling convention: keyword-only `(*, text, location)`, matching this codebase's existing call
sites (`schemas.triage.TriageResult` construction, `services/triage_service.py`'s ladder) rather
than the spec section's positional sketch — kept consistent rather than introducing a mismatch
between provider implementations.

`Protocol` (structural typing), not an ABC: `SimulatedTriage`/`RuleBasedTriage`/`LLMTriage`/
`OllamaTriage` are not subclasses of anything, they merely *have the shape*. That is the point —
a provider written by someone who never saw this file still drops in as long as it matches.
"""

from typing import Protocol, runtime_checkable

from app.schemas.triage import TriageResult


@runtime_checkable
class TriageProvider(Protocol):
    name: str  # e.g. "llm:groq" — goes straight into `triaged_by`

    async def triage(self, *, text: str, location: str) -> TriageResult: ...

    async def aclose(self) -> None: ...
