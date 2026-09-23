# HANDOVER — Phase 2 kickoff, DEV-A → DEV-B

<!-- Written at session close, 2026-09-23. Delete this file in the Gate 2 merge commit. -->

## 0. Position
| | |
|---|---|
| Base | `dev` @ `816ee6f` (Gate 1 merged, PR #23) |
| Phase / Gate | **P2 — DATA (A) ∥ FE SCAFFOLD (B) → Gate 2** |
| From / To | DEV-A (T361) → DEV-B (IfBilal) |
| Split | Parallel, disjoint trees — safe per `02-CRITICAL-PATH.md §6` |

Gate 1 is closed: contract frozen, `openapi.json` + `schema.d.ts` generated, `domain/enums.py` +
`domain/transitions.py` merged (dict-based, HARD rule 4), all 10 routes are
`NotImplementedError` stubs. Nothing below that — models, repos, real routes, frontend app — has
landed. That's today's starting line.

---

## 1. What's on you — frontend scaffold only, not views

Spec: `docs/11-FRONTEND.md` §4 (client) + §5 (Dockerfile) **only** — §3 (Submit/Dashboard/Stats
views) is Phase 4, don't build it now, there's no live API to point it at yet.

Build: Vite+React18+TS scaffold (package.json/schema.d.ts already exist from Gate 1 — don't
hand-edit `schema.d.ts`, it's `make gen-client` output) · router with empty placeholder pages ·
MSW handlers typed off `schema.d.ts` · `client.ts` (~60-line typed wrapper, `API_BASE = "/api"`,
never a baked-in URL — §5.3 −8) · error boundary (render-time only, shows last `X-Request-ID`) ·
both Dockerfiles, multi-stage, pinned, non-root (mind the 4 non-root nginx gotchas in §5) ·
`.dockerignore` ×2 with **measured** before/after context sizes → `docs/evidence/dockerignore-context-sizes.txt`.

**Gate 2 acceptance for you:** all three routes render against MSW, zero real network calls.
Don't touch `backend/app/domain/`, `openapi.json`, or `schema.d.ts` — any of those changing means
the contract changed, which is a `chore/contract-*` PR, not a Phase 2 edit.

---

## 2. What's on me — data layer

Spec: `docs/05-DATA-LAYER.md`. SQLAlchemy models (native PG enums, CHECK constraints, both
indexes) · Alembic env + hand-written migration `0001` (autogenerate mangles native enums/DESC
indexes/triggers) · repository layer, all SQL confined there · idempotent seed (UUIDv5 +
`ON CONFLICT DO NOTHING`, ≥30 rows). `backend/alembic/` is currently just a `.venv` dependency,
no project env initialized — that's my first task today.

If you need a model shape for MSW mocks, use `04-CONTRACTS.md`/`schema.d.ts`, not my ORM — the
ORM isn't the contract.

---

## 3. Where parallel stops being safe

Schema change (field added, enum value changed) after this point = `chore/contract-*` PR, both
review, `make gen-client` re-run, announced at standup — never slipped into a branch quietly.

---

## 4. Gate 2 checklist (`02-CRITICAL-PATH.md §4`)

- [ ] `alembic upgrade head && downgrade base && upgrade head` succeeds — mine
- [ ] `grep -rn "CREATE TABLE" backend/app/` returns nothing — mine
- [ ] `make seed && make seed` → identical count, ≥30 — mine
- [ ] `\d+ complaints` shows both named indexes — mine
- [ ] `docs/ENGINEERING-NOTES.md` has the named query per index — mine
- [ ] **Frontend renders all three routes against MSW, zero real network** — yours
- [ ] `docs/evidence/dockerignore-context-sizes.txt` has real numbers — yours

Don't open the `dev` PR until every line is actually checked, not "looks done."

---

## 5. Ground rules, unchanged

`main` stays protected. Two separate branches this time — mine `feat/data-layer`, yours
something like `feat/fe-scaffold`. `caveman` before either of us codes, `grilled meat` before
either PR, both logged in `docs/AI-USAGE.md` at the moment they run. Any ≥2-defensible-answer
fork (likely: MSW handler structure, or Dockerfile base image) is a `ponytail` moment — invoke it
live, don't rationalize after the fact. Cross-partner review only, never approve your own diff.

---

## 6. After Phase 2

Phase 3 splits again: I build the real backend API (all 10 route bodies, `/health`+`/ready`,
SIGTERM drain, state machine) — first phase the stubs stop raising `NotImplementedError`. You
build `compose.yaml`/`compose.prod.yaml` (2 networks, 3 volumes, healthchecks, isolation proof).

---

*Drafted with Claude Code, DEV-A side, at Phase 2 kickoff. Disagreements welcome — this is my
read of where we are, not a ruling on your half.*
