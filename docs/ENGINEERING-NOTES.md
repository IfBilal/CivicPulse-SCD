# Engineering Notes

Design decisions not fully covered by the numbered docs, written when the decision is made
(`CLAUDE.md §5`). Sections are H2-delimited; edit only your own per `01-WORKFLOW.md §3.2`.

---

## DEV-A · `make submission-check` uses `python`, not `python3`

`03-REPO-BOOTSTRAP.md §5`'s Makefile has `submission-check: ; python scripts/check_submission.py`
verbatim. On this dev machine (and likely others — Debian/Ubuntu-derived systems since Python 3
transition don't ship a bare `python` binary by default), `python` is not on `PATH`, only
`python3`. Running `make submission-check` fails with `python: command not found`, exit 127 —
not a bug in `scripts/check_submission.py` itself, which runs fine as `python3
scripts/check_submission.py`.

Per `CLAUDE.md`'s own precedence rule — *"If `00-SPEC.md` and an implementation doc disagree,
the implementation doc is a bug — say so, don't quietly reconcile them"* — this is exactly that
situation one level down: `03-REPO-BOOTSTRAP.md §5`'s Makefile line is portable-Python-unsafe.
Not silently patching the Makefile against the frozen bootstrap doc; flagging it here instead so
both devs decide together whether to:

(a) change the Makefile target to `python3 scripts/check_submission.py` (breaks nothing, `python3`
    is the correct invocation everywhere the assignment actually runs — CI runners, most Linux
    dev machines), or
(b) leave it and require every contributor to alias `python=python3` locally.

**Recommendation:** (a). No reason to keep a broken default when the fix is a one-word Makefile
edit and every other Makefile target in this repo already calls out to `docker compose`,
`kubectl`, etc. by their real binary names.

**Status:** unresolved — not fixed in `chore/be-submission-check` branch; deferred to whoever
merges next, since `Makefile` line is CODEOWNERS-neutral-ish territory (touches both DEV-A's
backend-tooling concern and the file DEV-B originally authored the stub of).

---

## DEV-A · `make check` is expected red until Phase 2 lands `app/` code

`02-CRITICAL-PATH.md §4` Gate 0 lists `make check` exits 0 on a clean clone as a checklist item.
As of this Phase 0 bootstrap slice, `make check` currently fails at the `test-be` leg: `pytest`
enforces `--cov-fail-under=65` (`backend/pyproject.toml`), and `backend/app/` contains only
`__init__.py` — zero statements, zero tests, so coverage is 0.00% and the run exits 1. `lint`
(ruff) and `type` (mypy) both pass cleanly once `backend/.venv` is activated.

This is not a bug to fix now — the 65% floor is Phase 5's target, written against code that
doesn't exist until Phase 2 (`02-CRITICAL-PATH.md §4` PHASE 2). Lowering or disabling the
coverage floor to force a green `make check` today would hide the real signal once `app/` has
code. Treating Gate 0's `make check` line as "passes lint+type cleanly; `test-be` is red for the
structural reason above, not a config or code defect" until Phase 2 adds the first real module
and test.

**Status:** documented per user decision (leave as-is), not patched. Re-verify `make check`
exits 0 for real once Phase 2 lands the first backend module + test.

---

## Phase 1 (joint) · Route bodies are stubs that raise `NotImplementedError` → 501

*ponytail record, 2026-09-23, `feat/contract-freeze`.* Phase 1 must produce the OpenAPI document
(and therefore every route signature), but Phase 3 (DEV-A) owns route/service implementation.
**Chosen:** real `routes/*.py` modules with final signatures, `operation_id`s and `responses=`,
bodies `raise NotImplementedError`, mapped to a `501 not_implemented` envelope by a registered
handler that Phase 3 deletes. **Rejected:** (a) a hand-written `openapi.yaml` as the source of
truth — two sources of truth that drift the moment Phase 3 edits a route, and loses FastAPI's
"schema is generated from the code" argument (§2.2); (b) implementing the endpoints now — pulls
Phase 3's data layer dependency into Phase 1 and blows the "Day 2 AM" budget.

## Phase 1 (joint) · One `ErrorEnvelope`, untyped `details`

*ponytail record, 2026-09-23.* **Chosen:** a single `ErrorEnvelope{error:{code,message,request_id,
fields?,details?}}` with `details: dict[str, Any]` for every non-2xx. The frontend has one error
renderer and shows `error.message` verbatim (Rubric B); the per-code `details` shapes (409
`from/to`, 429 `retry_after_seconds`, 503 `failed`) are pinned by contract tests instead of types.
**Rejected:** (a) one envelope model per status code — typed `details`, but five near-identical
models in `schema.d.ts` for a frontend that never branches on `details`; (b) RFC 7807
`application/problem+json` — standard, but `04-CONTRACTS.md §5` already fixes the shape and the
field-level `fields[]` list has no 7807 equivalent without an extension anyway.

## Phase 1 (joint) · Stats buckets are `dict[Enum, int]`, not per-member fields

*ponytail record, 2026-09-23.* **Chosen:** `by_category: dict[Category, int]` etc. Adding a category
stays a one-line enum edit. The "every bucket present even at zero" rule is enforced by the stats
service + its test (Phase 4), not by the type. **Rejected:** (a) explicit `CategoryCounts{water:int,
…}` models — the type guarantees every key, but duplicates each enum's members in a second place
that must be edited in lockstep; (b) a list of `{key, count}` pairs — chart-friendly but loses
O(1) lookup and diverges from the `04-CONTRACTS.md §6.5` example.

## Phase 1 (joint) · Empty `reporter_contact` normalises to `null`

*ponytail record, 2026-09-23.* An HTML form with an untouched optional field sends `""`.
**Chosen:** `""` (after strip) → `None`; anything non-empty must be email-ish or phone-ish.
**Rejected:** (a) reject `""` with a 400 — punishes the citizen for the frontend's form
serialisation; (b) accept any string ≤120 — `04-CONTRACTS.md §2` asks for a format check.

## Phase 1 (joint) · `gen-client` uses a minimal, locked `frontend/package.json` now

*ponytail record, 2026-09-23.* Gate 1 needs `make gen-client` to work, but the Vite scaffold is
Phase 2b. **Chosen:** a minimal `frontend/package.json` + `package-lock.json` pinning
`openapi-typescript@7.13.0` and its `typescript@5.9.3` peer; `make gen-client` runs `npm ci` then
`npx --no-install` so the generator can never be silently fetched at a different version (a
different generator version changes `schema.d.ts` and would make the CI drift gate flap).
Phase 2b (DEV-B) grows this same `package.json` rather than replacing it. The Makefile's frontend
`lint/type/test-fe` guards now key off `frontend/vite.config.ts` (the "scaffolded" marker) instead
of `test -d frontend`, and use `if/then/else` — the old `test -d … && (…) || echo skip` form
would have **swallowed real frontend lint/type/test failures** as a "skip" exit 0.
**Rejected:** (a) `npx --yes openapi-typescript@7.13.0` with no package.json — the top-level
version is pinned but its transitive deps float, so output can drift between CI runs;
(b) deferring `gen-client` to Phase 2b — leaves a Gate 1 box unchecked and lets the contract
freeze without the frontend ever compiling against it.

## Phase 1 (joint) · Makefile calls `python3`, not `python`

Resolves the DEV-A note above ("`make submission-check` uses `python`") with option (a):
`submission-check` and `openapi` now call `python3`. Inside an activated venv both names exist,
so nothing breaks; on stock Debian/Ubuntu the bare `python` doesn't.

---

## DEV-A · Phase 2 named queries for `ix_complaints_status_priority` and `ix_complaints_created_at`

Per `05-DATA-LAYER.md §4` — *"an unexplained index is cargo cult"*.

**`ix_complaints_status_priority` serves `Q-DASH-FILTER`** — the Dashboard's default operator
view (`GET /api/complaints?status=open&priority=high`):
```sql
SELECT c.*, COUNT(*) OVER () AS total_count
FROM complaints c
WHERE c.status = 'open' AND c.priority = 'high'
ORDER BY c.created_at DESC
LIMIT 20 OFFSET 0;
```
`status` leads because it's the highest-selectivity predicate an operator actually filters on
first (they live in `status='open'`); `priority` second lets `WHERE status=? AND priority=?`
stay a single index range scan while `WHERE status=?` alone still uses the leading column.

**`ix_complaints_created_at (DESC)` serves `Q-LIST-RECENT`** — the unfiltered dashboard page 1
and the stats time window:
```sql
SELECT * FROM complaints ORDER BY created_at DESC LIMIT 20;
```
`DESC` in the index lets the planner walk forward and stop at 20 with no sort node.

**Known gap, disclosed rather than hidden:** neither index helps deep `OFFSET` — `OFFSET 5000`
still walks 5000 rows. Irrelevant at this data volume; the honest fix would be keyset
pagination, rejected because `04-CONTRACTS.md`'s `page`/`page_size`/`total` envelope is frozen.

**Sandbox limitation, disclosed:** this session has no Docker/container runtime available, so
the actual `EXPLAIN (ANALYZE, BUFFERS)` before/after capture (`docs/evidence/explain-q-dash-filter.txt`)
and the full `alembic upgrade head && downgrade base && upgrade head` round trip were **not run
live** — only statically verified (ruff clean, mypy strict clean, `lint-layers` clean, migration
script imports and constructs without error, unit/contract suite green at 86% coverage). Every
integration test (D1, D2, D4–D10, seed D11) is written and collects cleanly, but fails at
runtime here with `docker.errors.DockerException` — no daemon, not a code defect. **Next action
for whoever has Docker:** `cd backend && pytest -m integration` once, and if green, capture the
EXPLAIN evidence with `psql` against the same container before closing Gate 2.

**Review findings, self-reviewed diff (no partner review pass yet — that still happens at PR
review per `CLAUDE.md §6` rule 5):**
1. `app/db/session.py` — `get_session()` had no rollback-on-exception; fixed, now rolls back and
   re-raises before the `async with` closes the session.
2. `app/cli/seed.py::main` — a CHECK-constraint violation during `make seed` raised a raw
   SQLAlchemy traceback with no operator-facing context; fixed, now rolls back and logs a
   one-line stderr note before re-raising.
3. **WONTFIX for this branch:** `app/repositories/complaint_repo.py::list_page` trusts
   `page`/`page_size` are already validated — a `page=0` or negative value produces a negative
   `OFFSET` and a raw DB error instead of a clean 400. Not fixed here because bounds validation
   belongs at the Pydantic/route layer (`domain/limits.py`'s `PAGE_MIN`/`PAGE_SIZE_MAX`), which
   is Phase 3 (routes) scope — adding a repository-layer guard now would duplicate that
   validation in two places. Flagging so Phase 3 explicitly clamps before calling `list_page`.
4. **WONTFIX for this branch:** `tests/integration/conftest.py::db_session`'s engine has no
   explicit `poolclass`, fine under serial pytest but a connection-exhaustion trap if the suite
   later runs under `pytest-xdist` against the single shared testcontainers instance. Not fixed
   now since nothing in this repo runs tests in parallel yet; revisit if that changes.
