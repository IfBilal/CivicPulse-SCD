# 06 — BACKEND CORE (FastAPI · lifespan · middleware · probes · shutdown)

> **Owner:** DEV-A · **Day:** 4 · **Gate:** Gate 3 · **Rubric:** C lines 2, 4, 5, 6 (11 marks)
> Everything here is infrastructure that the endpoints in `07-BACKEND-API.md` sit on top of.

---

## 1. Settings — the only place `os.environ` is read

```python
# backend/app/config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid", frozen=True)

    app_env: Literal["dev", "prod"] = "dev"
    version: str = "dev"                     # injected at build: ARG GIT_SHA
    log_level: Literal["DEBUG","INFO","WARNING","ERROR"] = "INFO"
    log_format: Literal["json","console"] = "json"

    database_url: PostgresDsn
    db_pool_size: int = 5
    db_max_overflow: int = 2
    db_pool_timeout_s: float = 5.0

    redis_url: RedisDsn

    triage_provider: Literal["llm","ollama","rules","simulated"] = "simulated"
    triage_timeout_s: float = 10.0
    triage_total_budget_ms: int = 12_000
    triage_max_retries: int = 1
    triage_retry_jitter_ms: int = 250
    triage_cache_ttl_s: int = 86_400
    triage_min_confidence: float = 0.35
    triage_ring_size: int = 20

    llm_base_url: AnyHttpUrl = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.1-8b-instant"
    llm_api_key: SecretStr = SecretStr("")     # ← SecretStr: never printed by repr()
    ollama_base_url: AnyHttpUrl = "http://ollama:11434"
    ollama_model: str = "llama3.2:1b"

    stats_cache_ttl_s: int = 30
    ratelimit_enabled: bool = True
    ratelimit_requests: int = 10
    ratelimit_window_s: int = 60
    trusted_proxy_hops: int = 1

    cors_allow_origins: list[AnyHttpUrl] = []
    prestop_drain_s: float = 5.0

    @model_validator(mode="after")
    def _llm_needs_key(self) -> "Settings":
        if self.triage_provider == "llm" and not self.llm_api_key.get_secret_value():
            raise ValueError("TRIAGE_PROVIDER=llm requires LLM_API_KEY")
        return self
```

Three properties that matter:

| Property | Consequence |
|---|---|
| `extra="forbid"` | A typo'd env var (`TRIAGE_PROVDER=llm`) is a **startup crash**, not a silent fall back to `simulated` in production. |
| `frozen=True` | No module can mutate settings at runtime. Configuration is immutable after boot, which is what makes `/api/meta/providers.configured` trustworthy. |
| `SecretStr` on the key | `repr(settings)`, a Pydantic `.model_dump()` in a log line, and a FastAPI validation-error dump all print `**********`. This is §2.5 item 6 (*"never log the API key"*) implemented as a type, not as discipline. |

Add `test_settings_repr_redacts_key` asserting `"gsk_" not in repr(settings)` and
`"gsk_" not in json.dumps(settings.model_dump())`.

---

## 2. Application factory and lifespan

```python
# backend/app/main.py — this file contains NO business logic and NO DDL
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings)
    app.state.ready = False
    app.state.started_at = time.monotonic()
    app.state.redis = Redis.from_url(str(settings.redis_url), decode_responses=True,
                                     socket_timeout=2, socket_connect_timeout=2,
                                     health_check_interval=30)
    app.state.triage = build_triage_provider(settings)      # factory, §08
    app.state.ring = TriageRing(maxlen=settings.triage_ring_size)
    app.state.ready = True
    log.info("startup.complete", extra={"provider": app.state.triage.name})
    try:
        yield
    finally:
        app.state.ready = False                              # ① flip readiness FIRST
        await asyncio.sleep(settings.prestop_drain_s)        # ② let endpoints drain
        await app.state.triage.aclose()
        await app.state.redis.aclose()
        await engine.dispose()                               # ③ close pool connections
        log.info("shutdown.complete")

def create_app() -> FastAPI:
    app = FastAPI(title="CivicPulse", version=settings.version,
                  lifespan=lifespan, servers=[{"url": "/"}],
                  default_response_class=ORJSONResponse)
    register_exception_handlers(app)
    register_middleware(app)
    register_routers(app)
    return app
```

**`alembic upgrade head` is absent from this file, deliberately.** Migrations run in `make up`, in the
CI integration job, and in the Kubernetes `initContainer`. §2.3 forbids schema DDL in application
startup code and Rubric D pays 4 marks for it.

**`app.state.ready` is the shutdown lever.** `/ready` reads it before it touches any dependency,
which is what makes the ordering in the `finally` block produce a zero-downtime rollout.

---

## 3. Middleware stack — order is a contract

Starlette runs middleware **outermost-first on the way in, innermost-first on the way out**.
Registered order (top = outermost):

```
1. RequestIDMiddleware      ← must be outermost: everything downstream logs the id
2. AccessLogMiddleware      ← needs the id; must see the final status code
3. PrometheusMiddleware     ← must see the final status code; must NOT measure /metrics
4. CORSMiddleware           ← must run before routing to answer OPTIONS preflight
5. RateLimitMiddleware      ← scoped to POST /api/complaints only (§04 6.1 ordering)
   └── router
```

| Position | Why not elsewhere |
|---|---|
| RequestID outermost | If the rate limiter rejects at 429, that response **still** needs `X-Request-ID` and that rejection **still** needs a log line with the id |
| AccessLog above Prometheus | Both need the status; log last-in-first-out so the log line is emitted after metrics are recorded and can include the observed duration |
| Prometheus skips `/metrics` | Otherwise the scrape measures itself and pollutes the latency histogram |
| RateLimit innermost | It needs the resolved path to know whether this is `POST /api/complaints`; and putting it outside CORS would make a preflight consume quota |

### 3.1 Request ID (Rubric C, 3 marks — *propagated* `request_id`)

```python
_request_id: ContextVar[str] = ContextVar("request_id", default="-")

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if _is_uuid4(incoming) else str(uuid.uuid4())
        token = _request_id.set(rid)
        request.state.request_id = rid
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(token)
        response.headers["X-Request-ID"] = rid
        return response
```

`ContextVar` rather than a thread-local: async tasks inherit the context, so a log line emitted
inside `TriageService` — three awaits deep — carries the id with **no parameter threading**. That is
what "propagated" means, and it is worth saying in the viva.

**Validate the inbound id.** Echoing arbitrary client input into every log line is a log-injection
vector (`\n` in a header → forged log records). Accept only a well-formed UUIDv4; otherwise
generate. `test_request_id_hostile_input` asserts a header of `"x\nlevel=ERROR"` is discarded.

Propagation continues **outbound**: the LLM HTTP client sends `X-Request-ID: <rid>` too, so a
provider-side trace can be correlated. Costs one line, looks professional.

### 3.2 Structured logging (Rubric C, 3 marks — *JSON to stdout*)

```python
class JsonFormatter(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": r.levelname, "logger": r.name, "msg": r.getMessage(),
            "request_id": _request_id.get(),
            "service": "backend", "version": settings.version,
        }
        payload.update(getattr(r, "extra_fields", {}) or {})
        if r.exc_info:
            payload["error_class"] = r.exc_info[0].__name__
            payload["stack"] = self.formatException(r.exc_info)
        return orjson.dumps(payload).decode()
```

Wiring rules, all of which are checkable:

- **Handler is `StreamHandler(sys.stdout)` and nothing else.** No `FileHandler`, no
  `RotatingFileHandler`. §2.2: *never to a file, because a container's filesystem is ephemeral and your
  log shipper reads stdout.* `test_no_file_handlers` asserts `not any(isinstance(h, FileHandler) …)`.
- **Hijack uvicorn's loggers:** `logging.getLogger("uvicorn.access").handlers = []` and
  `propagate = True`, otherwise you emit two log formats and the JSON claim is false.
- **Never log a request body.** Complaint text is PII (ADR-0004). Log `text_len`, not `text`.
- **Never log the key.** `SecretStr` covers accidental dumps; a `logging.Filter` that redacts
  `gsk_[A-Za-z0-9]{20,}` and `AIza[\w-]{35}` from any formatted message is belt and braces.

**The one mandated WARNING** (§2.2): *one WARNING per triage fallback with the complaint id, the
provider and the error class.* Exactly one — not one per retry attempt, not one per except branch:

```python
log.warning("triage.fallback", extra={"extra_fields": {
    "complaint_id": str(cid), "provider": provider.name,
    "error_class": type(exc).__name__, "attempts": attempts,
    "elapsed_ms": elapsed_ms, "fallback_to": "rules"}})
```

`test_fallback_emits_exactly_one_warning` uses `caplog` and asserts
`len([r for r in caplog.records if r.levelno == WARNING]) == 1`.

### 3.3 CORS — kept even though the proxy removes the need (contradiction A7)

```python
app.add_middleware(CORSMiddleware,
    allow_origins=[str(o) for o in settings.cors_allow_origins],  # explicit list, never ["*"]
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Cache", "X-Request-ID", "Retry-After"],
    max_age=600)
```

`expose_headers` is the subtle one: without it, `fetch()` in the browser **cannot read**
`X-Cache`, and Rubric B's cache-badge line silently fails in any cross-origin configuration.
In production the nginx `/api` proxy makes everything same-origin so the header is readable
anyway — but the dev path (`vite dev` on :5173 → backend on :8000) is cross-origin, and that is
the path where you learn the lesson §1.3 promised.

`allow_origins=["*"]` is never used and `test_cors_wildcard_rejected` asserts it.

---

## 4. Dependency injection — how layers get their collaborators

```python
# backend/app/deps.py
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise

def get_redis(request: Request) -> Redis:  return request.app.state.redis
def get_triage(request: Request) -> TriageProvider: return request.app.state.triage

def get_complaint_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    redis:   Annotated[Redis, Depends(get_redis)],
    triage:  Annotated[TriageProvider, Depends(get_triage)],
    request: Request,
) -> ComplaintService:
    return ComplaintService(
        repo=ComplaintRepository(session),
        triage=TriageService(primary=triage, fallback=RuleBasedTriage(),
                             cache=RedisTriageCache(redis), ring=request.app.state.ring,
                             settings=settings),
    )
```

**The route never sees `AsyncSession`.** It depends on `ComplaintService`; the service depends on
`ComplaintRepository`; the repository holds the session. That is §2.2's one-way arrow made
mechanical, and `make lint-layers` (`05-DATA-LAYER.md §5`) fails the build if it is violated.

**Provider swapping in tests** is `app.dependency_overrides[get_triage] = lambda: AlwaysRaises()`
— which is exactly how the mandated fallback test is written without a network, a sleep, or a
re-run (§2.5 *"Determinism"*).

---

## 5. `/health` and `/ready` — the 3-mark distinction

```python
# backend/app/routes/health.py
router = APIRouter()   # NOTE: no session dependency anywhere in this module

@router.get("/health", operation_id="health")
async def health(request: Request) -> HealthOut:
    return HealthOut(status="ok", version=settings.version, pid=os.getpid(),
                     uptime_seconds=int(time.monotonic() - request.app.state.started_at))

@router.get("/ready", operation_id="ready")
async def ready(request: Request, response: Response) -> ReadyOut | JSONResponse:
    if not request.app.state.ready:
        return _not_ready({"lifecycle": "shutting_down"}, ["lifecycle"])
    pg, rd = await asyncio.gather(_check_pg(), _check_redis(), return_exceptions=True)
    checks = {"postgres": _fmt(pg), "redis": _fmt(rd)}
    failed = [k for k, v in checks.items() if not v.startswith("ok")]
    if failed:
        return _not_ready(checks, failed)          # 503, body NAMES the dependency
    return ReadyOut(status="ready", checks=checks)

async def _check_pg() -> None:
    async with asyncio.timeout(2.0):
        async with SessionLocal() as s:
            await s.execute(text("SELECT 1"))

async def _check_redis() -> None:
    async with asyncio.timeout(2.0):
        await app_redis().ping()
```

| Property | Reason |
|---|---|
| `/health` imports nothing from `db` or `providers` | Rubric C: *"/health does not touch the database"*. Enforced by `test_health_module_imports` scanning the module's AST for forbidden imports. |
| `/ready` checks run **concurrently** with independent 2 s timeouts | Serial checks make readiness latency additive; a 2 s Redis stall plus a 2 s PG stall is a 4 s probe that trips `timeoutSeconds: 3` and evicts a healthy pod |
| `/ready` returns 503 **naming** the dependency | §2.2 verbatim. `details.failed: ["postgres"]` is what turns a 3 a.m. page into a 10-second diagnosis |
| `/ready` short-circuits on `state.ready == False` | This is the zero-downtime lever — see §6 |
| Neither is rate-limited, neither is logged at INFO | Probes fire every 2–10 s ×N pods; access-logging them buries the real traffic. Filter `path in {"/health","/ready","/metrics"}` out of the access log. |

**The wiring-backwards failure, stated so you can answer it at viva:** if `/health` checked the
database, a 30-second Postgres stall would fail **liveness** on every backend pod simultaneously,
kubelet would restart all of them, the restarts would hammer the recovering database, and the
cluster would enter a self-sustaining crash loop. Readiness failing in the same scenario merely
removes pods from the Service and returns 503 to clients until the DB recovers. Same input, two
wildly different blast radii — which is why §2.2 says *"wire them backwards and a slow database
becomes a restart loop across your entire deployment."*

---

## 6. SIGTERM and graceful shutdown (Rubric C, 2 marks)

**The full termination sequence on Kubernetes, in order:**

```
t=0     kubelet decides to terminate the pod
t=0     pod removed from Service Endpoints  ─┐  these two are CONCURRENT and
t=0     preStop hook starts: sleep 5        ─┘  the ordering is NOT guaranteed
t=5     preStop returns
t=5     SIGTERM delivered to PID 1 (uvicorn)
t=5     lifespan finally: app.state.ready = False
t=5     /ready starts returning 503
t=5→10  prestop_drain_s: in-flight requests complete; no new ones routed
t=10    triage client closed, redis closed, engine.dispose() closes pool connections
t=10    process exits 0
        terminationGracePeriodSeconds = 30  ← must exceed preStop + drain + margin
```

**Why the `preStop: sleep` exists at all.** Endpoint removal propagates asynchronously through
kube-proxy/iptables on every node. Without the sleep, a pod can receive SIGTERM and stop
accepting connections *before* the last node has updated its rules, and those in-flight connections
become connection-refused — visible as non-zero failed requests in the rollout demo. The sleep
buys the control plane time to converge. §3.3 says exactly this: *"so the pod leaves the Service
endpoints before it stops accepting connections."*

**Implementation notes:**

- Run uvicorn as **PID 1 in exec form** (`CMD ["uvicorn", …]`). A shell-form `CMD` makes
  `/bin/sh` PID 1, and `sh` does not forward SIGTERM — the container then dies on the 30-second
  SIGKILL and drops every in-flight request. This is why §3.1 mandates exec form.
- `--timeout-graceful-shutdown 25` on uvicorn, strictly less than
  `terminationGracePeriodSeconds: 30`.
- Single process per container (`--workers 1`); scale with replicas. Multi-worker adds a
  master-process signal-forwarding problem that Kubernetes already solves better.

**Test (no sleeps, no flakes):**

```python
async def test_sigterm_drains_inflight(app_process):
    fut = asyncio.create_task(client.post("/api/complaints", json=SLOW_BODY))  # provider stalls 2 s
    await asyncio.sleep(0.1)
    app_process.send_signal(signal.SIGTERM)
    resp = await fut
    assert resp.status_code == 201            # in-flight completed, not dropped
    assert app_process.wait(timeout=20) == 0  # clean exit, not SIGKILL
```

And the compose-level proof for the gate: run `hey -z 20s -c 10` against `/api/stats`, send
`docker compose kill -s SIGTERM backend` mid-run, assert **zero non-2xx** in the hey summary.
Tee to `docs/evidence/sigterm-drain.txt`.

---

## 7. Exception handlers — one envelope, no leaks

```python
def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation)   # → 400, NOT 422
    app.add_exception_handler(InvalidTransition, _conflict)          # → 409 naming the transition
    app.add_exception_handler(NotFound, _not_found)                  # → 404
    app.add_exception_handler(RateLimited, _rate_limited)            # → 429 + Retry-After
    app.add_exception_handler(Exception, _unhandled)                 # → 500, opaque body
```

`_validation` flattens Pydantic's `loc` tuple into the dotted field path of
`04-CONTRACTS.md §5.1` and **remaps 422 → 400**, because §2.2 specifies 400 and a contract test
asserts `422` appears nowhere in the OpenAPI schema.

`_unhandled` logs at ERROR with the full stack **and** returns a body containing only
`{"code":"internal_error","request_id":…}`. No exception message, no class name, no path. The
`request_id` is the join key — it is in the response header, in the response body, and in the log
line, so a user can quote it and an operator can `grep` it. Say that sentence at viva.

**Domain exceptions live in `app/domain/errors.py` and carry data, not HTTP:**

```python
class InvalidTransition(Exception):
    def __init__(self, src: Status, dst: Status) -> None:
        self.src, self.dst = src, dst
```
The service raises it; only the handler knows it is a 409. That is the layer rule (`services/` has no
status codes) enforced at the type level, and `make lint-layers` greps for `status_code` under
`services/` to keep it honest.
