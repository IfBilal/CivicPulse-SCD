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
| 1 | `domain/enums.py` | todo |
| 2 | `domain/limits.py` | todo |
| 3 | `domain/transitions.py` | todo |
| 4 | `schemas/` (complaint, page, stats, meta, health, errors, triage) | todo |
| 5 | App factory + route signatures (stubs) | todo |
| 6 | Validation handler (422→400, bad UUID→404) | todo |
| 7 | OpenAPI post-processing (no 422, relative servers) | todo |
| 8 | `app/cli/openapi_dump.py` | todo |
| 9 | Makefile `python` → `python3` | todo |
| 10 | `frontend/package.json` + `schema.d.ts` | todo |
| 11 | Unit tests (transitions, enums) | todo |
| 12 | Contract tests | todo |
| 13 | CI job (contract tests + drift gate) | todo |
| 14 | `grilled meat` | todo |
| 15 | PR into `dev`, both approve | todo |

## 2. Decisions taken (ponytail records live in `docs/ENGINEERING-NOTES.md`)

_(filled in as they happen)_

## 3. What you (DEV-A) need to do

- Review everything above marked done — Phase 1 needs **both** sign-offs; you are co-owner,
  not a rubber stamp. Push back on any decision in §2 you disagree with *before* freeze.
- Finish anything still `todo`, in order.
