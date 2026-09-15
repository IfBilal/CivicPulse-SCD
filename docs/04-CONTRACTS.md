# 04 — THE CONTRACT (FROZEN AT END OF PHASE 1)

> **Owner:** both, one PR, both approve · **Day:** 2 AM · **Gate:** Gate 1
> **Changing anything here after Phase 1 requires a `chore/contract-*` PR, both reviewers, a
> `make gen-client` run, and a standup announcement.** This file is what makes two parallel
> windows possible. `00-SPEC.md §1.2`: *"Keep the contracts in §2 — they are what gets tested."*

---

## 1. Enums — the closed vocabularies

```python
# backend/app/domain/enums.py
from enum import StrEnum

class Category(StrEnum):
    WATER = "water"; ELECTRICITY = "electricity"; SANITATION = "sanitation"
    ROADS = "roads"; STREETLIGHTS = "streetlights"; OTHER = "other"

class Priority(StrEnum):
    HIGH = "high"; NORMAL = "normal"; LOW = "low"

class Status(StrEnum):
    OPEN = "open"; IN_PROGRESS = "in_progress"; RESOLVED = "resolved"; REJECTED = "rejected"

class TriagedBy(StrEnum):
    LLM_GROQ     = "llm:groq"        # §2.3 verbatim
    LLM_GEMINI   = "llm:gemini"      # superset — contradiction A4
    LLM_OLLAMA   = "llm:ollama"      # §2.3 verbatim
    RULES        = "rules"           # §2.3 verbatim
    RULES_FALLBACK = "rules:fallback" # §2.3 verbatim — THE value the fallback test asserts
    SIMULATED    = "simulated"       # superset — contradiction A4, needed because CI writes rows
```

`StrEnum` (3.11+) so that `json.dumps` and SQLAlchemy binding both produce the bare string with
no `.value` ceremony, and so a stray `Category.WATER == "water"` comparison in a test is true.

**The enum is the injection guardrail's teeth** (§2.5 item 7): the LLM's `category` is parsed into
`Category`; anything outside the six members is a `ValidationError`, which is **not retryable**
(contradiction A14) and goes straight to `rules:fallback`.

---

## 2. Field-level validation rules (mirrored in three places)

| Field | Rule | App (Pydantic) | DB (CHECK) | Frontend (mirror) |
|---|---|---|---|---|
| `text` | 10–2000 chars, non-blank after strip | `min_length=10, max_length=2000` + strip validator | `ck_complaints_text_len` | same bounds, same message |
| `location` | 3–200 chars | `min_length=3, max_length=200` | `ck_complaints_location_len` | same |
| `reporter_contact` | nullable, ≤ 120, must be email-ish **or** E.164-ish if present | union validator | `ck_complaints_contact_len` | same |
| `ai_summary` | nullable, ≤ 140 | `max_length=140` | `ck_complaints_summary_len` | display only |
| `page` | ≥ 1 | `ge=1` | — | clamp |
| `page_size` | 1–100 | `ge=1, le=100` | — | clamp to 100 |

> §2.3 is explicit that `text` bounds are *"enforced in the DB as well as the app"*. Two enforcement
> points, one source of truth: constants live in `app/domain/limits.py` and are imported by both the
> Pydantic model and the Alembic migration. The frontend gets them from the OpenAPI schema, so
> §2.1's *"mirrors server rules without replacing them"* is literally true — the mirror is generated.

---

## 3. The state machine (Rubric C, 3 marks)

**Explicit transition table, not a chain of ifs** (§2.2).

```python
# backend/app/domain/transitions.py
from app.domain.enums import Status

TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.OPEN:        frozenset({Status.IN_PROGRESS, Status.REJECTED}),
    Status.IN_PROGRESS: frozenset({Status.RESOLVED, Status.REJECTED}),
    Status.RESOLVED:    frozenset(),   # terminal
    Status.REJECTED:    frozenset(),   # terminal
}
TERMINAL = frozenset(s for s, t in TRANSITIONS.items() if not t)

def is_allowed(src: Status, dst: Status) -> bool:
    return dst in TRANSITIONS[src]
```

Matrix (✔ = 200, ✘ = 409). **16 cells, and there is one test per cell** (`16-TESTING.md §4.1`):

| from ↓ \ to → | open | in_progress | resolved | rejected |
|---|---|---|---|---|
| **open** | ✘ | ✔ | ✘ | ✔ |
| **in_progress** | ✘ | ✘ | ✔ | ✔ |
| **resolved** | ✘ | ✘ | ✘ | ✘ |
| **rejected** | ✘ | ✘ | ✘ | ✘ |

Note the diagonal: `open → open` is **409**, not a no-op 200. The spec says *"everything else is
409"* and offers no idempotency exemption. Document the choice in the PR; be ready for the viva
question *"why isn't a self-transition idempotent?"* — answer: because the operator's intent was to
advance, and silently succeeding on a no-op hides a UI bug.

---

## 4. Headers — the wire-level contract

| Header | Direction | Rule |
|---|---|---|
| `X-Request-ID` | in **and** out | Accepted from client; if absent or not a valid UUIDv4, generate one. **Echoed on every response, including 4xx/5xx.** Appears in every log line (§2.2). |
| `X-Cache` | out, `/api/stats` only | `HIT` \| `MISS`. Exactly those two tokens, uppercase (§2.4). |
| `Retry-After` | out, 429 only | **Integer seconds** (not an HTTP-date), = seconds until the limiter window resets. |
| `X-RateLimit-Limit` / `-Remaining` / `-Reset` | out, `POST /api/complaints` | Not required by spec; ship them. Costs nothing, makes the 429 debuggable, and gives the frontend something honest to render. |
| `Cache-Control` | out, `/api/stats` | `public, max-age=0, must-revalidate` — we want the browser to re-ask so **our** cache decides, not the browser's. |

---

## 5. Error envelopes

One shape for everything, so the frontend has one error renderer.

### 5.1 Validation — `400`

```jsonc
{
  "error": {
    "code": "validation_error",
    "message": "Request body failed validation.",
    "request_id": "6f1c1f2e-...",
    "fields": [
      {"field": "text",     "code": "too_short", "message": "must be at least 10 characters", "constraint": {"min": 10, "max": 2000}},
      {"field": "location", "code": "missing",   "message": "field required"}
    ]
  }
}
```

`fields[]` is the *field-level error body* Rubric C demands. Built by a custom
`RequestValidationError` handler that flattens Pydantic's `loc` tuple into a dotted path
(`body.text` → `text`, `query.page_size` → `page_size`).

### 5.2 Invalid transition — `409` (**must name the attempted transition**, §2.2)

```jsonc
{
  "error": {
    "code": "invalid_status_transition",
    "message": "Invalid status transition: resolved -> in_progress. 'resolved' is terminal.",
    "request_id": "...",
    "details": {
      "from": "resolved",
      "to": "in_progress",
      "allowed_from_current": [],
      "terminal": true
    }
  }
}
```

> The frontend renders `error.message` **verbatim** (Rubric B, 5 marks). Not a mapped string, not a
> toast that says "Something went wrong". Test: `tests/Dashboard.test.tsx` asserts the exact server
> string appears in the DOM.

### 5.3 Rate limited — `429`

```jsonc
{"error":{"code":"rate_limited","message":"Rate limit exceeded: 10 requests per 60s.",
          "request_id":"...","details":{"limit":10,"window_seconds":60,"retry_after_seconds":37}}}
```
Plus `Retry-After: 37`.

### 5.4 Others

| Status | `code` | When |
|---|---|---|
| 404 | `not_found` | unknown complaint id |
| 422 | — | **never emitted.** FastAPI's default 422 is remapped to 400 by the exception handler, because §2.2 says 400. |
| 503 | `not_ready` | `/ready` only; `details.failed: ["postgres"]` |
| 500 | `internal_error` | never contains an exception message or a stack trace in the body — the `request_id` is the join key to the logs |

---

## 6. The ten endpoints

> §2.2 tables **nine**; Rubric C says *"all ten endpoints"* (contradiction A3). The tenth is the
> OpenAPI surface, which §2.1 makes load-bearing. We ship it deliberately and map it in the README.

### 6.1 `POST /api/complaints` → 201

Request:
```jsonc
{"text":"burst water main flooding Street 12 since fajr, water entering ground floors",
 "location":"Street 12, Sector G-9/1, Islamabad",
 "reporter_contact":"+923001234567"}
```
Response `201`, `Location: /api/complaints/{id}`:
```jsonc
{"id":"018f...","text":"...","location":"...","reporter_contact":"+923001234567",
 "category":"water","priority":"high","status":"open",
 "ai_summary":"Burst main flooding Street 12; ground floors taking water.",
 "triaged_by":"llm:groq","triage_latency_ms":842,"triage_confidence":0.91,
 "created_at":"2026-09-14T06:12:04.221Z","updated_at":"2026-09-14T06:12:04.221Z"}
```
Codes: `201` · `400` (field-level) · `429` (+`Retry-After`). **Never `500` because of the LLM** —
that is the whole point of §2.5 item 4.

**Ordering inside the handler is contractual:** rate-limit check → body validation → triage →
persist. Rate limit *before* validation so a flood of malformed bodies still costs one Redis
`INCR`, not a Pydantic parse each.

### 6.2 `GET /api/complaints/{id}` → 200 / 404
Path param must be a UUID; a non-UUID is **404**, not 400 — the resource does not exist and we
do not leak the id format. (Decide this now, test it, and say it in the PR.)

### 6.3 `GET /api/complaints` → 200

Query: `category`, `priority`, `status` (each optional, repeatable → OR within a field, AND
across fields), `page` (≥1, default 1), `page_size` (1–100, default 20), `sort`
(`created_at|-created_at|priority|-priority`, default `-created_at`).

```jsonc
{"items":[ /* ComplaintOut */ ],
 "total":137, "page":1, "page_size":20, "pages":7,
 "filters_applied":{"status":["open"],"priority":["high"]}}
```

`total` is mandatory (§2.2). Computed in **one** round trip via `COUNT(*) OVER () AS total_count`
in the same statement as the page — not a second `SELECT count(*)`. Justify in the notes; it also
removes a read-skew window between the count and the page.

`page_size=101` → **400**, not a silent clamp. The spec says `≤ 100`; a silent clamp hides a
client bug.

### 6.4 `PATCH /api/complaints/{id}/status` → 200 / 404 / 409

```jsonc
{"status":"in_progress","note":"crew dispatched"}   // note optional, ≤ 280, not persisted in v1
```
Concurrency: the UPDATE is conditional —
`UPDATE complaints SET status=:new WHERE id=:id AND status=:expected_current`. Zero rows
affected ⇒ re-read and return **409** with the *actual* current status in `details.from`. This makes
two operators clicking at once produce a correct 409 instead of a lost update.

### 6.5 `GET /api/stats` → 200, `X-Cache: HIT|MISS`

```jsonc
{"total":137,
 "by_category":{"water":41,"electricity":22,"sanitation":18,"roads":29,"streetlights":21,"other":6},
 "by_priority":{"high":24,"normal":88,"low":25},
 "by_status":{"open":61,"in_progress":30,"resolved":39,"rejected":7},
 "generated_at":"2026-09-14T06:20:00Z",
 "cache_age_seconds":12}
```

`by_status` and `cache_age_seconds` are the two fields deliberately added during the **scheduled
merge conflict** (`01-WORKFLOW.md §2.4`). `cache_age_seconds` is `0` on a MISS.
All six categories, all three priorities, all four statuses appear **even at zero** — a chart that loses
its axis when a bucket empties is a bug.

### 6.6 `GET /api/meta/providers` → 200 (the observability surface, §2.2)

```jsonc
{"active":"llm:groq",
 "configured":"llm",
 "available":["llm","ollama","rules","simulated"],
 "cache":{"hits":58,"misses":79,"hit_rate":0.423},   // §2.5 item 5 — the MEASURED hit rate
 "recent":[
   {"complaint_id":"018f...","provider":"llm:groq","latency_ms":842,"fallback":false,"cached":false,"at":"…"},
   {"complaint_id":"018f...","provider":"rules:fallback","latency_ms":10031,"fallback":true,
    "error_class":"httpx.ReadTimeout","at":"…"}
 ]}
```
`recent` is the **last 20** (§2.2), newest first, from an in-process `collections.deque(maxlen=20)`.
It is per-pod and that is fine — say so in the notes, and say what you would do instead
(a Redis `LPUSH`+`LTRIM` list) if you needed it cluster-wide. **Never includes complaint text, never
includes the API key, never includes the prompt.**

### 6.7 `GET /health` → 200 always-if-alive (§2.2: **must not touch the database**)

```jsonc
{"status":"ok","uptime_seconds":3021,"version":"a1b2c3d","pid":1}
```
Implementation constraint: this handler is registered **without** the DB dependency, and there is a
test that monkeypatches the session factory to raise and asserts `/health` still returns 200.
That test is the proof for Rubric C's *"/health does not touch the database"* line.

### 6.8 `GET /ready` → 200 / 503 naming the failed dependency

```jsonc
// 503
{"error":{"code":"not_ready","message":"Dependency check failed: postgres",
  "request_id":"...","details":{"checks":{"postgres":"fail: timeout after 2000ms","redis":"ok"},
  "failed":["postgres"]}}}
```
Each check has its **own 2 s timeout** and they run concurrently (`asyncio.gather`). A readiness
probe that can block for the full DB pool timeout will itself cause the outage it is meant to report.

### 6.9 `GET /metrics` → 200, `text/plain; version=0.0.4`

Required series (§2.2):

| Metric | Type | Labels |
|---|---|---|
| `http_requests_total` | Counter | `method`, `path_template`, `status` |
| `http_request_duration_seconds` | Histogram | `method`, `path_template`; buckets `.005 .01 .025 .05 .1 .25 .5 1 2.5 5 10` |
| `triage_duration_seconds` | Histogram | `provider`, `outcome` ∈ `{ok,fallback,cached}`; buckets `.05 .1 .25 .5 1 2 5 10 15` |
| `triage_fallback_total` | Counter | `provider`, `error_class` |
| `triage_cache_hits_total` / `_misses_total` | Counter | — |
| `ratelimit_rejections_total` | Counter | — |
| `app_info` | Gauge=1 | `version`, `provider` |

**`path_template`, never the raw path.** `/api/complaints/018f-…` as a label value is an unbounded
cardinality explosion that will eat Prometheus. Use the matched route (`/api/complaints/{id}`).
Say this in the notes; it is a real production failure mode and a good viva answer.

`/metrics` is excluded from the request-duration histogram (it would measure itself) and is **not**
exposed through the Ingress (`13-KUBERNETES.md §7`).

### 6.10 `GET /openapi.json` (+ `/docs`) — the tenth endpoint

The typed client is generated from it (§2.1). Contract requirements:
- `operation_id` is explicit and stable on every route (`create_complaint`, `list_complaints`,
  `get_complaint`, `update_complaint_status`, `get_stats`, `get_providers`, `health`, `ready`) —
  otherwise FastAPI derives ugly names and `schema.d.ts` churns on every refactor.
- Every response code above is declared in `responses={...}` with its model, so the generated types
  include the error envelope.
- `servers: [{"url": "/"}]` — **never an absolute URL**, which would smuggle an environment into
  the schema and undo ADR-0002.
- Dumped **without starting a server**: `python -m app.cli.openapi_dump` imports the app factory
  and prints `json.dumps(app.openapi(), indent=2, sort_keys=True)`. `sort_keys` makes the CI
  drift check stable.

---

## 7. Pydantic models (the exact wire shapes)

```python
# backend/app/schemas/complaint.py
class ComplaintCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=TEXT_MIN, max_length=TEXT_MAX)
    location: str = Field(min_length=LOC_MIN, max_length=LOC_MAX)
    reporter_contact: str | None = Field(default=None, max_length=CONTACT_MAX)

class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; text: str; location: str; reporter_contact: str | None
    category: Category; priority: Priority; status: Status
    ai_summary: str | None; triaged_by: TriagedBy
    triage_latency_ms: int; triage_confidence: float | None
    created_at: datetime; updated_at: datetime

class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status
    note: str | None = Field(default=None, max_length=280)
```

`extra="forbid"` is deliberate: an unknown field is a **400**, not a silent drop. A frontend that
sends `{"catagory": "water"}` should be told, not ignored.

```python
# backend/app/schemas/triage.py — §2.5 verbatim, plus the A5 superset
class TriageResult(BaseModel):
    model_config = ConfigDict(extra="ignore")   # the MODEL may add keys; we discard them
    category: Category
    priority: Priority
    summary: str = Field(max_length=140)
    confidence: float = Field(ge=0.0, le=1.0)
```

Note the asymmetry and be ready to defend it at viva: `extra="forbid"` for **our** clients (strict,
we control them, a typo is a bug worth surfacing) and `extra="ignore"` for the **model** (we do not
control it, and rejecting a response solely for an extra key would trigger a fallback that loses a
perfectly good classification). Two different trust postures, one validation library — which is the
FastAPI+Pydantic argument in §2.2 made concrete.

---

## 8. Typed-client generation and the CI drift gate

```bash
make openapi        # backend → openapi.json, no server
make gen-client     # openapi.json → frontend/src/api/schema.d.ts via openapi-typescript
git diff --exit-code frontend/src/api/schema.d.ts   # CI: fails if the committed client is stale
```

`frontend/src/api/client.ts` is a thin `fetch` wrapper typed by `paths` from `schema.d.ts`:

```ts
import type { paths } from "./schema";
type CreateBody = paths["/api/complaints"]["post"]["requestBody"]["content"]["application/json"];
type CreateOk   = paths["/api/complaints"]["post"]["responses"][201]["content"]["application/json"];
type ApiError   = paths["/api/complaints"]["post"]["responses"][400]["content"]["application/json"];
```

This is how §2.1's *"typed API client generated from or checked against the backend's OpenAPI
schema"* is satisfied **and** how a backend contract change that the frontend has not absorbed
becomes a red `tsc` in CI instead of a runtime `undefined` in the demo video.

**Base URL:** `client.ts` uses the relative prefix `/api`. There is no `VITE_API_URL`. That is
ADR-0002, and it is also the answer to §5.2 question 3 (*the exact line guaranteeing
build-once-deploy-many*).

---

## 9. Contract test suite (runs in `ci.yml → test-backend`, marked `contract`)

`backend/tests/contract/` — these tests encode this file and nothing else. They are the
regression net that lets the contract be "frozen" in practice rather than in spirit.

| Test | Asserts |
|---|---|
| `test_openapi_operation_ids_stable` | the eight operation ids exist and match a committed golden list |
| `test_openapi_servers_relative` | `servers[0].url == "/"` |
| `test_all_documented_status_codes_declared` | every code in §5–6 appears in the route's `responses` |
| `test_error_envelope_shape` | 400/404/409/429/503 all match the `ErrorEnvelope` model |
| `test_422_never_emitted` | a malformed body yields **400**, and the word `422` appears nowhere in the schema |
| `test_page_size_over_100_is_400` | boundary: 100 → 200, 101 → 400 |
| `test_x_request_id_echoed_on_every_path` | parametrised over all ten endpoints, including error paths |
| `test_x_cache_only_on_stats` | header present on `/api/stats`, absent elsewhere |
| `test_409_body_names_transition` | `details.from` and `details.to` equal the attempted pair |
| `test_health_has_no_db_dependency` | introspect the route's dependency graph; assert no session dependency |
