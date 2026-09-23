# HANDOVER — `feat/contract-freeze` (Phase 1, joint)

**From:** IfBilal (DEV-B / Edge) · **To:** T361 (DEV-A / Core) · **Date:** 2026-09-23
**Branch:** `feat/contract-freeze` (the ONE shared Phase 1 branch — commit here, don't fork it)

This file is updated after every chunk of work and pushed with it. If you're reading it, the
"Status" table below is the truth as of the latest commit on this branch.

---

## 0. How to pick this up

```bash
git fetch && git switch feat/contract-freeze && git pull
cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" pre-commit
source .venv/bin/activate          # pre-commit hook + make targets need this on PATH
cd .. && (cd frontend && npm ci)   # once frontend/package.json exists (task 10)
```

Caveman task list for this phase: `docs/AI-USAGE.md` → `2026-09-23 · feat/contract-freeze`.

## 1. Status

| # | Task | Status |
|---|---|---|
| 1 | `domain/enums.py` | **done** |
| 2 | `domain/limits.py` | **done** |
| 3 | `domain/transitions.py` | **done** |
| 4 | `schemas/` (complaint, page, stats, meta, health, errors, triage) | **done** |
| 5 | App factory + route signatures (stubs) | **done** |
| 6 | Validation handler (422→400, bad UUID→404) | **done** |
| 7 | OpenAPI post-processing (no 422, relative servers) | **done** |
| 8 | `app/cli/openapi_dump.py` | **done** |
| 9 | Makefile `python` → `python3` | **done** |
| 10 | `frontend/package.json` + `schema.d.ts` | **done** |
| 11 | Unit tests (transitions, enums) | **done** |
| 12 | Contract tests | **done** |
| 13 | CI job (contract tests + drift gate) | **done** (not yet seen green on GitHub — check the PR run) |
| 14 | `grilled meat` | **done** (findings in `docs/AI-USAGE.md`) |
| 15 | PR into `dev`, both approve | todo |

## 2. Decisions taken (ponytail records live in `docs/ENGINEERING-NOTES.md`)

Four ponytail records in `docs/ENGINEERING-NOTES.md` (search "Phase 1 (joint)"):
1. Route bodies are stubs → `501 not_implemented` (handler in `app/errors.py`). **Phase 3: delete
   `_on_not_implemented` + `test_stub_routes_are_501_until_phase_3` once every handler is real.**
2. One `ErrorEnvelope` with untyped `details`; per-code shapes pinned by contract tests.
3. Stats buckets are `dict[Enum, int]`; zero-fill is the stats service's job (Phase 4).
4. Empty `reporter_contact` → `null`.

Also: non-UUID path id → **404** (handled in the validation handler, not the route);
`/metrics` is `include_in_schema=False` so the typed client has exactly 8 operations.

## 3. What you (DEV-A) need to do

- Review everything above marked done — Phase 1 needs **both** sign-offs; you are co-owner,
  not a rubber stamp. Push back on any decision in §2 you disagree with *before* freeze.
- Finish anything still `todo`, in order.
