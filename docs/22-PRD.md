# 22 — PRODUCT REQUIREMENTS DOCUMENT (PRD)

**Product:** CivicPulse — municipal complaint intake, AI triage and operations platform
**Version:** 1.0 · **Status:** Approved for build · **Owners:** DEV-A (Core), DEV-B (Edge)
**Authority:** `00-SPEC.md` is the single source of truth. This PRD **restates** the spec as
product requirements; where the two disagree, the spec wins and this file is a bug.

---

## 1. Problem statement

Municipal complaint intake fails at the sorting step, not the collecting step.

A citizen submits *"burst water main flooding Street 12 since fajr, water entering ground floors"*
into a free-text form. That text lands in an undifferentiated queue. On a Monday the queue is four
hundred items long, and the burst main sits behind three streetlight complaints because nothing
sorted them. By the time a human reads it, a street is flooded.

**The naive fix fails for understood reasons.** A category dropdown pushes classification onto the
person least equipped to do it: citizens pick wrong, pick "Other" to get through the form faster,
and cannot judge urgency relative to the rest of the queue. The information needed to sort the
queue **is already in the text**. Somebody has to read it.

**The engineering problem is not the reading. It is that the reader must be replaceable.** Today
it is a keyword rule. Tomorrow it is a language model. Next year it is a fine-tuned classifier. The
system around it must not care which, and must not fall over when the clever one is rate-limited,
slow, or simply wrong.

---

## 2. Goals and non-goals

### 2.1 Goals

| # | Goal | Measured by |
|---|---|---|
| G1 | Sort a free-text complaint queue by **category** and **priority** without asking the citizen to do it | ≥ 85% category agreement against a 30-item human-labelled golden set |
| G2 | Make the classifier a **swappable component** | 4 implementations behind one interface, selected by one env var, with no call-site changes |
| G3 | **Never fail intake** because a third party failed | `POST /api/complaints` returns 201 for every valid body, under every provider failure mode |
| G4 | Give operators a live, filterable view with a **safe** status workflow | illegal transitions are impossible to commit; the server explains why |
| G5 | Run the whole system from a **clean clone in one command**, and on Kubernetes with a second | both commands verified by the developer who did not write them |
| G6 | Make every claim in the documentation **demonstrable** | every README assertion has an evidence artefact |

### 2.2 Non-goals (explicitly out of scope for v1)

| Non-goal | Why | What we say instead |
|---|---|---|
| Operator authentication / RBAC | Not in the spec; a half-built auth system is worse than an honest gap | README §Known limitations: *"the dashboard is unauthenticated; production needs an operator IdP and per-role authorisation on PATCH /status"* |
| Assignment to crews, SLAs, work orders | Beyond triage; would double the domain | — |
| Notifications to citizens (SMS/email) | Requires a provider, consent, and a retention policy | — |
| Multi-tenancy / multi-municipality | One tenant is enough to demonstrate every competency | — |
| Duplicate **merging** | We deduplicate *inference* via the content-hash cache, not *records*. Nine neighbours reporting one burst main are nine legitimate reports | ADR-0001 |
| Retention / deletion policy | Named and deferred | ADR-0004 §4.4, Issue #N |
| Offline/PWA support | No stated need | — |
| Horizontal scaling of Postgres | Single writer is correct at this volume | `05-DATA-LAYER.md §1` connection arithmetic |

---

## 3. Users and personas

| Persona | Context | Needs | Pain today |
|---|---|---|---|
| **Ayesha, citizen** | Phone browser, patchy connection, writes Urdu-influenced English, wants to report a burst main at 6 a.m. | Submit in under 60 s; know it was received; know it was understood | Forms demand a category she cannot judge; no acknowledgement that urgency registered |
| **Kamran, municipal operator** | Desktop, 400-item queue, 8-hour shift | See the urgent items first; filter by area/type; advance status without corrupting state | Unsorted queue; no notion of priority; status changed by accident with no guard |
| **Nadia, ops supervisor** | Reviews throughput weekly | Aggregate counts by category/priority/status | No aggregate view; counts assembled by hand |
| **On-call engineer** | 3 a.m. page | Know whether the system is degraded and why; roll back in 30 seconds | — (this is the audience for `/api/meta/providers`, `/metrics` and the RUNBOOK) |

---

## 4. User stories with acceptance criteria

Every criterion is testable and maps to a test ID from `16-TESTING.md`.

### US-1 — Submit a complaint (Ayesha)
> *As a citizen, I describe my problem in my own words and get a receipt that shows the system
> understood it.*

| # | Acceptance criterion | Test |
|---|---|---|
| 1.1 | Text 10–2000 chars and location 3–200 chars are required; contact optional | contract 400 tests, FE-1 |
| 1.2 | Invalid input returns a **field-level** error naming the field and the constraint | `test_create_400_field_level`, FE-10 |
| 1.3 | A valid submission returns **201** with category, priority, one-line summary (≤140), **and which provider decided** | `test_create_201_shape`, FE-2 |
| 1.4 | While waiting, the UI states honestly what is happening and escalates its message at 1.5 s and 6 s | FE-3 |
| 1.5 | If the AI provider fails in **any** way, the submission still returns **201**, marked `rules:fallback` | **F1** (the spec-mandated test) |
| 1.6 | A re-submission of identical text and location costs **no** second inference | F11 |
| 1.7 | Submitting faster than 10/min from one IP returns **429** with `Retry-After` | E9, E10 |
| 1.8 | Text containing instructions to the model cannot change the output vocabulary | F15 ×5 |

### US-2 — Triage a queue (Kamran)
> *As an operator, I see the urgent things first and can filter to my area.*

| # | Acceptance criterion | Test |
|---|---|---|
| 2.1 | List is paginated (`page`, `page_size ≤ 100`) and returns `total` | contract pagination tests |
| 2.2 | Filterable by category, priority and status; repeated values OR within a field, AND across fields | `test_filter_and_across_fields`, FE-7 |
| 2.3 | Default sort is newest first | `test_list_default_sort` |
| 2.4 | `page_size=101` is **rejected**, not silently clamped | `test_page_size_boundaries` |
| 2.5 | An out-of-range page returns 200 with an empty list, not 404 | `test_empty_page_is_200` |

### US-3 — Advance a status safely (Kamran)
> *As an operator, I cannot put a complaint into a state that makes no sense, and if I try the
> system tells me exactly what I attempted.*

| # | Acceptance criterion | Test |
|---|---|---|
| 3.1 | Only `open→in_progress`, `open→rejected`, `in_progress→resolved`, `in_progress→rejected` succeed | C-T01…C-T16 (all 16 cells) |
| 3.2 | Any other transition returns **409 naming the attempted transition** | `test_409_names_transition` |
| 3.3 | The 409 body includes `allowed_from_current`, so the client learns the machine instead of hardcoding it | `test_allowed_from_current` |
| 3.4 | The UI shows the server's 409 message **verbatim** | FE-4 (exact-string assertion) |
| 3.5 | Two operators acting simultaneously produce one success and one 409 — never a lost update | D9 |

### US-4 — See the shape of the queue (Nadia)
> *As a supervisor, I see counts by category, priority and status, and I can tell whether I am
> looking at a cached number.*

| # | Acceptance criterion | Test |
|---|---|---|
| 4.1 | Counts for **every** enum member appear, including zeros | `test_zero_filled_buckets`, FE-11 |
| 4.2 | Repeat calls within 30 s are served from cache and say so via `X-Cache: HIT` | E1 |
| 4.3 | A new complaint makes the next stats call a **MISS** — no waiting out the TTL | E4, E6 |
| 4.4 | The UI displays hit/miss and the cache age | FE-5 |

### US-5 — Operate the system (on-call engineer)
> *As an engineer, I can tell in one request whether triage is healthy, and roll back in 30 seconds.*

| # | Acceptance criterion | Test / evidence |
|---|---|---|
| 5.1 | `/api/meta/providers` shows the active provider, the **last 20 outcomes** with latency and fallback flag, and the **measured** cache hit rate | F19, `docs/TRIAGE.md §6` |
| 5.2 | `/metrics` exposes request count, latency histogram, triage latency and a fallback counter | `test_metrics_exposes_required_series` |
| 5.3 | `/health` stays 200 when Postgres is down; `/ready` returns 503 **naming** the failed dependency | C-C11, C-C13 |
| 5.4 | Every log line carries a `request_id` that is also in the response header and error body | C-C07 |
| 5.5 | A bad deploy can be reverted in under 30 s and, separately, reverted auditably through git | `15-CICD.md §7`, video beat 6 |

---

## 5. Functional requirements

| ID | Requirement | Spec | Priority |
|---|---|---|---|
| FR-01 | Ten HTTP endpoints exactly as `04-CONTRACTS.md` specifies | §2.2, Rubric C1 | **P0** |
| FR-02 | Triage returns `category`, `priority`, `summary ≤140`, `confidence 0–1`, validated against a Pydantic schema | §2.5 | **P0** |
| FR-03 | Four provider implementations behind one `Protocol`, selected by `TRIAGE_PROVIDER` | §2.5 | **P0** |
| FR-04 | 10 s per-call timeout; **one** jittered retry on timeout/429/5xx **only**; fallback to rules | §2.5 items 2–4 | **P0** |
| FR-05 | `triaged_by` persisted, including `rules:fallback` | §2.3 | **P0** |
| FR-06 | Content-hash triage cache, 24 h TTL, hit rate measured and reported | §2.5 item 5 | **P1** |
| FR-07 | Prompt-injection guardrail with a test | §2.5 item 7 | **P1** |
| FR-08 | Explicit status transition table; 409 naming the attempted transition | §2.2 | **P0** |
| FR-09 | Alembic migrations; no DDL in application startup | §2.3 | **P0** |
| FR-10 | Idempotent seed of ≥30 Urdu-influenced-English complaints across all categories | §2.3 | **P1** |
| FR-11 | `/api/stats` read-through cache, 30 s TTL, `X-Cache`, invalidated on write | §2.4 | **P0** |
| FR-12 | Distributed Redis rate limiter on `POST /api/complaints`, 429 + `Retry-After` | §2.4 | **P0** |
| FR-13 | Three frontend views with no business rules in the client | §2.1 | **P0** |
| FR-14 | Runtime configuration — one image runs in any environment | §2.1 | **P1** |
| FR-15 | `/health`, `/ready`, `/metrics` with the stated semantics | §2.2 | **P0** |
| FR-16 | Graceful SIGTERM drain | §2.2 | **P1** |

`P0` = a missing P0 makes the product incoherent. `P1` = degrades the product but it still works.
There is no `P2` — everything in the spec is at least P1, which is itself a fact about this spec.

---

## 6. Non-functional requirements

| ID | Category | Requirement | Verified by |
|---|---|---|---|
| NFR-01 | Availability | Intake never returns 5xx due to a provider failure | F1–F9 |
| NFR-02 | Latency | p95 `POST /api/complaints` < 3 s with a hosted provider; < 200 ms on a cache hit; < 50 ms on the rules path | k6 thresholds, `triage_duration_seconds` |
| NFR-03 | Latency | p95 `GET /api/stats` < 100 ms on a HIT | `http_request_duration_seconds` |
| NFR-04 | Throughput | ≥ 120 req/s sustained at ≤ 10 backend replicas | `load/k6-script.js` plateau stage |
| NFR-05 | Elasticity | Replicas track offered load within ~90 s; measured and charted | `hpa-replicas-vs-load.png` |
| NFR-06 | Durability | Zero row loss across `compose down/up` and across `delete pod postgres-0` | `persistence-*.txt` |
| NFR-07 | Security | No secret in git, in an image layer, in a log, in a metric label, or in a browser bundle | `17-SECURITY-SECRETS.md §7` |
| NFR-08 | Security | Frontend has no network path to the database | `network-isolation.txt`, NetworkPolicy |
| NFR-09 | Privacy | `reporter_contact` never leaves the process; hosted path redacts phone/email/ID patterns | ADR-0004, structural (never passed to `triage()`) |
| NFR-10 | Cost | One inference per distinct complaint per 24 h per model | F11, measured hit rate |
| NFR-11 | Observability | Every request correlatable by `request_id` across logs, response and traces | C-C07 |
| NFR-12 | Deployability | Deploy by immutable reference; rollback < 30 s | `15-CICD.md §4.2, §7` |
| NFR-13 | Maintainability | Four-layer separation enforced mechanically; coverage ≥ 65% on `app/` | `make lint-layers`, `--cov-fail-under=65` |
| NFR-14 | Portability | Identical behaviour on a laptop and a CI runner; every version frozen in a file | `16-TESTING.md §2`, NOTES Q1 |
| NFR-15 | Reproducibility | One image runs in every environment; no environment baked into a build | ADR-0002, `runtime-config.txt` |
| NFR-16 | Accessibility | Labelled inputs, `aria-live` errors, `role="status"` loading, never colour-only | `11-FRONTEND.md §7` |

---

## 7. Success metrics

| Metric | Target | Source | Why this number |
|---|---|---|---|
| Category agreement vs golden set | ≥ 85% (hosted), ≥ 60% (Ollama) | `docs/TRIAGE.md §4` | The gap **is** the buy-vs-host finding; a small gap would make the trade-off uninteresting and a huge one would make the local path unusable |
| High-priority recall on flooding/live-wire complaints | ≥ 95% | golden set subset | Missing an urgent item is the failure mode that motivated the product |
| Fallback rate under normal operation | < 5% | `triage_fallback_total / triage_duration_seconds_count` | Above this, the provider choice is wrong, not the code |
| Triage cache hit rate at steady state | ≥ 40% on realistic repeat traffic | `/api/meta/providers.cache` | Directly converts to quota headroom |
| Intake 5xx rate | **0** | `http_requests_total{status=~"5.."}` | NFR-01 is absolute |
| HPA lag | measured, reported, < 120 s | `hpa-watch.txt` | The spec asks for the number and the explanation, not a target |
| Failed requests during a rolling update | **0** | k6 `rate==0` threshold | Bonus is pass/fail |
| Clean-clone quickstart success | 1/1 by the developer who did not write it | Gate 8 | §5.3 −5 |

---

## 8. Constraints

| Constraint | Source | Consequence |
|---|---|---|
| Free-tier LLM only; no credit card | §2.5 | Org-level rate limits are a **design input**, which is why the limiter and the cache exist |
| Team of 2 | cover page | Ownership split + two scheduled swaps (`01-WORKFLOW.md §1`) |
| 2 weeks (cover) vs 4 weeks (§5.1) | contradiction A6 | Plan to 14 days, expansion map for 28 |
| Local Kubernetes only (k3d/kind) | §3.3 | *"A managed cloud cluster is not required and earns no extra marks"* |
| No late submission, no retake | §5.3 | **Submit something imperfect on time.** Freeze 48 h before the deadline |
| Individual viva multiplies the team mark | §5.4 | Cross-review is a requirement, not a courtesy |
| Student laptop hardware | §3.3 | Ollama gets a 1B model and a 4 GB limit; k3d gets 2 agents |

---

## 9. Assumptions

| # | Assumption | If false |
|---|---|---|
| A-1 | Complaint text is predominantly Urdu-influenced English | The rules provider's term lists need replacing; the interface does not |
| A-2 | Free-tier quota is measured in tens of requests/minute | The limiter's numbers change; the mechanism does not |
| A-3 | Duplicate complaints are common | The cache hit rate drops and the cost argument weakens — but the correctness story is unchanged |
| A-4 | A single Postgres writer suffices at this volume | Would need read replicas and a connection pooler; the repository layer already isolates the change |
| A-5 | Operators are trusted (no auth needed for v1) | NFR gap already disclosed in §2.2 |
| A-6 | The marker runs Docker 24+ and GNU Make | Quickstart must state versions — it does |

---

## 10. Risks

| # | Risk | L | I | Mitigation | Owner |
|---|---|---|---|---|---|
| R-1 | Free-tier key revoked or region-blocked mid-build | M | H | The provider interface **is** the mitigation: `TRIAGE_PROVIDER=ollama`, §2.5 *"you lose no marks for it"*. Verified Day 0 | A |
| R-2 | HPA evidence not captured before the deadline | M | H | Scheduled Day 10, flagged wall-clock-bound in `02 §3`; no recovery path if missed | both |
| R-3 | VPA `Target` empty because the recommender lacks history | M | M | Run the full 14-minute load profile before describing; two runs scheduled | A |
| R-4 | Secret committed | L | **VH** | `.gitignore` in the first commit, pre-commit gitleaks, `history-scan`; incident runbook ready | both |
| R-5 | NetworkPolicy silently unenforced on kind | M | M | Use k3d; verify empirically; **disclose if unenforced** rather than claim | B |
| R-6 | Alembic multi-head after a merge | M | L | Only DEV-A generates migrations; `alembic merge` cure documented | A |
| R-7 | Partner under-contributing | L | **VH** | §5.4 says escalate in **week 1**; weekly `shortlog` check | both |
| R-8 | Contract churn breaking parallel work | M | M | Phase-1 freeze; changes only via `chore/contract-*` PRs; CI drift gate turns churn into a red `tsc` | both |
| R-9 | Scope creep into bonus items before P0 is done | M | M | Cut order fixed in `02 §2.2`; bonuses cannot start before Gate 7 | both |
| R-10 | Video recorded last, badly, at 3 a.m. | M | M | Day 13 script, Day 14 two takes; it is 3 marks and the most-viewed artefact | both |

---

## 11. Release plan

| Milestone | Gate | Demonstrable capability | Tag |
|---|---|---|---|
| M0 Skeleton | Gate 0–1 | repo, protection, frozen contract, CI hello | `v0.1.0` |
| M1 Persisted intake | Gate 2–3 | POST/GET/list/PATCH against real Postgres, two networks, healthchecks | `v0.2.0` |
| M2 **Replaceable reader** | Gate 4 | four providers, the fallback ladder, the injection guardrail | `v0.3.0` |
| M3 Protected and cached | Gate 5 | stats cache, distributed limiter, full CI incl. integration | `v0.4.0` |
| M4 On a cluster | Gate 6 | k8s, three probes, StatefulSet, Ingress, NetworkPolicy | `v0.5.0` |
| M5 Elastic | Gate 7 | HPA chart, VPA loop, lag explained | `v0.6.0` |
| M6 **Shippable** | Gate 8 | CD by digest, both rollbacks, docs, evidence, video | `v1.0.0` |

M2 is the release that makes the product *the product*. Everything before it is CRUD; everything
after is operations.

---

## 12. Definition of done (product level)

Adapted from §1.4, which is the bar this PRD is written against:

- [ ] A stranger clones the repository and, **with one command**, has the whole system running with seeded data
- [ ] **A second command** puts it on a Kubernetes cluster
- [ ] A push to `main` tests it, builds **signed and scanned** images, deploys them, and **can be undone in thirty seconds**
- [ ] **Everything a claim in the README asserts, we can demonstrate** — every claim has a row in `20-RUBRIC-TRACEABILITY.md`
- [ ] Both developers can explain **any** part of the submission, including the part they did not write
