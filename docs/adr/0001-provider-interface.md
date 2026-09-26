# ADR-0001 — Triage provider interface

- **Status:** Accepted · 2026-09-25 · Phase 4 (`feat/ai-triage`)
- **Deciders:** DEV-A (author, primary owner of `backend/app/providers/triage/`), DEV-B (review)
- **Satisfies:** `00-SPEC.md §Appendix A` (contradiction A5) · `08-AI-TRIAGE.md §1` · Rubric F
  *"the classifier must be replaceable"*

## Context

`00-SPEC.md §149` requires everything under `providers/` to sit **behind interfaces** — a
classifier swap (rules → LLM → a different LLM → back to rules under an outage) must never
touch `services/`, `routes/`, or any call site. Two separate decisions were needed to make that
real rather than aspirational:

1. **How is the interface itself expressed** — an abstract base class every provider inherits
   from, or something structural?
2. **What does the spec's own sketch get wrong once it meets a real async web framework**, and
   how far is it safe to deviate from the literal text.

## Decision 1 — `Protocol`, not an ABC

```python
# backend/app/providers/triage/base.py
@runtime_checkable
class TriageProvider(Protocol):
    name: str
    async def triage(self, *, text: str, location: str) -> TriageResult: ...
    async def aclose(self) -> None: ...
```

`SimulatedTriage`, `RuleBasedTriage`, `LLMTriage`, and `OllamaTriage` are not subclasses of
anything — they merely *have the shape*. `@runtime_checkable` lets `isinstance()` checks work
in tests without importing every concrete provider.

### Options considered

| | Coupling | A provider written elsewhere, dropped in cold | Cost to add a 5th provider |
|---|---|---|---|
| A. Abstract base class, every provider inherits | Every provider imports and depends on the base module | Must know about and subclass it first | One import, one `super().__init__()` discipline to get right |
| B. `Protocol` (structural typing) | None — no provider imports `base.py` at runtime, only for the type hint | Works immediately if the shape matches, no shared ancestor needed | Write `triage()`/`aclose()`/`name`, nothing else |
| C. A plain function signature, no class at all | None | Works, but loses the ability to carry per-provider state (an HTTP client, a cache) cleanly | Simplest, but `LLMTriage`/`OllamaTriage` both need a held-open client — would need a closure or a second parallel "state" object |

**Chose B.** The spec's own replaceability requirement is best satisfied by the option with the
*least* coupling — a `Protocol` means `TriageService` (the consumer) and any given provider
(the implementation) share nothing except the shape, so a provider genuinely never needs to
know this codebase's base module exists. Rejected A because inheritance is coupling the
replaceability requirement explicitly argues against; rejected C because two of the four real
providers need to hold a client across calls, which a bare function can't express cleanly.

## Decision 2 — declared deviation from the spec's literal method signature

`08-AI-TRIAGE.md §1`'s own sketch writes `def triage(...)` — synchronous. The real interface is
`async def triage(...)`.

**Why:** a blocking 10-second HTTP call (Groq, Ollama) inside a synchronous function, called
from an async FastAPI request handler, serialises every concurrent request behind the event
loop — one slow triage call would stall the entire worker, not just its own request.

**Alternative considered and rejected:** `run_in_threadpool` (wrap the sync call in FastAPI's
own thread-pool helper). Rejected for two reasons: it multiplies OS threads per pod under load
(one thread per in-flight triage call, on top of the async event loop already handling
everything else), and the per-call timeout (`triage_timeout_s`, `asyncio.timeout` in
`TriageService`) becomes non-cancellable — a thread blocked on a slow socket read can't be
interrupted the way an `asyncio.timeout`-wrapped coroutine can, which directly undermines the
fallback ladder's own timeout guarantee (CLAUDE.md HARD rule 5).

The *shape* of the contract is otherwise unchanged from the spec: one method,
`(text, location) -> TriageResult`. `aclose()` is an addition, not a deviation — it lets the
app's lifespan release each provider's held connection (an `AsyncOpenAI`/`httpx.AsyncClient`
instance) cleanly on SIGTERM, rather than leaking a socket per worker restart.

**Calling convention:** keyword-only `(*, text, location)`, not the spec section's positional
sketch — kept consistent with every other call site in this codebase (`TriageResult`
construction, `TriageService`'s own ladder) rather than introducing one provider-facing
exception to an otherwise uniform convention.

## Decision 3 — `confidence` (contradiction A5)

`00-SPEC.md` contradiction A5: `TriageResult.confidence` is validated by the schema but the
spec's own worked example never persists or uses it past validation — "validated and then
discarded." The documented default resolution (A5's own entry) is the superset: persist it
**and** use it as a guard.

**Decision:** `triage_confidence NUMERIC(3,2) NULL` on `complaints` (a `CHECK` constraint
enforces `0 <= confidence <= 1` when not null — `backend/app/db/models.py`'s
`confidence_range` constraint), and `TriageService`'s post-validation step downgrades the
result to `Category.OTHER`/lower priority when `confidence < triage_min_confidence` (a real,
tested guard, not a stored-and-ignored column). Chosen because storing it is strictly a
superset of the spec's literal "discard" behaviour — nothing that discards confidence breaks by
it also being persisted, and the guard turns a number that would otherwise do nothing into a
real defence layer against a low-confidence provider result being trusted at face value.

## Consequences

- Any future 5th provider (Gemini, a different self-hosted model, a stub for a demo) needs no
  base-class knowledge — implement the three-member shape and it works, verified by
  `tests/unit/providers/triage/test_base_protocol.py::test_all_four_providers_satisfy_protocol`.
- `TriageService`'s constructor, retry loop, and fallback boundary never import a concrete
  provider type — only the `Protocol`.
- The async requirement means every provider's tests must use `httpx.MockTransport` or an
  injected fake client (never a real socket, CLAUDE.md HARD rule 15) rather than a simple
  synchronous stub.
