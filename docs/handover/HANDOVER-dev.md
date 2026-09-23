# HANDOVER — Gate 0 Closed, Phase 1 Contract Freeze Next

**From:** T361 (DEV-A / Core) · **To:** IfBilal (DEV-B / Edge) · **Date:** 2026-09-23
**Phase:** P0 Bootstrap → **closed**. **Phase:** P1 Contract Freeze — **not started, blocked on both of us**

This isn't a replacement for the planning docs — it's the "here's exactly where we are, here's
what's on you, here's what will bite you" note. Full role/ownership context is in
`01-WORKFLOW.md §1`/`§3.2` and the Phase 1 spec is in `02-CRITICAL-PATH.md §4` (PHASE 1) — read
both before you start. If you haven't read the prior handover, read `docs/handover/HANDOVER-phase0-devb-to-deva.md`
first — it explains the ground rules (branch protection, CODEOWNERS, no rubber-stamp reviews)
that are still in effect and this note doesn't repeat.

---

## 1. What's already done

Gate 0 is closed. `dev` is clean, up to date with `origin/dev`, and `main` has been synced to
match (`e95c521` on `main`, PR #21). Specifically:

- DEV-B's Phase 0 slice (`.gitignore`, `.env.example`, `.gitleaks.toml` + pre-commit, `.github/`
  scaffolding, branch protection on `main`, placeholder `ci.yml`) — merged, verified.
- DEV-A's Phase 0 slice — `backend/pyproject.toml` (deps, ruff, mypy, pytest+cov config) and the
  full Makefile — merged, plus a follow-up fix (`fcb3459`, PR #17) that added the missing
  `[build-system]` table and `version` key so `pip install -e ".[dev]"` actually works from a
  clean clone (Gate 0's checklist item was failing before that fix — see
  `docs/AI-USAGE.md`'s `2026-09-23 · fix/gate0-make-check` entry for the full finding list).
- `scripts/check_submission.py` exists — the 18-check `§5.3` mirror (PR #14).
- The Makefile `lint`/`type`/`test-fe` targets now guard on `test -d frontend` so they skip
  cleanly instead of failing on a directory that doesn't exist yet (Phase 2b scope).

**One deliberate, documented non-blocker:** `make check` still exits non-zero at the `test-be`
step. This is **not a bug** — `backend/app/` is intentionally just `__init__.py` right now, so
`pytest --cov-fail-under=65` has zero statements to cover and correctly fails. Don't "fix" this
by lowering the coverage floor. It clears itself once Phase 2 lands the first real module + test.
Full reasoning is in `docs/ENGINEERING-NOTES.md` (the `DEV-A · make check is expected red...`
section) — read it before you touch the coverage config for any reason.

**Also unresolved, flagged not fixed:** `03-REPO-BOOTSTRAP.md §5`'s Makefile line invokes
`python scripts/check_submission.py`, but only `python3` is on `PATH` on at least one dev
machine. Per `CLAUDE.md`'s precedence rule (implementation-doc bugs get said out loud, not
quietly patched), this was logged in `docs/ENGINEERING-NOTES.md` instead of silently fixed —
recommendation there is to change the Makefile target to call `python3` explicitly. **Decide
this together before Phase 1**, since the Makefile line is CODEOWNERS-neutral-ish (touches both
DEV-A's backend-tooling concern and DEV-B's original Makefile stub).

---

## 2. What's on both of us — Phase 1 is joint, not split

Unlike Phase 0, **Phase 1 is one PR, both devs, both approve** (`02-CRITICAL-PATH.md §4` PHASE 1,
and `04-CONTRACTS.md`'s own header: *"Owner: both, one PR, both approve"*). Don't split this into
parallel branches the way we did Phase 0 — the whole point of freezing the contract is that we
agree on it together before either of us builds against it.

Per `02-CRITICAL-PATH.md §4` PHASE 1, build:

| Task | Where it's specified |
|---|---|
| All ten endpoint shapes, request/response schemas | `04-CONTRACTS.md` (already drafted — verify against `00-SPEC.md §2.3`, don't just copy blind) |
| Field-level 400 envelope, 409 envelope (with attempted transition), pagination envelope | `04-CONTRACTS.md §2` onward |
| Enums (`Category`, `Priority`, `Status`, `TriagedBy`) in `backend/app/domain/enums.py` | `04-CONTRACTS.md §1` — content is given verbatim, including the two documented supersets (contradiction A4) |
| Header contract: `X-Request-ID`, `X-Cache`, `Retry-After` | `04-CONTRACTS.md` |
| The transition table as a **data structure** in `backend/app/domain/transitions.py` | `CLAUDE.md` HARD rule 4 — never an `if status ==` chain |
| OpenAPI dump script (`make openapi`) — writes `openapi.json` without starting a server | Gate 1 checklist |
| Generated `frontend/src/api/schema.d.ts` (`make gen-client`) | Gate 1 checklist |

**Gate 1 checklist** (`02-CRITICAL-PATH.md §4`) — walk this together before opening the PR:
- [ ] `make openapi` writes `openapi.json` without starting a server
- [ ] `make gen-client` regenerates `schema.d.ts` and `git diff --exit-code` is clean
- [ ] Every enum value in `04-CONTRACTS.md` matches `00-SPEC.md §2.3` exactly (plus the two documented A4/A5 supersets — no undocumented extras)
- [ ] Transition table is a data structure, not prose or an if-chain
- [ ] Both devs have signed off in the PR — **this is the last cheap moment to change the contract**. After this, any change needs a `chore/contract-*` PR, both reviewers, a `make gen-client` re-run, and a standup announcement.

Start from `dev` (current tip: `c05124b`). Branch name per `01-WORKFLOW.md §2.1` convention —
something like `feat/contract-freeze` or `chore/contract-freeze`, your call, but make it one
shared branch since this is joint work, not two competing PRs.

**Before you start, point your Claude Code session at the actual docs.** Tell it to read
`00-SPEC.md`, `01-WORKFLOW.md`, `02-CRITICAL-PATH.md §4` PHASE 1, and `04-CONTRACTS.md` in full
first. `04-CONTRACTS.md` already has most of the content written out — this is largely
transcription plus judgement calls on the open items below, not a from-scratch design task.

---

## 3. Open items Phase 1 needs to resolve (don't invent silently)

- `04-CONTRACTS.md §1`'s `TriagedBy` enum has two "superset" values (`LLM_GEMINI`, `SIMULATED`)
  marked as contradiction A4 against `00-SPEC.md §2.3`. Confirm both of us agree these stay before
  freezing — check `00-SPEC.md` Appendix A for the documented default assumption rather than
  re-litigating it from scratch.
- The unresolved `python` vs `python3` Makefile line (§1 above) — pick (a) or (b) and land it in
  this same PR or a quick prior one, since Phase 1 will lean on `make openapi`/`make gen-client`
  and a broken default invocation will cost time.
- If any other design fork shows up mid-Phase-1 (there will be at least one — enum supersets,
  pagination envelope shape, etc. all have ≥2 defensible answers), that's a `ponytail` moment per
  `CLAUDE.md §6` — invoke it right then, not at end-of-phase cleanup, and log it in
  `docs/AI-USAGE.md` the moment it happens.

---

## 4. Ground rules still in effect (from the Phase 0 handover, unchanged)

- `main` is protected — no direct pushes, not even admins. Branch → PR → `dev`, periodically
  `dev` → PR → `main`.
- PRs need a real review comment, not "LGTM" (`01-WORKFLOW.md §2.3`, Rubric A).
- Link every PR to an Issue (`Closes #N`).
- `CODEOWNERS` is live: `/backend/app/providers/` and `/backend/alembic/` → DEV-A;
  `/frontend/`, `/k8s/`, `/.github/workflows/` → DEV-B; `/backend/app/schemas/` and `/docs/adr/`
  need both.
- `caveman` at the start of Phase 1 (before writing any code), `ponytail` at every design fork,
  `grilled meat` before opening the Phase 1 PR — all three logged in `docs/AI-USAGE.md` at the
  moment they happen, not reconstructed afterward. See `CLAUDE.md §6` for the exact failure
  conditions on each (e.g. `grilled meat` needs ≥3 findings with `file:line`, not a rubber stamp).

---

## 5. What happens after Phase 1 lands

Per `02-CRITICAL-PATH.md §4`, PHASE 2 splits again: **A builds** the data layer (SQLAlchemy
models, Alembic migration `0001`, repository layer, idempotent seed ≥30 rows); **B builds** the
frontend scaffold (Vite + React 18 + TS, MSW handlers generated from the contract, both
Dockerfiles). This is also when `make check`'s `test-be` step should finally go green for real —
re-verify it once real `app/` code and tests exist, per the note in `docs/ENGINEERING-NOTES.md`.

---

*Drafted with Claude Code from the DEV-A side. Corrections/disagreements welcome — this reflects
my understanding of the current repo state and the docs, not a ruling.*
