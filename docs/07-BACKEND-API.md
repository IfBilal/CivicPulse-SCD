# 07 — BACKEND API (routes · services · state machine)

> **Owner:** DEV-A · **Day:** 4 · **Gate:** Gate 3 · **Rubric:** C lines 1 and 3 (10 marks)
> Implements `04-CONTRACTS.md` on top of `06-BACKEND-CORE.md`. Nothing here decides *what*
> the API looks like — that was frozen in Phase 1.

---

## 1. The layer rule, restated as code shapes

| Layer | May import | May raise | May know about |
|---|---|---|---|
| `routes/` | `schemas`, `services`, `deps` | nothing (it catches) | HTTP verbs, status codes, headers |
| `services/` | `repositories`, `providers`, `domain` | `domain.errors.*` | business rules, orchestration order |
| `repositories/` | `db.models`, `sqlalchemy` | `sqlalchemy` errors | SQL, transactions |
| `providers/` | `httpx`, `redis`, `schemas.triage` | provider-specific errors | wire formats of third parties |

A route function is allowed to be boring. If a route is more than ~12 lines, business logic has
leaked upward.

---

## 2. `POST /api/complaints`

### 2.1 Route

```python
@router.post("", status_code=201, response_model=ComplaintOut,
             operation_id="create_complaint",
             responses={400: {"model": ErrorEnvelope}, 429: {"model": ErrorEnvelope}})
async def create_complaint(
    body: ComplaintCreate,
    response: Response,
    svc: Annotated[ComplaintService, Depends(get_complaint_service)],
) -> ComplaintOut:
    complaint = await svc.create(text=body.text, location=body.location,
                                 contact=body.reporter_contact)
    response.headers["Location"] = f"/api/complaints/{complaint.id}"
    return ComplaintOut.model_validate(complaint)
```

Eight lines. No session, no SQL, no triage knowledge, no try/except. Rate limiting happened in
middleware; validation happened in Pydantic; the 400 envelope is produced by the handler
registered in `06-BACKEND-CORE.md §7`.

### 2.2 Service — the orchestration order is contractual

```python
class ComplaintService:
    async def create(self, *, text: str, location: str, contact: str | None) -> Complaint:
        outcome = await self._triage.triage_with_fallback(text=text, location=location)
        return await self._repo.create(
            text=text, location=location, contact=contact,
            category=outcome.result.category, priority=outcome.result.priority,
            ai_summary=outcome.result.summary, confidence=outcome.result.confidence,
            triaged_by=outcome.triaged_by, latency_ms=outcome.latency_ms,
        )
```

**Triage before persist, not after.** The contract returns a fully-triaged `201` body (§2.1 requires
the Submit view to render category, priority, summary and provider from the response). Persisting
first and triaging asynchronously would be a defensible *different* system — and it is the right
answer at scale — but it changes the contract, so it is not this system. Write the alternative into
`docs/ENGINEERING-NOTES.md`: *"we chose synchronous triage because the contract returns the
classification; the async design would return 202 + a polling URL, trade user-visible latency for
throughput, and require an outbox table."* That paragraph is viva gold.

**Transaction boundary.** `get_session` commits on clean exit (`06-BACKEND-CORE.md §4`). The
triage call happens **outside** any open transaction because a 10-second HTTP call holding a
Postgres connection would exhaust the pool under load. Verify: the `create` call is the first
statement issued on that session.

### 2.3 Status-code truth table for this endpoint

| Condition | Code | Body |
|---|---|---|
| valid, triage ok | 201 | `ComplaintOut`, `triaged_by="llm:groq"` |
| valid, provider raised | **201** | `ComplaintOut`, `triaged_by="rules:fallback"` ← §2.5 item 4 |
| valid, provider returned bad JSON | **201** | same, `rules:fallback`, **no retry** |
| valid, triage cache hit | 201 | `triaged_by` = the **original** provider, `triage_latency_ms` = the **cached** value; `cached: true` in the ring |
| `text` 9 chars | 400 | `fields[0].field == "text"` |
| unknown key in body | 400 | `extra="forbid"` |
| over rate limit | 429 | `Retry-After: <int>` |
| DB down | 503 from `/ready`, **500 here** | opaque envelope; this is the one case where a citizen sees a failure, and it is correct |

> The second and third rows are the assignment's thesis compressed into a table:
> *"A user must never see a 500 because a third party was rate-limited."*

---

## 3. `GET /api/complaints` — filtering, pagination, sorting

```python
@router.get("", response_model=ComplaintPage, operation_id="list_complaints")
async def list_complaints(
    svc: Annotated[ComplaintService, Depends(get_complaint_service)],
    category: Annotated[list[Category] | None, Query()] = None,
    priority: Annotated[list[Priority] | None, Query()] = None,
    status:   Annotated[list[Status] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Annotated[SortKey, Query()] = SortKey.CREATED_DESC,
) -> ComplaintPage: ...
```

- `ge=1, le=100` in the signature means the `≤ 100` rule appears **in the OpenAPI schema**, so the
  generated TS client types it and the frontend cannot construct an invalid request. One constraint,
  three enforcement points, zero duplication — this is the §2.2 argument for FastAPI in practice.
- Repeated params (`?status=open&status=in_progress`) → `IN` within a field, `AND` across fields.
- `pages = ceil(total / page_size)`; `pages == 0` when `total == 0`, not 1.
- `sort` is an enum mapped to a dict of SQLAlchemy order clauses in the repository. **Never**
  interpolate the sort string into SQL. (Same reflex as *"never build SQL from model output"*.)
- Out-of-range page (`page=99` with 2 pages) → **200 with an empty `items`**, not 404. A page is a
  window, not a resource.

---

## 4. `PATCH /api/complaints/{id}/status` — the state machine (Rubric C, 3 marks)

```python
class ComplaintService:
    async def change_status(self, cid: UUID, new: Status) -> Complaint:
        current = await self._repo.get(cid)
        if current is None:
            raise NotFound(cid)
        if not is_allowed(current.status, new):                    # TABLE lookup, not ifs
            raise InvalidTransition(current.status, new)
        updated = await self._repo.transition(cid, expected=current.status, new=new)
        if updated is None:                                        # lost the race
            fresh = await self._repo.get(cid)
            raise InvalidTransition(fresh.status, new)             # report the ACTUAL from-state
        await self._stats.invalidate()                             # §2.4 invalidate on write
        return updated
```

Three properties worth the marks:

1. **Table lookup.** `is_allowed` indexes `TRANSITIONS` (`04-CONTRACTS.md §3`). Adding a state
   later is a dict entry, not a new `elif` branch in a function that nobody dares touch.
2. **Conditional UPDATE.** The check-then-act is not atomic across two operators clicking
   simultaneously; the `WHERE status = :expected` makes the write atomic and turns the loser into a
   correct 409 rather than a silent overwrite. The second `get` is what lets the 409 name the *real*
   current state instead of a stale one.
3. **Cache invalidation is a write-path concern**, so it lives in the service, next to the write, not
   in the stats route. §2.4: *"Invalidate on write, so a newly submitted complaint appears in the
   stats immediately."*

**409 body** (`04-CONTRACTS.md §5.2`) names `from`, `to`, `allowed_from_current`, and `terminal`.
`allowed_from_current` is `sorted(TRANSITIONS[current])` — which means the API *teaches* the
client the state machine without the client hardcoding it. That is §2.1's *"never duplicated in it"*
requirement solved rather than merely obeyed, and it is a strong thing to point at on camera.

---

## 5. `GET /api/stats`

```python
@router.get("/stats", response_model=StatsResponse, operation_id="get_stats")
async def get_stats(response: Response,
                    svc: Annotated[StatsService, Depends(get_stats_service)]) -> StatsResponse:
    payload, hit, age = await svc.get()
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    return payload.model_copy(update={"cache_age_seconds": age})
```

Aggregation SQL lives in `stats_repo.py` and is **one** statement, not four:

```sql
SELECT
  count(*)                                                      AS total,
  jsonb_object_agg(k, v) FILTER (WHERE dim = 'category')        AS by_category,
  ...
FROM ( SELECT 'category' AS dim, category::text AS k, count(*) AS v FROM complaints GROUP BY 1,2
       UNION ALL
       SELECT 'priority', priority::text, count(*) FROM complaints GROUP BY 1,2
       UNION ALL
       SELECT 'status',   status::text,   count(*) FROM complaints GROUP BY 1,2 ) t;
```

Then **zero-fill every enum member in Python** before returning, so a category with no rows still
appears as `0` (`04-CONTRACTS.md §6.5`). A chart whose axis disappears when a bucket empties is a
bug that only shows up in the demo.

Everything about TTL, HIT/MISS, invalidation and the stampede lock is in `09-CACHE-RATELIMIT.md`.

---

## 6. `GET /api/meta/providers`

Reads three sources, none of which is the database:

| Field | Source |
|---|---|
| `configured` | `settings.triage_provider` (immutable, `frozen=True`) |
| `active` | `app.state.triage.name` — differs from `configured` if the factory degraded at boot (e.g. `llm` requested, no key ⇒ startup fails, so in practice these match; the field exists to make a mismatch visible rather than silent) |
| `cache.hits/misses/hit_rate` | Prometheus counters read via `REGISTRY.get_sample_value` — one source of truth for both `/metrics` and this endpoint |
| `recent` | `app.state.ring`, a `deque(maxlen=20)` |

`hit_rate` is `hits / (hits + misses)` with a `0.0` guard, rounded to 3dp. **This is the "measured,
reported hit rate"** of §2.5 item 5 and Rubric F. Snapshot it into `docs/TRIAGE.md` after the load
test so the number in your documentation is one you actually observed.

**Never leak:** complaint text, the prompt, the API key, the base URL with credentials. The ring
stores `complaint_id`, `provider`, `latency_ms`, `fallback`, `cached`, `error_class`, `at` — and
nothing else. `test_meta_providers_leaks_nothing` asserts the serialised response contains no
substring of the seeded complaint text and no `gsk_`/`AIza` prefix.

---

## 7. Endpoint → test → rubric traceability for this file

| Endpoint | Key tests | Rubric |
|---|---|---|
| `POST /api/complaints` | `test_create_201_shape`, `test_create_400_field_level`, `test_create_429_retry_after`, `test_create_fallback_still_201` | C1, F3, E3 |
| `GET /api/complaints/{id}` | `test_get_200`, `test_get_404_unknown_uuid`, `test_get_404_non_uuid` | C1 |
| `GET /api/complaints` | `test_filter_and_across_fields`, `test_filter_or_within_field`, `test_page_size_boundaries`, `test_total_present`, `test_empty_page_is_200` | C1 |
| `PATCH …/status` | 16 parametrised transition cases, `test_409_names_transition`, `test_concurrent_transition_one_wins` | C1, C3 |
| `GET /api/stats` | `test_x_cache_miss_then_hit`, `test_invalidated_on_write`, `test_zero_filled_buckets` | E1, E2 |
| `GET /api/meta/providers` | `test_ring_capped_at_20`, `test_hit_rate_math`, `test_meta_providers_leaks_nothing` | F6 |
| `GET /health` | `test_health_ok_with_db_down`, `test_health_module_imports` | C4 |
| `GET /ready` | `test_ready_503_names_postgres`, `test_ready_concurrent_timeouts` | C4 |
| `GET /metrics` | `test_metrics_exposes_required_series`, `test_metrics_path_template_label` | C1, J |
| `GET /openapi.json` | the nine contract tests in `04-CONTRACTS.md §9` | C1, B4 |

---

## 8. Route-level anti-patterns that cost marks (self-review checklist before the PR)

- [ ] No `Depends(get_session)` in any route signature
- [ ] No `select(`, `.execute(`, `text(` anywhere under `routes/`
- [ ] No `if status == …` chain anywhere — transitions come from the table only
- [ ] No `try/except` in a route that maps a domain error to a status code (handlers do that)
- [ ] No business default applied in a route (`priority = priority or "normal"` belongs in the service)
- [ ] No `print()` — `ruff` rule `T20` fails the build
- [ ] No `response_model=dict` — every response is a named Pydantic model, or the generated TS client degrades to `unknown`
- [ ] Every route has an explicit `operation_id` (schema stability, `04-CONTRACTS.md §6.10`)
- [ ] Every non-200 code the contract lists is declared in `responses={...}`
