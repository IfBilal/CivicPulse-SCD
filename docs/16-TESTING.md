# 16 — TESTING STRATEGY (the consolidated matrix)

> **Owner:** both · **Continuous** · **Rubric:** C7 (3), B5 (2), and the *evidence* for D, E, F, H, I
> Spec floors: **≥ 14 backend tests**, **coverage ≥ 65% on `app/`**, **≥ 5 meaningful frontend
> tests**, **all deterministic**. This file contains **96 backend tests and 11 frontend tests**.
> The floors are floors, not targets.

---

## 1. The three rules that govern every test here

1. **Deterministic by design, not by luck** (§2.5). No `time.sleep`, no real network, no
   re-run-until-green, no reliance on dict ordering or wall-clock. If a test needs time to pass, it
   fakes the clock. If it needs an LLM, it uses `SimulatedTriage`. If it needs a race, it uses
   explicit `asyncio` synchronisation, not a sleep.
   > *"If you find yourself writing `time.sleep()` in a test or re-running to get a pass, the design is
   > wrong and the pressure you are feeling is the point of the requirement."*
2. **Every test cites a clause.** Each test module opens with a docstring naming the `00-SPEC.md`
   section and the rubric line it defends. That is what makes `20-RUBRIC-TRACEABILITY.md`
   mechanical and what lets you answer *"which test proves that?"* instantly at viva.
3. **A test that cannot fail is not a test.** For every new test, `git stash` the implementation and
   confirm red. Put it in the PR checklist (`01-WORKFLOW.md §7`) because it is the single cheapest
   defence against tests that assert nothing.

---

## 2. Taxonomy and markers

```toml
markers = ["unit","integration","contract","slow"]
```

| Marker | Definition | Deps | Budget | Where it runs |
|---|---|---|---|---|
| `unit` | one function or class, no I/O | none | < 50 ms | every commit (pre-commit) |
| `contract` | asserts the frozen wire shape of `04-CONTRACTS.md` | in-process app | < 200 ms | every commit |
| `integration` | real Postgres + real Redis via testcontainers | containers | < 5 s | CI, and locally before a PR |
| `slow` | load-ish or multi-container | compose | < 60 s | CI `integration` job only |

```bash
pytest -m "unit or contract"        # the fast loop, ~4 s
pytest -m integration               # the honest loop, ~90 s
pytest                              # everything + coverage gate
```

**Why testcontainers and not SQLite.** SQLite has no native enums, no `gen_random_uuid()`, no
`timestamptz`, no `COUNT(*) OVER ()` semantics identical to PG, no advisory locks, and no
`CHECK` behaviour matching ours. Every one of those is load-bearing in `05-DATA-LAYER.md`. A
green SQLite suite against a Postgres production system is a false signal — which is precisely
§5.2 question 1's *"three things that differ between your laptop and a CI runner."*
`testcontainers[postgres,redis]` pinned to `postgres:16.4-alpine` and `redis:7.4.1-alpine` makes
the test environment **the same image as production**.

---

## 3. `conftest.py` — the fixture spine

```python
# backend/tests/conftest.py
@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16.4-alpine") as pg:
        yield pg

@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7.4.1-alpine") as r:
        yield r

@pytest.fixture(scope="session")
async def migrated_engine(pg_container):
    url = pg_container.get_connection_url().replace("psycopg2", "psycopg")
    cfg = AlembicConfig("alembic.ini"); cfg.set_main_option("sqlalchemy.url", url)
    alembic_upgrade(cfg, "head")                 # migrations, never metadata.create_all()
    engine = create_async_engine(url, poolclass=NullPool)
    yield engine
    await engine.dispose()

@pytest.fixture
async def session(migrated_engine):
    """Every test runs inside a transaction that is ROLLED BACK. Zero cross-test leakage."""
    conn = await migrated_engine.connect()
    trans = await conn.begin()
    s = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
    yield s
    await s.close(); await trans.rollback(); await conn.close()

@pytest.fixture
async def redis(redis_container):
    r = Redis.from_url(redis_container.get_connection_url(), decode_responses=True)
    await r.flushdb()                            # isolation; the DB is per-session
    yield r
    await r.aclose()

@pytest.fixture
def frozen_clock(monkeypatch):
    """Fake monotonic + wall clock. Replaces every sleep-based test in this suite."""
    t = {"now": 1_757_000_000.0}
    monkeypatch.setattr(time, "time", lambda: t["now"])
    monkeypatch.setattr(time, "monotonic", lambda: t["now"])
    return t                                     # tests do frozen_clock["now"] += 31

@pytest.fixture
async def app(migrated_engine, redis):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.state.redis = redis
    app.state.triage = SimulatedTriage(seed=1337)
    yield app
    app.dependency_overrides.clear()

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

# ── provider doubles ───────────────────────────────────────────────────────
class AlwaysRaises:
    name = "llm:groq"; calls = 0
    async def triage(self, text, location): 
        type(self).calls += 1; raise httpx.ConnectError("boom")
    async def aclose(self): ...

class CountingProvider:
    """Wraps SimulatedTriage and counts real invocations — proves cache behaviour."""
    def __init__(self): self.calls = 0; self._inner = SimulatedTriage(seed=7)
    async def triage(self, text, location):
        self.calls += 1; return await self._inner.triage(text, location)
```

**The rollback-per-test transaction fixture is the single most important line in this file.** It
makes tests order-independent and parallel-safe without truncating tables, and it means a test
that forgets to clean up cannot poison the next one. Combined with `flushdb` on Redis, every test
starts from a known state in single-digit milliseconds.

---

## 4. The backend matrix

### 4.1 Domain and state machine — `unit` (20 tests)

| ID | Test | Asserts | Rubric |
|---|---|---|---|
| C-T01…C-T16 | `test_transition[src-dst]` ×16 | the **full 4×4 matrix** of `04-CONTRACTS.md §3`: 4 allowed → `True`, 12 denied → `False` | C3 |
| C-T17 | `test_terminal_states_have_no_successors` | `TRANSITIONS[RESOLVED] == TRANSITIONS[REJECTED] == frozenset()` | C3 |
| C-T18 | `test_transition_table_covers_every_status` | `set(TRANSITIONS) == set(Status)` — a new enum member without a table entry is a **KeyError at import**, not a runtime 500 | C3 |
| C-T19 | `test_no_if_chain_in_service` | AST scan: `change_status` contains no `Compare` node against a `Status` literal | C3 |
| C-T20 | `test_allowed_from_current_is_sorted_and_serialisable` | the 409 payload's hint list | C1 |

```python
ALL = list(Status)
@pytest.mark.parametrize("src,dst", [(s, d) for s in ALL for d in ALL])
def test_transition_matrix(src, dst):
    expected = (src, dst) in {(OPEN, IN_PROGRESS), (OPEN, REJECTED),
                              (IN_PROGRESS, RESOLVED), (IN_PROGRESS, REJECTED)}
    assert is_allowed(src, dst) is expected
```
Sixteen cases from four lines. C-T18 is the one that earns its keep: it converts *"we documented the
table"* into *"the table cannot be incomplete."*

### 4.2 Data layer — `integration` (16 tests)
Full list in `05-DATA-LAYER.md §8` (D1–D11, with D11 expanding to six seed tests). Summary:
migration round trip incl. `DROP TYPE`, empty autogenerate diff, no DDL in `app/`, DB-level
CHECK on `text`, enum rejects unknown category, `updated_at` trigger fires on raw UPDATE, single
statement for page+total, pagination boundaries, atomic conditional transition, indexes exist, and
the six seed tests (idempotent, ≥30, category spread, priority spread, constraint-clean, stable ids).

### 4.3 Backend core — `unit` + `integration` (14 tests)

| ID | Test | Asserts | Rubric |
|---|---|---|---|
| C-C01 | `test_settings_extra_forbid` | `TRIAGE_PROVDER=llm` ⇒ `ValidationError` at boot | C |
| C-C02 | `test_settings_repr_redacts_key` | `gsk_` absent from `repr` **and** `model_dump_json` | F, §5.3 |
| C-C03 | `test_llm_provider_requires_key` | `TRIAGE_PROVIDER=llm` with empty key ⇒ startup fails | F |
| C-C04 | `test_request_id_generated_when_absent` | UUID4 in `X-Request-ID` | C5 |
| C-C05 | `test_request_id_echoed_when_valid` | round-trips the client's id | C5 |
| C-C06 | `test_request_id_hostile_input` | `"x\nlevel=ERROR"` discarded, new id generated | C5 |
| C-C07 | `test_request_id_in_every_log_line` | `caplog` — all records carry the id, including from 3 awaits deep | C5 |
| C-C08 | `test_logs_are_json_to_stdout` | every captured line parses as JSON; **no `FileHandler` on any logger** | C5 |
| C-C09 | `test_uvicorn_access_logger_hijacked` | `logging.getLogger("uvicorn.access").handlers == []` | C5 |
| C-C10 | `test_middleware_order_is_contractual` | `app.user_middleware` class order matches `06-BACKEND-CORE.md §3` | C |
| C-C11 | `test_health_ok_with_db_down` | session factory raises ⇒ `/health` still **200** | **C4** |
| C-C12 | `test_health_module_imports` | AST of `routes/health.py` imports nothing from `db`/`repositories` | **C4** |
| C-C13 | `test_ready_503_names_postgres` | body `details.failed == ["postgres"]` | **C4** |
| C-C14 | `test_ready_checks_run_concurrently` | both checks stall 1.9 s ⇒ total < 2.5 s, not 3.8 s | C4 |

### 4.4 Shutdown — `slow` (3 tests)

| ID | Test | Asserts | Rubric |
|---|---|---|---|
| C-S01 | `test_sigterm_drains_inflight` | in-flight POST returns 201; process exits **0**, not SIGKILL | **C6** |
| C-S02 | `test_ready_flips_false_before_drain` | `/ready` → 503 while `/health` still 200 during shutdown | C6 |
| C-S03 | `test_exec_form_cmd_pid1` | `docker compose exec backend ps -o pid,comm` ⇒ PID 1 is `uvicorn`, **not `sh`** | C6, G |

C-S03 is a one-line test that defends the whole graceful-shutdown story: shell-form `CMD` makes
`sh` PID 1 and SIGTERM is never forwarded (`12-DOCKER-COMPOSE.md §1`).

### 4.5 API / contract — `contract` (19 tests)
The ten in `04-CONTRACTS.md §9` plus the nine endpoint-behaviour tests in `07-BACKEND-API.md §7`
(201 shape, field-level 400, 404 on unknown and on non-UUID, filter AND/OR semantics, page_size
boundaries 1/100/0/101, `total` present, empty page is 200, `Location` header, 409 names the
transition, concurrent transition one-wins).

### 4.6 AI layer — `unit` + `integration` (24 tests)
**F1–F24 in `08-AI-TRIAGE.md §8`.** F1 is the spec-mandated one and is the first test in the file.

### 4.7 Cache and rate limiting — `integration` (17 tests)
**E1–E17 in `09-CACHE-RATELIMIT.md §6`.**

### 4.8 Observability — `unit` (8 tests)
The eight in `10-OBSERVABILITY.md §7`, including the cardinality test that asserts a UUID never
appears as a `path_template` label value.

### 4.9 Totals

| Group | Count |
|---|---|
| Domain / state machine | 20 |
| Data layer | 16 |
| Backend core | 14 |
| Shutdown | 3 |
| API / contract | 19 |
| AI layer | 24 |
| Cache / rate limit | 17 |
| Observability | 8 |
| **Backend total** | **121** |
| Frontend (Vitest) | 11 |

> Rubric C asks for ≥ 14. Delivering 121 is not padding — each one maps to a distinct clause, and
> the mapping is in `20-RUBRIC-TRACEABILITY.md`. **What the viva will ask is not "how many" but
> "show me the test for X".** Being able to answer that in five seconds for any X is the deliverable.

---

## 5. Failure-injection catalogue

Every failure mode the spec mentions has a deterministic double. This table is the bridge between
§2.5's prose and the suite.

| Spec failure | Double | Expected behaviour | Test |
|---|---|---|---|
| provider raises | `AlwaysRaises` | 201, `rules:fallback`, 1 WARNING | F1, F20 |
| provider returns prose | `FailureMode.MALFORMED` | `ValidationError` ⇒ fallback, **0 retries** | F2 |
| category outside enum | `BAD_ENUM` | rejected by `Category`, fallback | F3 |
| 400-char "one-line" summary | `OVERLONG_SUMMARY` | rejected by `max_length=140`, fallback | F4 |
| provider 429 | `RATE_LIMIT` | **exactly 1** retry with jitter, then fallback | F5 |
| provider 5xx | `SERVER_ERROR` | exactly 1 retry | F6 |
| provider 400 | `raise APIStatusError(400)` | **0** retries | F7 |
| provider hangs | `TIMEOUT` (20 s stall) | abandoned ≤ 10 s | F8 |
| injection obeyed by model | `INJECTION_OBEY` | schema rejects it | F15 |
| Redis down (cache) | `redis.aclose()` then call | 200, `X-Cache: MISS` | E7 |
| Redis down (limiter) | same | 201 with `triaged_by="rules"` (fail-open bounded) | E16 |
| Postgres down | stop the container | `/health` 200, `/ready` 503 naming postgres | C-C11, C-C13 |
| two operators race | `asyncio.gather` on two PATCHes | one 200, one 409 | D9 |
| pod killed mid-window | limiter TTL assertion | TTL always > 0 (Lua atomicity) | E12 |

---

## 6. Frontend tests (Vitest + Testing Library + MSW)

The seven in `11-FRONTEND.md §6` plus four:

| # | Test | Asserts |
|---|---|---|
| 8 | `Api.client.test.ts` | non-2xx ⇒ `ApiError` carrying the parsed envelope, not a raw `Response` |
| 9 | `Api.requestId.test.ts` | every outbound request carries a fresh `x-request-id` |
| 10 | `Submit.extraField.test.tsx` | a 400 with two `fields[]` entries renders **both** inline messages |
| 11 | `Stats.zeroBuckets.test.tsx` | a category with count 0 still renders a labelled bar |

**MSW handlers are generated from the same `openapi.json`** the TS types come from, so a mock that
drifts from the contract is impossible. Mocking `client.ts` instead would test the mock — say that
in the PR.

Frontend coverage is **reported but not gated**: the spec gates backend coverage only, and a
coverage gate on presentational components incentivises snapshot padding.

---

## 7. Coverage policy

```toml
addopts = "--cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=65"
[tool.coverage.run]
branch = true
omit = ["app/cli/*", "alembic/*"]
```

| Decision | Reason |
|---|---|
| Gate in `pyproject.toml`, not in the workflow | The gate then applies locally too. A rubric number that only exists in CI is discovered at the worst moment |
| `branch = true` | Line coverage on the retry ladder is misleading — the interesting thing is whether the `except RETRYABLE` **branch** was taken |
| `omit` CLI and alembic | The seed CLI is covered by its own integration tests; migrations are covered by D1/D2. Counting migration lines would inflate the number without adding signal |
| 65%, not 90% | It is the spec's number. **Do not chase a higher number by testing getters.** Point coverage at the retry ladder, the state machine and the error handlers — measured by `--cov-report=term-missing`, the uncovered lines should be boilerplate, never a decision branch |

**The one coverage assertion worth adding by hand:**

```python
def test_critical_paths_fully_covered():
    """The fallback ladder and the transition table must be 100%, whatever the global number is."""
    data = coverage.CoverageData(); data.read_file("backend/.coverage")
    for path in ("app/services/triage_service.py", "app/domain/transitions.py"):
        missing = analyse_missing(data, path)
        assert not missing, f"{path} has uncovered lines {missing}"
```
A global 65% that leaves the fallback path untested would satisfy the rubric and miss the point.

---

## 8. Anti-flake rules (§2.5, enforced)

| Banned | Use instead |
|---|---|
| `time.sleep(n)` | `frozen_clock["now"] += n` |
| real HTTP to any provider | `SimulatedTriage` / `respx` for transport-level tests |
| `datetime.now()` in an assertion | inject a clock, or assert a range |
| relying on DB row order | explicit `ORDER BY` in the test's own query |
| `assert len(x) > 0` | assert the exact expected collection |
| `pytest-randomly` disabled to "fix" a failure | fix the shared state; random order is a **feature** |
| retrying a flaky test in CI | delete or fix it — *"a flaky pipeline trains a team to ignore red"* |

```bash
# Flake detector — run once before submission, commit the output
pytest -p no:randomly -q            # fixed order
pytest -q --count=5                 # pytest-repeat, 5× each
for i in 1 2 3; do pytest -q -x || echo "FLAKE on run $i"; done \
  | tee docs/evidence/test-stability.txt
```
Three consecutive clean full runs is the bar. Anything less and you have an undiscovered
dependency on order, clock or network.

---

## 9. Where each test runs

| Suite | pre-commit | `ci.yml` | `cd.yml` | local before PR |
|---|---|---|---|---|
| `unit` + `contract` | ✅ | ✅ `test-backend` | ✅ (reused) | ✅ |
| `integration` (testcontainers) | ❌ (too slow) | ✅ `test-backend` | ✅ | ✅ |
| `slow` (compose) | ❌ | ✅ `integration` | ✅ | before a phase gate |
| Vitest | ❌ | ✅ `test-frontend` | ✅ | ✅ |
| k6 load | ❌ | ❌ | ❌ | manual, Phase 7 |
| k6 rollout (`rate==0`) | ❌ | ❌ | optional | manual, Phase 8 |

k6 stays out of CI deliberately: a load test in a PR pipeline is a slow, noisy, runner-dependent
signal that will eventually go red for reasons unrelated to the change. It belongs in a scheduled or
manual workflow. Saying *why* something is **not** automated is as much a maturity signal as
automating it.
