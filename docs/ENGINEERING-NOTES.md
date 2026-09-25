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
