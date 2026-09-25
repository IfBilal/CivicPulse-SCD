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

## DEV-B · Phase 2 · Views built now against MSW (not placeholders)

*ponytail record, 2026-09-23, `feat/fe-scaffold`.* The Phase 2 handover scopes the frontend to a
scaffold with placeholder pages; DEV-B asked for the complete designed frontend now.
**Chosen:** build Submit / Dashboard / Stats fully against MSW handlers typed off `schema.d.ts`,
with the §6 component tests. Phase 4 becomes "turn MSW off, point at the live API, fix what the
real backend disagrees with". **Rejected:** (a) placeholders now, views in Phase 4 — the spec's
order, but puts all Rubric B UI risk into the same days as the AI-triage crunch; (b) views against
the live backend only — impossible until Phase 3, and loses the zero-network test harness.

## DEV-B · Phase 2 · The fake server lives in `frontend/mocks/`, outside `src/`

*ponytail record.* MSW needs a stand-in backend that can return a realistic 409, which means some
copy of the transition rule. **Chosen:** `frontend/mocks/fakeServer.ts`, outside `src/`, loaded
only in `vite --mode mock` and tests; production builds tree-shake it out (verified: no `msw` in
`dist/`). The app code in `src/` holds zero rules — enforced by ESLint `no-restricted-syntax`, the
`make lint` grep, and `tests/client.test.ts`. **Rejected:** (a) mocks under `src/mocks` — trips the
HARD-rule-9 grep and blurs "app" vs "test double"; (b) a mock that accepts every transition —
then the verbatim-409 UX can't be exercised by hand at all.

## DEV-B · Phase 2 · Validation bounds come from a copy of `openapi.json`

*ponytail record.* `11-FRONTEND.md §3.1` wants client bounds read from the generated schema, but
`schema.d.ts` is types only — `minLength` doesn't exist at runtime. **Chosen:** `make gen-client`
also copies `openapi.json` to `frontend/src/api/openapi.json`; `api/schemaMeta.ts` reads bounds
and enum members from it (and throws if they're missing). The CI drift gate diffs the copy too.
**Rejected:** (a) importing `../../openapi.json` across the package boundary — breaks the Vite dev
server's fs allow-list and couples the image to the repo layout; (b) hand-typed constants — the
exact drift §2.1 forbids.

## DEV-B · Phase 2 · `openapi-typescript --empty-objects-unknown`

Found while building the Dashboard: Pydantic's `dict[str, Any]` (`ErrorBody.details`,
`FieldError.constraint`) is emitted as `{"type":"object"}` and openapi-typescript's default renders
that as `Record<string, never>` — no code could read `details.terminal` from a 409 type-safely.
The flag renders it `Record<string, unknown>`. Generator config only: `openapi.json` is
byte-identical, 2 lines of `schema.d.ts` change. Not a contract change.

## DEV-B · Phase 2 · nginx resolves the backend per request, upstream set at boot

*ponytail record.* `11-FRONTEND.md §2.1` has `proxy_pass http://backend:8000/api/;` — a literal
host is resolved once at startup, so nginx **exits** if `backend` isn't resolvable yet (standalone
`docker run` for the build-once-deploy-many evidence, compose restarts, k8s rollouts), and nginx's
resolver ignores DNS search domains, so the short name fails inside Kubernetes.
**Chosen:** `proxy_pass http://$backend_upstream;` with `resolver` taken from `/etc/resolv.conf`
and `BACKEND_UPSTREAM` (default `backend:8000`; k8s sets the FQDN) written at boot by
`10-config.sh`, which validates every value before writing it (config.js is served to browsers).
**Rejected:** (a) the spec's static `proxy_pass` — crash-on-boot coupling; (b) a hard-coded
`resolver 127.0.0.11` (Docker's DNS) — wrong inside Kubernetes.

## DEV-B · Phase 2 · Build context = repo root, per-Dockerfile ignore files

`12-DOCKER-COMPOSE.md §3` builds both images with `context: .`, so `backend/.dockerignore` and
`frontend/.dockerignore` (as `§2` names them) would be **silently ignored** — Docker only reads the
ignore file at the context root. Used BuildKit's `<Dockerfile>.dockerignore` convention instead:
`backend/Dockerfile.dockerignore`, `frontend/Dockerfile.dockerignore`, both allow-lists. Also fixed
a spec bug: Dockerfiles do not support trailing comments, so the spec's
`COPY a b ./   # deps BEFORE source` would copy files named `#`, `deps`, … and fail.

## DEV-B · Phase 2 · Palette validated, not eyeballed

Category hues are OKLCH-generated inside the dark-mode lightness band (L 0.60–0.66, C ≥ 0.13) and
run through a CVD/contrast validator: all checks pass; the one adjacent pair in the 6–8 ΔE CVD
floor (sanitation/electricity, protan) is legal because every bar and chip also carries its text
label and icon — colour is never the only channel.
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

**Resolved, 2026-09-24:** the authoring sandbox has no Docker, so the integration suite
couldn't run live there — closed instead via CI. Added a `data-layer` job to
`.github/workflows/ci.yml` (GitHub-hosted `ubuntu-24.04` runners have Docker preinstalled, so
`testcontainers` works with zero extra setup). The full D1, D2, D4–D10, seed-D11 matrix — 16
tests — now runs against a real `postgres:16-alpine` container on every push and is green:
run `35973640707`, 16 passed, 0 failed. This surfaced two real bugs that no static check could
have caught (both fixed, both now covered by a regression test):

1. **Missing `values_callable` on every `PGEnum` column** (`app/db/models.py`) — without it,
   SQLAlchemy serialises a Python `Enum` member by `.name` ("STREETLIGHTS") instead of `.value`
   ("streetlights"), but the migration's `CREATE TYPE` statements only define the lowercase
   wire values. Every INSERT/UPDATE would have raised `InvalidTextRepresentation` — this would
   have broken Phase 3's very first `POST /api/complaints` the moment it touched a real
   database. Added `test_orm_enum_columns_round_trip_by_value`.
2. **`alembic/env.py` reads `app.settings.settings.database_url`, a module-level singleton
   instantiated once at first import** — pytest imports every collected test module during
   collection, before any fixture runs, so setting `DATABASE_URL` in a fixture body was too
   late. Fixed by mutating the already-instantiated `settings` object's field directly in the
   test fixtures, rather than depending on env var read timing.

The remaining `EXPLAIN (ANALYZE, BUFFERS)` before/after capture
(`docs/evidence/explain-q-dash-filter.txt`) is still outstanding — that's an evidence artefact
for the Gate 2 checklist, not a test, and needs a `psql` session against a running container.
Next action: `make up && make seed`, then run the two `EXPLAIN` queries above by hand and
`tee` the output.

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

---

## DEV-A · `scripts/check_submission.py`'s `RUBRIC-TESTS` check always reports 0

Found while verifying the Phase 2 data-layer PR didn't regress `check_submission.py`.
`rubric_tests()` runs `python3 -m pytest --collect-only -q` and counts `"::"` occurrences in
stdout to estimate the test count. This project's `backend/pyproject.toml` enables
`pytest-cov` by default via `addopts`, and `pytest-cov` rewrites `--collect-only -q`'s output
format from the usual per-test `path::test_name` lines into per-**file** summary lines
(`tests/unit/test_enums.py: 5`) with no `::` anywhere in the output. The count is therefore
always 0, regardless of how many tests actually exist — confirmed: 65 real tests exist in
`backend/tests/` as of this branch, and the check still reports `0 backend tests collected,
floor is 14`.

Not silently patched — this is DEV-B's/joint territory (`scripts/check_submission.py` was
authored in `chore/scripts-check-submission`, PR #14) and the fix touches a shared detector,
not app code. **Recommendation:** either add `-p no:cacheprovider --no-cov` to the collect
invocation (bypasses the coverage plugin's output rewrite) or switch to `pytest --collect-only
-q --no-header` and count lines matching a test-id regex instead of a bare `"::"` substring
search. **Status:** flagged, not fixed — decide together before this becomes a real
`RUBRIC-TESTS` false negative at a gate review.

## DEV-B · Phase 2 · `nginx:1.27.2-alpine` → `-alpine-slim` (real Docker build, 2026-09-24)

Once Docker actually worked on this machine, the frontend runtime image measured **81.7 MB**,
over `11-FRONTEND.md §5`'s own "~60 MB means the split isn't doing its job" line — despite the
multi-stage split working correctly (`/usr/share/nginx/html` is 1.2 MB; no `node`/`npm` in the
final image). The gap was the base image itself: `nginx:1.27.2-alpine` bundles GeoIP/XSLT/
image-filter/njs dynamic modules (one ~37.5 MB layer) that `frontend/nginx.conf` never loads.
**Fixed**: switched to nginx's own `-alpine-slim` variant (same nginx build, no unused dynamic
modules) — confirmed it still ships `wget` (used by `HEALTHCHECK`), `adduser`/`addgroup`/`su`
(used to create the non-root user), and the `docker-entrypoint.d/` mechanism. Runtime image is
now **29 MB**. No functional change; still pinned to an exact tag, never `:latest` or bare
`:alpine`.

Also verified end-to-end with real containers (previously only estimated): both images build
clean via `docker build --target <stage>`; both run as the non-root `app` user; `/healthz`
returns 200 and the Docker `HEALTHCHECK` reports `healthy`; `docs/evidence/runtime-config.txt`
captures the same image digest serving two different `config.js` outputs under `APP_ENV=dev`
vs `APP_ENV=prod` — the build-once-deploy-many proof ADR-0002 describes, now with a live
digest instead of a description. `docs/evidence/dockerignore-context-sizes.txt` was also
re-measured for real (`docker buildx`'s own "transferring context" figure, not the earlier tar
estimate — Docker was previously broken on this dev machine, a system-level AppArmor/user-
namespace issue, fixed by a reboot + restarting the docker snap service, unrelated to the repo).

---

## DEV-B · Phase 3 · `compose.yaml`/`compose.prod.yaml`, Gate-3 evidence captured against a
stubbed backend

`backend/app/routes/ops.py` still `raise NotImplementedError` on `/health` and `/ready` (DEV-A's
Phase 3, running in parallel on a separate branch, not this branch's scope per the handover).
`compose.yaml`'s `depends_on: backend: {condition: service_healthy}` on `frontend` means a plain
`docker compose up --wait` cannot complete yet — `backend` never reports healthy, so `frontend`
is created but never started, and `make up`'s `--wait` flag would hang/fail on a clean checkout
of this branch alone.

This does not indicate a defect in the compose topology. Verified independently:
- `docker compose config` parses both files clean.
- `docker compose build` produces both images real.
- `database` and `cache` reach `healthy` on their own (no dependency on backend).
- Attached-network check: `frontend` → `edge` only, `database`/`cache` → `internal` only,
  `backend` → both (`docker inspect ... | jq keys`), matching `12-DOCKER-COMPOSE.md §4`.
- Both Gate-3/DEV-B evidence items were captured for real by starting the already-*created*
  (but not yet started) `frontend`/`backend` containers directly with `docker start <name>`,
  bypassing only the compose-level start-ordering wait — no edit to `compose.yaml` (see
  `AI-USAGE.md`'s ponytail entry for the alternatives rejected):
  - `docs/evidence/network-isolation.txt`: `frontend` cannot resolve or reach `database:5432`
    (`ping: bad address`, `nc: bad address`, exit 1); `backend` can (`socket.create_connection`
    exit 0 — used in place of `nc`, which the minimal backend image deliberately doesn't ship).
  - `docs/evidence/persistence-compose.txt`: seeded 36 rows, `docker compose down` (volumes
    kept) `&& docker compose up -d`, row count still 36 after. `backend` itself is `unhealthy`
    in this capture (expected, stub-driven) — `database`/`cache`/`frontend` health confirmed
    independently in the same file.

**Once DEV-A's `/health`/`/ready` land, this workaround stops being necessary** — `make up`'s
plain `--wait` will pass without manual intervention, and the full Gate-3 script in
`12-DOCKER-COMPOSE.md §9` (the rows outside DEV-B's two — all ten endpoints, `/health`/`/ready`
status codes, SIGTERM drain) is DEV-A's to close out, not re-run here.

---

## DEV-B · `make lint-localhost` silently passes right now regardless of match

Found while running the deduction-armour targets against the new `compose.yaml`. The recipe is
`@! grep -rnI ... backend/app compose.yaml compose.prod.yaml k8s/ || (echo FAIL; exit 1)`.
`k8s/` doesn't exist yet (Phase 6 hasn't started), so `grep` exits **2** (path error), not 0/1.
Bash's `!` treats any nonzero as false and negates it to true, so `! grep` evaluates to exit 0
regardless of whether real matches were found, and the `||` FAIL branch never runs. Confirmed:
`compose.yaml`'s two intentional `127.0.0.1` self-healthcheck lines (correct, per
`12-DOCKER-COMPOSE.md §1`/`§3` — a container checking itself, not a service-to-service call) are
real matches, printed to stdout, and the target still reports success either way. Not specific
to those two correct lines — **any** real service-to-service `localhost` violation introduced
between now and Phase 6 would be masked the same way, silently, until `k8s/` is scaffolded.

Not fixed here — shared `Makefile` territory (like the `check_submission.py` pytest-cov note
above), and the fix is a judgment call (create `k8s/.gitkeep` now vs. loop per-path so a missing
directory can't swallow a real hit vs. `mkdir -p` guard in the recipe). Flagging for whoever
touches `Makefile` next, ideally before Phase 6 lands anything under `k8s/` for real.

---

## DEV-A · Phase 3 — `ReadyOut.status` is `"ok"`, not `"ready"`

`06-BACKEND-CORE.md §5`'s prose example for `/ready` shows `status="ready"`, but the frozen
schema (`backend/app/schemas/health.py`, written and merged at Phase 1) declares
`status: Literal["ok"]`. Per `CLAUDE.md`'s source-of-truth order, `04-CONTRACTS.md` (and the
schema files that implement its frozen surface) outrank a design doc's prose example. Implemented
`/ready` against `"ok"` as written in the schema; not silently reconciling the design-doc example
to match, since `06-BACKEND-CORE.md §5` itself is now a documented bug rather than a followed
instruction — flagging it here per `CLAUDE.md`'s "say so, don't quietly reconcile" rule.

## DEV-A · Phase 3 — `/ready`'s 503 now ships the `ErrorEnvelope`, not `ReadyOut`

Follow-up to the note above. The first pass of `/ready` returned a `ReadyOut`-shaped body
(`{"status":"ok","checks":{...}}`) on *both* 200 and 503, just flipping the status code on
failure. That satisfied `response_model=ReadyOut` and every test that existed at the time, but
it silently diverged from `04-CONTRACTS.md §6.8`, which specifies the 503 as the one
`ErrorEnvelope` shape used everywhere else — `{"error":{"code":"not_ready","message":...,
"request_id":...,"details":{"checks":{...},"failed":[...]}}}`. The route's own
`responses=errors(503)` OpenAPI declaration already documented `ErrorEnvelope` for that code;
the runtime body just didn't match it. `test_error_responses_use_envelope`
(`tests/contract/test_openapi.py`) only checks the *declared* schema, not what a route actually
returns at runtime, so this shipped without a red test.

Fixed by adding `NotReady` to `app/domain/errors.py` (carries `checks`/`failed`, no HTTP
status — same pattern as `InvalidTransition`/`RateLimited`) and a `_on_not_ready` handler in
`app/errors.py` that builds the contract's exact envelope. `routes/ops.py::ready()` now raises
`NotReady` on any failure (dependency check or draining) instead of hand-building a response —
which also brings it in line with CLAUDE.md §3's rule that routes never choose a status code,
only registered handlers do. Added `test_ready_503_is_error_envelope_shaped` asserting the
literal envelope fields, so a future regression back to the `ReadyOut`-on-503 shape goes red.
Practical consequence of the bug, for the record: the generated TS client types `/ready`'s 503
as `ErrorEnvelope` off the OpenAPI schema, so frontend code reading `error.request_id` on a 503
would have read `undefined` at runtime against the old body.

## DEV-A · Phase 3 — `SimulatedTriage`'s `malformed` mode raises, it doesn't return bad data

`TriageResult` (`app/schemas/triage.py`) is a Pydantic model with `category: Category` and
`priority: Priority` — both closed enums. There is no way to construct a "malformed"
`TriageResult` instance; any attempt to build one with an invalid category/priority raises a
`ValidationError` at construction time, which is exactly the class of failure a real LLM
provider returning bad JSON would surface once its raw response is parsed into `TriageResult`.
So `SimulatedTriage(mode="malformed")` raises `SimulatedTriageError` immediately, standing in
for "the primary provider's output failed validation," rather than returning some
not-actually-a-`TriageResult` sentinel that would need an escape hatch in the type system to
exist. This keeps the provider's return type honest (`TriageProvider.triage` always returns a
real `TriageResult` or raises) and pushes the "is this a validation failure (no retry) vs. a
transient failure (one retry)" distinction to where it belongs — Phase 4's `TriageService`
retry/budget wrapper, which doesn't exist yet. For Phase 3, `ComplaintService.create()` treats
any exception from the primary provider identically: catch, fall back to `RuleBasedTriage`,
201. The no-retry-on-validation-failure behavior itself (CLAUDE.md HARD rule 6) is Phase 4
scope to prove with a real retry counter; Phase 3 proves only "primary raises → service catches
→ falls back → 201," which is what `test_fallback_emits_201_and_rules_fallback` in
`backend/tests/unit/test_complaint_service.py` asserts.

## DEV-A · Phase 3 — `stats_counts()` is four simple queries, not one `UNION ALL`

`07-BACKEND-API.md §5` shows the stats aggregation as a single statement: three `SELECT dim, k,
count(*)` branches `UNION ALL`'d together, then `jsonb_object_agg(...) FILTER (WHERE dim = ...)`
pivoted back out in the outer query. `ComplaintRepository.stats_counts()`
(`backend/app/repositories/complaint_repo.py`) instead issues four separate, simple statements:
`count(*)`, then one plain `GROUP BY` per dimension (category/priority/status).

**Rejected alternative — implement the spec's literal `UNION ALL` + `jsonb_object_agg` query:**
rejected for this phase because it trades one extra DB round trip (three round trips vs. four)
for a meaningfully harder-to-verify query — `jsonb_object_agg` returns JSON, which SQLAlchemy
doesn't type-check against `Category`/`Priority`/`Status` the way `dict(result.tuples().all())`
does from three ordinary `GROUP BY`s, and the FILTER-based pivot is the kind of SQL that's easy
to get subtly wrong (e.g. NULL handling per dimension) without integration-test coverage to
catch it — which this sandbox couldn't run (no Docker). Four straightforward statements are
strictly easier to reason about and match mypy strict cleanly.

**Chosen:** four statements now. `/api/stats` isn't in the hot path the way `POST
/api/complaints` is (it's cached — `09-CACHE-RATELIMIT.md`, Phase 5 — so the extra round trips
happen once per cache TTL window, not per request), so the cost of the simpler version is low.
Revisit if Phase 7's load test shows `/api/stats`'s cache-miss latency mattering; the return
type of `stats_counts()` doesn't need to change if the query is optimized later, since callers
(`StatsService.get()`) only see `(total, by_category, by_priority, by_status)`.

## DEV-A · Phase 3 — `RateLimitMiddleware` is an in-memory stub, not the Redis Lua limiter

`09-CACHE-RATELIMIT.md`'s distributed sliding-window Redis Lua rate limiter is explicitly
Phase 5 scope. This phase wires the middleware slot in the contractual position (innermost,
scoped to `POST /api/complaints` only) with a simple per-process in-memory fixed-window counter
gated on `settings.ratelimit_enabled`, so the *ordering* and *route-scoping* are provable now by
test without building distributed state a Phase 5 rewrite would discard anyway. The counter is
process-local and resets on restart — acceptable for proving middleware wiring, not acceptable
as the production limiter (a multi-pod deployment would let each pod's memory count
independently, undercounting the true rate by a factor of replica count). This limitation is
inherent to "stub now, build for real in Phase 5" and is not a Phase 3 defect.

---

## DEV-B · Phase 5 · real bug found running the full backend suite together in CI

Found while verifying `ci.yml`'s new `test-backend` job (`pytest`, whole suite, no marker
filter — `15-CICD.md §3.2`) for real, locally, before pushing it.

**`app/logging_config.py::configure_logging()`** (lines 63-77) unconditionally does
`for existing in list(root.handlers): root.removeHandler(existing)` on the **root** logger, with
no save/restore. Any test that constructs `TestClient(create_app())` calls this once per
process (app-factory startup), which strips **every** existing root handler — including
pytest's own `caplog` handler, which pytest attaches to the root logger to capture records.
Once any test creates the app, every *subsequent* test in the same process that asserts on
`caplog.records` silently gets zero records back, regardless of whether logging actually
happened.

**Reproduced:** `tests/unit/test_logging_config.py::test_fallback_emits_exactly_one_warning`
passes in isolation (`pytest tests/unit/test_logging_config.py -k fallback`) and fails
(`assert 0 == 1`, zero warnings captured) when run as part of the full suite — confirmed by
running the whole suite with `--no-cov` and isolating the failing test's traceback. This is
test-order-dependent state leakage via global logging config, exactly the class of bug
`CLAUDE.md` HARD rule 15 (never rely on shared mutable state across tests) exists to catch — it
just wasn't triggered before because nothing previously ran the **whole** suite together in one
process with **no `-m` filter** (the old `ci.yml`'s `contract` job ran `pytest -m "unit or
contract"`, a different subset/order that apparently never hit this exact interaction; the old
`data-layer` job ran a 16-test slice in isolation).

**Not fixed here** — `app/logging_config.py` is backend/app territory (DEV-A's), not something
this branch should touch per the project's layer/ownership split. Likely direction for whoever
picks it up: `configure_logging()` should only remove handlers it previously added itself (e.g.
tag them, or track the single handler instance across calls) rather than wiping the root
logger's entire handler list — or tests that call `create_app()` should snapshot/restore
`logging.getLogger().handlers` around the call. Flagging so `ci.yml`'s `test-backend` job (this
branch) isn't mistaken for broken when it shows this specific, understood, reproducible failure
— everything else in the full suite is green.

**Update, 2026-09-25, after merging `dev` (which now includes Phase 4, PR #33) into this
branch:** re-ran the full suite against the merged code. The bug is still present and now hits
**three** tests, not one — Phase 4 added its own `caplog`-based fallback-warning tests
(`tests/unit/services/test_triage_service.py::test_exactly_one_warning_per_fallback` and
`::test_no_extra_warning_on_retryable_then_fallback`), both hit by the identical root cause as
the original `test_logging_config.py::test_fallback_emits_exactly_one_warning`. Current numbers
on merged `dev`+this branch: **258 passed, 3 failed, 91.15% coverage** (floor 65%). This means
the bug is no longer just a latent risk this PR would expose — **`dev`'s own full suite already
fails today if run unfiltered**, independent of this branch. Worth surfacing to DEV-A directly,
not just left in this file, since it now affects tests he already merged.

## DEV-B · Phase 5 · branch protection only covers `main`, requiring a job that no longer exists

`main`'s ruleset (`main-protection`, id `23726494`) requires exactly one status check,
`bootstrap-check` — that job is removed/renamed in this PR's `ci.yml` (folded into
`lint-and-type`, per `15-CICD.md §2`'s "the seven job names go verbatim into branch
protection"). Left as-is, any future `dev`→`main` PR would hang forever on `bootstrap-check`
("Expected — waiting for status", `15-CICD.md §2` trap 2). Updated the ruleset's
`required_status_checks` to the new seven names after this PR's `ci.yml` ran once (so GitHub has
seen the contexts). Also noted, not changed: `dev` — the branch every PR in this project actually
targets — has **no** branch protection or required checks at all (`main`'s ruleset only applies
to the repo's default branch). Whether to also protect `dev` is a repo-wide workflow policy
decision, not something to change unilaterally inside a CI-scoped PR; flagging it here so it's a
deliberate choice, not an oversight nobody noticed.

---

## DEV-A · Phase 4 (AI triage) — ambiguities resolved before writing code

Written before the fallback-ladder implementation, per `CLAUDE.md §5` (say what you're choosing
and why, before the code, not after).

1. **RETRYABLE classification for `SimulatedTriage`'s failure modes.** `08-AI-TRIAGE.md §5`
   gives the RETRYABLE/NON_RETRYABLE tuples in terms of real exception types
   (`httpx.TimeoutException`, `RateLimitError`, `APIStatusError_5xx`, ...), but `SimulatedTriage`
   (§3.2) needs its own exception types per failure mode so the ladder can be exercised without
   any real HTTP stack. **Chosen:** `SimulatedRateLimitError`/`SimulatedServerError` are new,
   dedicated exception classes registered directly in `TriageService.RETRYABLE`;
   `SimulatedMalformedResponseError`/`SimulatedValidationError` are registered in
   `NON_RETRYABLE`. **Rejected:** (a) reusing `httpx.HTTPStatusError` inside `SimulatedTriage`
   itself — rejected because it would force the simulated provider to fabricate a fake
   `httpx.Request`/`Response` pair for a code path that has nothing to do with HTTP, coupling an
   in-process fake to a wire-protocol library; (b) classifying by string-matching the exception
   message — rejected as fragile and exactly the kind of stringly-typed logic `CLAUDE.md §3`
   warns against.
2. **`classify()`'s default for an unrecognised exception type.** The spec's RETRYABLE/
   NON_RETRYABLE tuples aren't exhaustive — `FailureMode.RAISE` deliberately raises a bare
   `RuntimeError`, which is neither. **Chosen:** treat anything unclassified as NON_RETRYABLE
   (straight to fallback, no retry) rather than RETRYABLE. **Reasoning:** CLAUDE.md HARD rule 5
   requires every path reach fallback regardless; routing unknown failures through NON_RETRYABLE
   gets there in one hop instead of burning a retry (and the associated jitter sleep) on a
   failure mode the ladder doesn't understand. **Rejected:** treating unknown exceptions as
   RETRYABLE — would silently double the latency of any genuinely novel provider bug for no
   benefit, since retrying an *unclassified* failure has no more reason to succeed than a
   classified NON_RETRYABLE one.
3. **`providers/triage/cache.py` vs `services/triage_cache.py`.** The task brief offered either
   path. **Chosen:** `providers/triage/cache.py`, because the module's job (Redis wire format,
   TTL, a third-party client shape) is exactly what `CLAUDE.md §3` scopes to `providers/`
   ("httpx, redis, third-party wire — external formats, isolated"); `services/` is business
   rules and orchestration order, which is `TriageService`'s job, not the cache's.
4. **Calling convention for `TriageProvider.triage`.** `08-AI-TRIAGE.md §1` writes
   `async def triage(self, text: str, location: str) -> TriageResult` (positional). **Chosen:**
   keyword-only, `triage(self, *, text: str, location: str)`, applied consistently across
   `RuleBasedTriage`/`SimulatedTriage`/`LLMTriage`/`OllamaTriage`/`TriageService`. **Reasoning:**
   two adjacent `str` parameters of the same type are a classic transposition hazard
   (`triage(location, text)` vs `triage(text, location)` both type-check and neither raises);
   keyword-only args make the mistake a `TypeError` at the call site instead of a silent
   mis-classification. This is the same category of deviation the spec itself pre-declares for
   `async` vs `def` — the *shape* of the contract (one method, text+location in, `TriageResult`
   out) is unchanged.
5. **Provider default on an unrecognised `TRIAGE_PROVIDER` value.** Written when this branch's
   own `Settings.triage_provider` was a plain `str` with no enum constraint, at which point
   `factory.py`'s `match` block had no `case _` and could receive any string. Original choice:
   fail closed to `RuleBasedTriage()` rather than raise at startup, on the reasoning that `rules`
   structurally cannot fail (`08-AI-TRIAGE.md §3.1`) and a config typo should degrade the
   classifier, not crash the boot.

   **Superseded, 2026-09-25, at the merge of Phase 3 into Phase 4:** Phase 3's
   `Settings.triage_provider` is typed `Literal["llm","ollama","rules","simulated"]`
   (`06-BACKEND-CORE.md §1`), which Pydantic validates at settings-construction time — an
   unrecognised value is already a `ValidationError` before `build_triage_provider` ever runs,
   making the `case _` branch above dead code once both phases' `Settings` classes were
   reconciled into one. **Re-decided, at the merge:** keep the `Literal` type and its fail-fast
   behavior rather than widening back to `str` — every other field in `Settings` (`extra=
   "forbid"`, `frozen=True`) already treats a config typo as a startup crash, not a silent
   degradation, and `TRIAGE_PROVIDER` following that same rule is more consistent than carving
   out one field to fail closed instead. The `case _` branch and its comment were removed from
   `factory.py`; `match` is now exhaustive over the `Literal`'s four values, which mypy can
   verify statically.

---

## DEV-B · Phase 5 · real HIGH/CRITICAL CVEs found by the new `scan` job — base images bumped

Found on the first real `scan` job run once `trivy-action` itself was working (see `AI-USAGE.md`).
Not a masking bug this time — genuine findings: **44 HIGH/CRITICAL** (40 HIGH, 4 CRITICAL) in the
backend image, all in OS packages (`gpgv`, `libgnutls30`, `libssl3`, `openssl`, ...), every one
with a `fixed` version already published. `python:3.12.7-slim-bookworm` was pinned back on
2024-12-03; Docker Hub's current build of that same Python line is `3.12.14-slim-bookworm`
(2026-09-19) — nearly two years of accumulated Debian security patches the pin never picked up.

**Fixed:** bumped `backend/Dockerfile`'s two `FROM python:3.12.7-slim-bookworm` lines to
`python:3.12.14-slim-bookworm` (same minor line, `12-DOCKER-COMPOSE.md §1`'s pinning discipline
unchanged — still an exact tag, never `:latest`/`:slim`/floating), and
`frontend/Dockerfile`'s runtime stage from `nginx:1.27.2-alpine-slim` to
`nginx:1.27.5-alpine-slim` (latest patch on the same 1.27 line). Rebuilt both locally: backend
imports clean (`python -c "import app.main"`), frontend serves `/healthz` and the
`docker-entrypoint.d` config script runs exactly as before — no functional change, only the OS
package versions underneath moved forward.

**Not fixed here, disclosed:** the scan also found `orjson==3.10.18` (4× HIGH,
`CVE-2025-67221`, unbounded-recursion DoS), fixed in `3.11.6`. `backend/pyproject.toml` pins
`orjson==3.10.*`, so picking up the fix means widening that constraint to `3.11.*` and
regenerating `requirements.lock` (`make lock`) — an actual Python dependency version change, in
`backend/pyproject.toml`, which is backend/app territory (DEV-A's, with two open PRs already
touching adjacent files) rather than the Dockerfile/base-image maintenance this branch owns.
Flagging for DEV-A or a joint follow-up; `scan`'s `HIGH,CRITICAL` gate will keep failing on this
one specific finding until then.
