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
| 13 | CI job (contract tests + drift gate) | **done** — green on PR #23 |
| 14 | `grilled meat` | **done** (findings in `docs/AI-USAGE.md`) |
| 15 | PR into `dev`, both approve | **PR #23 open** (Closes #22) — waiting on both approvals |

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

All build work is done and CI is green; what's left is **your review and sign-off**. This is
the last cheap moment to change the contract (after merge it's a `chore/contract-*` PR).

1. Pull the branch (§0), run `cd backend && pytest` (59 pass) and `make gen-client && git diff
   --exit-code` (must be clean).
2. Review PR #23 **with a real comment** (Rubric A: no "LGTM"). Especially check:
   - `backend/app/routes/*.py`: these are *your* Phase 3 files. Signatures, `operation_id`s and
     `responses=` are the frozen contract; bodies are yours to fill.
   - The 6 decisions in the PR body / §2 above. If you disagree, change it **on this branch
     before approving**, re-run `make gen-client`, commit both `openapi.json` and `schema.d.ts`.
   - grilled-meat finding #5 (`docs/AI-USAGE.md`): `fields[].constraint` only has the bound
     Pydantic reports, not both min+max as in the `04-CONTRACTS.md §5.1` example. Accept or fix.
3. Both of us approve → merge into `dev`.

## 4. Notes for Phase 2/3

- **Phase 3 (you):** delete `_on_not_implemented` in `app/errors.py` and
  `test_stub_routes_are_501_until_phase_3` once every handler is real. The request-id
  middleware should set `request.state.request_id`; `request_id_of()` already reads it.
- `limits.py` constants are meant to be imported by your Alembic migration's CHECK constraints
  (`04-CONTRACTS.md §2`), so app and DB can't drift.
- `make check`'s `test-be` step is **green now** (93% coverage), so the "expected red" note in
  ENGINEERING-NOTES no longer applies.
- **Phase 2b (me):** the Vite scaffold grows the existing `frontend/package.json`; the Makefile's
  frontend targets switch on once `frontend/vite.config.ts` exists.
- Activate `backend/.venv` before committing, or the pre-commit hook fails with
  `pre-commit not found` (install it into the venv: `pip install pre-commit`).
