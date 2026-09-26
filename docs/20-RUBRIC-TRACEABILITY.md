# 20 — RUBRIC TRACEABILITY MATRIX

> **Owner:** both · **Updated at every phase gate** · **The single sheet you walk into the viva with.**
>
> Every scoring line in `00-SPEC.md §4`, mapped to: where it is implemented, the test that proves
> it, the evidence artefact a marker can open, and a status. Status is `PROVEN` only when the test
> is green **and** the artefact exists. Anything else is `PENDING`.
>
> **Totals:** rubric body sums to **175** (contradiction A1 — cover says 150). Bonus caps at **+15**.
> Deductions total **−101**. Work the deduction column first; see `02-CRITICAL-PATH.md §7`.

---

## A · Collaboration and version control — 15

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| A1 | 3 | `main` protected: no direct push, PR required, CI required, ≥1 approval | GitHub ruleset, `03-REPO-BOOTSTRAP.md §9` | live `gh api .../rulesets/23726494` — PR+CODEOWNERS review, all 7 CI jobs required, `current_user_can_bypass: never` | `branch-protection.png`, `branch-ruleset.json` | ☑ |
| A2 | 2 | Two-branch model + feature branches; nothing direct to `main` | `01-WORKFLOW.md §2` | `origin/main`'s 8 commits are squash-merged PRs only (no non-PR direct pushes); `check_submission.py::VCS-DIRECT-MAIN` PASS | `check-submission-run.txt` | ☑ — NOTE: `origin/main` is currently stale/diverged from `origin/dev` (58 commits behind, not a strict ancestor) — the *discipline* holds, but `main` itself needs a `dev`→`main` PR before submission; see handover |
| A3 | 4 | ≥5 merged PRs, each Issue-linked, each with a substantive partner review | 8 phase-gate PRs, `01-WORKFLOW.md §2.3` | live audit, re-run this session (`gh pr list --json reviews`, 42 merged PRs now, including this session's own #49-53): PR-count sub-clause clears the floor (42 ≥ 5); "substantive partner review" sub-clause is DISPROVEN and has gotten WORSE, not better — 26 of 42 PRs have zero reviews, a further 10 have only empty-body rubber-stamp approvals, leaving only 6 of 42 with anything resembling a real review comment | `pr-review-audit.txt`, `pr-review-audit-live.txt` | ☐ — genuinely unfixable by any further automation; requires the human partner to leave real review comments on outstanding PRs going forward, and cannot be retroactively applied to already-merged PRs |
| A4 | 3 | ≥35 commits, conventional prefixes, neither partner <35% | `01-WORKFLOW.md §2.2` | identity-merged shortlog; result depends on counting method: 35.9% (`--all` refs) vs 22.6% (`--no-merges HEAD`) — contested, not safely provable either way | `shortlog.txt` | ☐ |
| A5 | 3 | One deliberate merge conflict, resolved, + 2–4 sentences on why | `01-WORKFLOW.md §2.4`, on `schemas/stats.py` | `01-WORKFLOW.md §2.4` is explicit this is **scheduled, two-person work**: both partners independently branch from the same `dev` SHA and each add a real field to `StatsResponse` (`by_status`, `cache_age_seconds` — both fields already exist in the shipped schema, so the underlying feature work is done, just not via this ceremony). This cannot be honestly produced by a single Claude Code session acting alone — doing so would be a fabricated conflict, not the real collaborative exercise the rubric is testing. A different, genuinely real merge conflict WAS resolved this session (`docs/AI-USAGE.md`, an append-only log, conflicted across PR #48's `dev`→`main` promotion and again across PR #53's rebase) — real markers, real resolution, real reasoning (kept both sides' entries since the log is additive, not exclusive) — but it is not the specific `schemas/stats.py` two-person exercise this row names | none of `merge-conflict-markers.txt`/`-raw.py`/`-graph.txt`/`merge-conflict.md` exist for the `schemas/stats.py` exercise specifically | ☐ — genuinely requires the two human partners to run the scheduled exercise in `01-WORKFLOW.md §2.4` together; not something any further automation can close |

## B · Frontend — 18

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| B1 | 5 | Submit: validation, honest loading, renders category/priority/summary **and provider** | `11-FRONTEND.md §3.1` · `pages/Submit.tsx` | live Playwright session against real compose: empty-submit shows real field errors ("Must be at least 10 characters"/"...3 characters"); a real POST creates a complaint visible on the Dashboard with real category/priority/summary/provider badges | `screenshots/submit-form-empty.png`, `screenshots/submit-form-validation.png`, `screenshots/dashboard-expanded.png` | ☑ |
| B2 | 5 | Dashboard: pagination, filters, transitions, **409 verbatim** | `11-FRONTEND.md §3.2` · `pages/Dashboard.tsx` | live Playwright session: real filter/sort/per-page controls, real pagination ("Showing 1-20 of 50"), a genuine invalid transition (Open→Resolved) clicked in the UI produces the exact server message `"Cannot transition from 'open' to 'resolved'."` displayed verbatim as a banner | `screenshots/dashboard-view.png`, `screenshots/dashboard-409-conflict.png` | ☑ |
| B3 | 3 | Stats view + cache-hit state from `X-Cache` | `11-FRONTEND.md §3.3` · `components/CacheBadge.tsx` | live Playwright session: first load shows `MISS computed just now`, a reload shows `HIT cached 15s ago` — the exact worked example this rubric row itself specifies | `screenshots/stats-view.png`, `screenshots/stats-view-cache-hit.png` | ☑ |
| B4 | 3 | Runtime configuration — one image, any environment | ADR-0002 · `api/config.ts:L1` · `nginx.conf` proxy | live `curl localhost:8080/config.js` against the real running frontend container: `window.__CIVICPULSE__ = { env: "dev", version: "dev", statsPollMs: 15000, showCacheBadge: true }` — generated at container start by the entrypoint, not baked into the image | `runtime-config-live.txt` | ☑ |
| B5 | 2 | ≥5 meaningful component tests passing in CI | `16-TESTING.md §6` (11 tests) | ran live: 14 tests / 11 files passed; `ci.yml::test-frontend`'s own `[ "$n" -ge 5 ]` guard matches | `frontend-test-run.txt` | ☑ |

## C · Backend — 25

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| C1 | 7 | **All ten endpoints** to contract, correct codes, field-level errors | `07-BACKEND-API.md` · `routes/*` | 19 contract tests (`04-CONTRACTS.md §9` + `07 §7`); 275 unit+contract tests pass live (`test-stability.txt`); live Swagger UI screenshot against the real running backend (`/docs`, OAS 3.1) shows all documented operations: complaints CRUD, stats, meta/providers, health/ready | `test-stability.txt`, `screenshots/swagger-docs.png` | ☑ |
| C2 | 4 | Four-layer separation; **no SQL outside `repositories`** | `05 §5`, `06 §4`, `07 §1` | ran `make lint-layers` live: exit 0, all three grep guards clean | `layer-lint-and-typecheck.txt` | ☑ |
| C3 | 3 | State machine as an **explicit transition table**; invalid → 409 | `domain/transitions.py` | read `transitions.py` directly: a real `dict[Status, frozenset[Status]]`, zero if/elif; `test_transitions.py` (4 parametrized tests) passes live; live API call forcing `open→resolved` (not in `TRANSITIONS[OPEN]`) returns a real 409 with `{"code":"invalid_transition","details":{"from":"open","to":"resolved","allowed_from_current":["in_progress","rejected"]}}`, and the same invalid transition clicked in the real UI surfaces that exact message verbatim | `409-response.txt`, `screenshots/dashboard-409-conflict.png` | ☑ — table-not-if-chain and the live 409 both proven; no separate AST-based "no if-chain" static-analysis test exists, and there is no video artefact (video is a separate, later Gate 8 deliverable, not part of this row) |
| C4 | 3 | `/health` vs `/ready`; `/health` does not touch the DB | `06 §5` · `routes/health.py` | live compose test with Postgres stopped: `/health` stays 200, `/ready` returns 503 with body naming `postgres` explicitly (`{"failed":["postgres"]}`), recovers to 200 once Postgres is back | `health-vs-ready.txt` | ☑ |
| C5 | 3 | Structured JSON logging to stdout with propagated `request_id` | `06 §3.1–3.2` | live request against real compose: response header `x-request-id: e7d8e4af-...`; the corresponding stdout log line is real structured JSON with the SAME `request_id`, plus `method`/`path`/`status_code`/`duration_ms` | `log-sample-live.txt`, `docs/RUNBOOK.md §3` | ☑ |
| C6 | 2 | **SIGTERM handled**; in-flight requests drain | `06 §6` | live concurrent-load test against real compose: `docker compose kill -s SIGTERM backend` mid-load — 144 requests already in flight at kill time: 0 failures (100% drained cleanly); new requests sent after the kill fail until the single-replica container restarts, which is expected compose behaviour (no orchestrator to route around a single instance), not a drain-logic defect | `sigterm-drain.txt` | ☑ — in-flight drain proven; the file also discloses the separate single-replica-outage caveat honestly rather than overclaiming zero-downtime |
| C7 | 3 | ≥14 backend tests, deterministic, coverage ≥65% | `16-TESTING.md` (doc says 121; real count is higher) | ran `pytest -m "unit or contract"` 3x independently: 275/275 pass every time, 90.11% coverage every time (floor is 65%) | `test-stability.txt` | ☑ |

## D · Data layer — 12

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| D1 | 4 | Alembic migrations; **zero DDL in startup code** | `05 §3` · `alembic/versions/0001_initial.py` | live `alembic history --verbose` against real Postgres confirms migration `0001` is the only revision, hand-written (not autogenerated); `docker compose logs backend \| grep -i "create table\|alter table"` returns nothing across a full startup | `alembic-history-live.txt`, `no-startup-ddl-check.txt` | ☑ |
| D2 | 3 | Schema complete incl. `triaged_by`, `ai_summary`, `triage_latency_ms`, `timestamptz` | `05 §2` · `db/models.py` | live `\d+ complaints` against real Postgres: all four columns present with correct types (`triaged_by_enum`, `character varying(140)`, `integer`, `timestamp with time zone`), plus all 6 CHECK constraints and the `updated_at` trigger | `schema-dump-live.txt` | ☑ |
| D3 | 2 | Two indexes, **each justified by a named query** | `05 §4` — Q-DASH-FILTER, Q-LIST-RECENT | live `\d+ complaints` confirms both named indexes exist; live `EXPLAIN (ANALYZE, BUFFERS)` before/after dropping+recreating `ix_complaints_status_priority` for the exact Q-DASH-FILTER query from `05-DATA-LAYER.md` | `schema-dump-live.txt`, `explain-q-dash-filter.txt` | ☑ — indexes and their structural correctness proven live; the doc's own "Seq Scan → Bitmap Index Scan" viva line does NOT appear at this row count (~50 seeded rows) — Postgres's planner correctly prefers a sequential scan at this scale, disclosed honestly in the evidence file rather than hidden; re-run against a larger seeded table to see the transition |
| D4 | 3 | Idempotent seed ≥30; twice changes nothing | `05 §6` — UUIDv5 + `ON CONFLICT (id) DO NOTHING` | live compose run: `python -m app.cli.seed` twice against a real Postgres — "36 rows attempted, 36 rows now in complaints" both times, identical | `seed-idempotency.txt` | ☑ |

## E · Cache layer — 10

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| E1 | 3 | `/api/stats` read-through, 30 s TTL, correct `X-Cache` | `09 §2` | live compose test: first `/api/stats` read → `MISS`, second → `HIT`, real Redis round-trip | `cache-behaviour.txt` | ☑ |
| E2 | 2 | Cache **invalidated on write** | `09 §2.3` · `complaint_service.py` | live compose test: after MISS→HIT, a real `POST /api/complaints` (201) forces the next `/api/stats` read back to `MISS` | `cache-behaviour.txt` | ☑ |
| E3 | 4 | **Distributed** Redis limiter, 429 + `Retry-After` | `09 §4` · `lua/fixed_window.lua` | live compose test: 9 POSTs succeed (201), 10th+ return 429 with a real `Retry-After: 18` header; confirmed the limiter key (`rl:<ip>`) lives in Redis itself (`redis-cli KEYS`), proving shared/distributed state, not per-process | `ratelimit-distributed.txt` | ☑ |
| E4 | 1 | Redis AOF on a named volume, **with your justification** | `09 §5` (five-part argument) | code read confirms `--appendonly yes --appendfsync everysec` + named volume in `compose.yaml`; `docs/ENGINEERING-NOTES.md` line 784 has a real "AOF justification" section (not literally headed `§AOF` but matching content) | `static-code-audit-DEFGH.txt` | ☑ |

## F · AI layer — 25

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| F1 | 5 | `TriageProvider` + ≥3 implementations, env-selected | `08 §1–§3` (**four** impls) | live `GET /api/meta/providers` against real compose: `"available":["llm","ollama","rules","simulated"]`, `"active":"simulated"` (env-selected via `TRIAGE_PROVIDER`) | `meta-providers-live.txt` | ☑ |
| F2 | 5 | Structured output requested **and validated**; malformed rejected safely | `08 §3.3`, `§5` | **THE critical safety test, live**: spun up a real backend container with `SIMULATED_FAILURE_MODE=malformed` against the running compose stack's real Postgres/Redis — a real `POST /api/complaints` still returns 201 with `triaged_by:"rules:fallback"`, and the container's own stdout log shows exactly one WARNING (`"attempts":1`) naming `provider` and `error_class:"SimulatedMalformedResponseError"` — zero retries on a validation failure, per CLAUDE.md HARD rule 6 | `malformed-provider-test-live.txt` | ☑ |
| F3 | 6 | Timeout, **single jittered retry on retryable only**, fallback, `triaged_by` recorded | `08 §5` | **live, on real infrastructure**: (a) `SIMULATED_FAILURE_MODE=raise` — provider always raises, real POST still returns 201 with `triaged_by:"rules:fallback"` (`fallback-test-live.txt` — this is CLAUDE.md's own "the single most important test in the codebase," run for real, not simulated); (b) `SIMULATED_FAILURE_MODE=rate_limit` — real POST returns 201, log shows `"attempts":2"` (one retry, not zero, not two), total round-trip 596ms, well inside the 12s budget (`ratelimit-provider-test-live.txt`) | `fallback-test-live.txt`, `ratelimit-provider-test-live.txt` | ☑ |
| F4 | 3 | Content-hash caching **with a measured, reported hit rate** | `08 §6` | live `GET /api/meta/providers` against real Redis-backed compose: `"cache":{"hits":2,"misses":2,"hit_rate":0.5}` — a real, live-measured, non-zero, non-fabricated hit rate, not a template number | `meta-providers-live.txt` | ☑ — this session's own live capture supersedes `docs/TRIAGE.md`'s earlier "BLOCKED — needs a real k6 load run" disclosure for the caching-mechanism claim specifically; a full k6-driven hit-rate benchmark (Phase 7/8 scope) is separate and still pending |
| F5 | 3 | Prompt-injection guardrail **plus a test** | `08 §4` (five layers) | code read confirms 5 documented defence layers in `prompt.py` + a 6th soft layer; injection-scenario tests exist in `test_triage_service.py`/`test_llm.py`/`test_simulated.py` and pass live (part of the 275) | `static-code-audit-DEFGH.txt` | ☑ |
| F6 | 2 | `triage_latency_ms` recorded and surfaced via `/api/meta/providers` | `07 §6`, `10 §2` | live `GET /api/meta/providers`: `"recent"` array has real entries each with `latency_ms`, `provider`, `fallback`, `cached`, `error_class`, `at` — matches the ring-buffer shape exactly | `meta-providers-live.txt` | ☑ |
| F7 | 1 | PII / data-governance ADR | ADR-0004, `17 §4` | read the file directly: 127 lines, real data-classification table, explicit provider-egress decision citing exact code paths — not a stub | `docs/adr/0004-pii-and-data-governance.md` (file itself, already existed) | ☑ |

## G · Docker and Compose — 15

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| G1 | 4 | Both images multi-stage, pinned, non-root, exec-form `CMD`, cache-correct layers | `12 §1`, `11 §5` | live `docker compose up --build` produced real images (backend 333MB, frontend 34.2MB); `docker compose exec ... id` on both running containers confirms `uid=10001(app)` (non-root); `docker inspect ... .Config.Cmd` confirms exec-form JSON arrays on both (`["uvicorn",...]`, `["nginx","-g","daemon off;"]`) | `image-build-evidence-live.txt` | ☑ |
| G2 | 2 | `.dockerignore` per context, **before/after sizes reported** | `12 §2` | both `.dockerignore` files confirmed to exist; pre-existing `dockerignore-context-sizes.txt` has specific before/after byte counts with a commit SHA | `dockerignore-context-sizes.txt` (pre-existing, not reproduced this session — no Docker to re-measure) | ☑ (evidence pre-dates this session but is internally consistent — real SHA + specific numbers, not round/suspicious) |
| G3 | 4 | Two networks, `internal: true`, frontend **provably** cannot reach the DB | `12 §4` | re-verified live this session: `docker compose exec frontend nc -z -w2 database 5432` — DNS resolution itself fails ("bad address"), the frontend container has no route to the `internal` network at all | `network-isolation.txt`, `network-isolation-recheck.txt` | ☑ |
| G4 | 2 | Three volumes each justified; dev bind mount present and **absent from prod** | `12 §5–§6` | code read confirms 3 named volumes (pgdata, redisdata, ollama_models), each justified by a comment (on the mount line, not the top-level declaration); confirmed dev-only bind mount in `compose.yaml` absent from `compose.prod.yaml` | `static-code-audit-DEFGH.txt` | ☑ |
| G5 | 2 | Healthchecks on all services + `depends_on: service_healthy` | `12 §8` | live `docker compose ps` against real running stack: backend/cache/database/frontend all report `healthy` | `compose-healthchecks-live.txt` | ☑ |
| G6 | 1 | `compose.prod.yaml`: `image: ${IMAGE_TAG}`, no `build:`, no DB/cache port | `12 §7` | code read + `check_submission.py::PORT-EXPOSED-PROD` PASS confirm the pattern, no `build:` key, explicit "NO ports:" comments | `check-submission-run.txt` | ☑ |

## H · Kubernetes — 20

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| H1 | 5 | Namespace, Deployments, **StatefulSet+PVC**, ClusterIP, Ingress `/` and `/api` | `13 §1–§3, §7` | live k3d cluster, real `kubectl apply -k k8s/overlays/dev`: `kubectl get all` shows `statefulset.apps/postgres` (not a Deployment), all four Services `ClusterIP` only, Ingress with both paths; `kubectl delete pod postgres-0` then re-seed reports the same 36 rows, proving the PVC-backed StatefulSet survives pod loss | `k8s-get-all-live.txt`, `persistence-k8s-live.txt` | ☑ |
| H2 | 2 | ConfigMap/Secret separated; **placeholders only** | `13 §8` | read `secret.yaml` directly: every value is literally `PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUES`; `configmap.yaml` has no secret-shaped values; `check_submission.py::SEC-K8S-SECRET` PASS | `check-submission-run.txt` | ☑ |
| H3 | 4 | All three probes correct; liveness DB-independent, readiness DB-dependent | `13 §5` | live k3d cluster: `kubectl get pod -o jsonpath` on real running backend pods shows all three probes wired exactly as designed — liveness `/health` (10s period, DB-independent), readiness `/ready` (5s period, DB-dependent), startup `/health` (30 attempts × 2s, generous cold-start tolerance) | `probe-config.txt` | ☑ |
| H4 | 2 | `requests` **and** `limits` on every container | `13 §4` | walked every container spec across `k8s/base/*.yaml` and `k8s/overlays/**/*.yaml` by hand (migrate initContainer, backend, frontend, postgres, redis, prod overlay patch) — all have both `requests:` and `limits:`, no gaps found; confirmed live via `kubectl describe deploy` on the real k3d cluster (backend: 50m/500m CPU, 128Mi/256Mi mem; frontend: 50m/500m CPU, 64Mi/128Mi mem) | `static-code-audit-DEFGH.txt`, `resource-requests-limits.txt` | ☑ |
| H5 | 4 | HPA v2 with tuned `behavior` + `hpa -w` capture + **replicas-vs-load chart** | `14 §3–§4` | live k3d cluster + metrics-server + a real concurrent-request load generator: `kubectl get hpa -w` captured the full real cycle — CPU 2%→101%→243%→229%→222%, replicas 2→4→6→8, held near the 60% target for several minutes, then fell back 8→6→4→2 once load stopped. `kubectl top pods` returns real numbers throughout (metrics pipeline genuinely wired, not just installed) | `hpa-watch.txt`, `kubectl-top-pods.txt` | ☑ — no `k6-summary.json`/PNG chart (no k6 binary available this session; load was a Python thread-pool generator instead), but the core rise-and-fall claim is proven with real numbers |
| H6 | 3 | VPA recommender mode, recommendations committed, **requests updated**, conflict explained | `14 §7` | code read confirms `vpa.yaml` sets `updateMode: "Off"` (recommender-only) with a header comment explaining the HPA/VPA conflict rationale | `static-code-audit-DEFGH.txt` — no `vpa-describe-run1/2.txt` exist; these need a live cluster running long enough for VPA to produce recommendations | ☐ — manifest + rationale verified; the describe-run artefacts are genuinely absent, BLOCKED on a live cluster |

## I · CI/CD — 20

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| I1 | 4 | `ci.yml` lint/type/tests on every PR, **configured as required checks** | `15 §3` | live `gh api` confirms `main`'s ruleset requires exactly the 7 job names ci.yml defines, no-bypass | `branch-protection.png`, `branch-ruleset.json` | ☑ |
| I2 | 3 | Compose integration smoke asserting a real request path | `15 §3.7` (six assertions in one job) | read `ci.yml`'s `integration` job directly: genuinely 6 assertions (triage round-trip, MISS→HIT, POST-invalidates-cache, network segmentation, 429+Retry-After, log upload) | `ci-workflow-structure.txt` (no fresh run triggered this session — CI history from before this session already shows this job passing on recent PRs, e.g. PR #43) | ☑ (structure verified in code; recent real runs on this job were green per `gh run list`) |
| I3 | 3 | Trivy scan + `kubeconform` validation in CI | `15 §3.5–3.6` | read `ci.yml`'s `scan` and `manifests` jobs directly: real Trivy HIGH/CRITICAL gate + SARIF upload, real kubeconform against both overlays | `ci-workflow-structure.txt`, `ci-red-then-green.txt` (documents the `scan` job's own real red→green history) | ☑ |
| I4 | 4 | `cd.yml` with **`needs:` gating publish**, GHCR tagged by commit SHA | `15 §4` | read `cd.yml` directly: `build-push` has `needs: test`, tags include `${{ github.sha }}` | live `gh api .../actions/workflows` shows **cd.yml has never run** — only `ci` is registered; `main` is stale/diverged from `dev`, where cd.yml actually lives | ☐ — YAML structure verified; the workflow has literally never executed, no GHCR package page exists yet |
| I5 | 3 | Deploy job on an ephemeral cluster, waits on `rollout status`, smoke-tests Ingress | `15 §4` `deploy-k8s` | read `cd.yml`'s `deploy-k8s` job directly: `needs: build-push`, real `helm/kind-action`, real `rollout status` waits, real ingress smoke test | same as I4 — cd.yml has never run | ☐ — YAML structure verified; no successful run exists |
| I6 | 2 | Secrets from GitHub Secrets, scoped token, least-privilege `permissions:` | `15 §4.3`, `17 §2` | read both workflow files directly: every job has an explicit `permissions:` block scoped to only what it needs (e.g. `scan` gets `security-events: write` with a comment explaining why, not a blanket widen); secrets only ever read via `secrets.*` | `ci-workflow-structure.txt` | ☑ |
| I7 | 1 | **Evidence of a red pipeline blocking a merge, then green** | `15 §6` | live `gh run list`/`gh pr checks` trace of PR #43's `scan` job failing (real permissions bug) across 4 runs, then going green after the dedicated fix PR #45 merged — reconstructed from real GitHub Actions API data, not screenshots | `ci-red-then-green.txt` | ☑ |

## J · Documentation, portfolio, reflection — 15

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| J1 | 4 | README: problem, badges, **Mermaid diagram**, working quickstart, API table, screenshots | `18 §1`, diagram from `21 §1` | read `README.md` directly (rebuilt in PR #50, screenshots+known-limitations refreshed this session): problem statement, 3 real badges, a Mermaid architecture diagram, working `make up` quickstart, a K8s second-command path, real API table, 5 real screenshots from a live Playwright session against the running app, a 16-row evidence index, all 4 ADRs linked, an honest current known-limitations section, AI-usage link, team section — every section `18-DOCS-EVIDENCE-VIVA.md §1` requires now present with real content, not placeholders | README.md itself; `screenshots/*.png` | ☑ — clean-clone execution by the non-authoring partner (the one sub-clause needing a second human/machine) still pending, tracked separately in the deduction-armour row below |
| J2 | 4 | **Four ADRs** | `18 §2` | read all four ADR files directly: 102 / 74 / 103 / 127 lines respectively — all comfortably over the ">40 lines" substantiveness bar; `check_submission.py::RUBRIC-ADR` PASS | `check-submission-run.txt`, `docs/adr/*` (files themselves) | ☑ |
| J3 | 2 | RUNBOOK: deploy, roll back, read logs, **what to do when triage fails** | `18 §5` | `docs/RUNBOOK.md` exists (317 lines, PR #52): §1 deploy, §2 rollback (imperative + declarative + migration caveat), §3 read logs, §4 "triage is failing" (the load-bearing section, matched against the real fallback ladder), plus DB-down/Redis-down/scale-out/credential-rotation/restore-from-backup sections beyond the minimum ask; every file:line citation in it verified against real source files, not guessed | `docs/RUNBOOK.md` | ☑ |
| J4 | 3 | Video ≤5 min, **both partners speaking**, six required beats | `18 §7` | not applicable to static evidence-closure work — this needs an actual recording session with both partners | none | ☐ — not attempted this session (requires the two human contributors) |
| J5 | 2 | ENGINEERING-NOTES answering **all eight** §5.2 questions with file:line | `18 §4` | `docs/ENGINEERING-NOTES.md` (PR #52) now has a dedicated `## The eight viva questions` section with all 8 (`### Q1` through `### Q8`) answered with real file:line citations, each verified against the actual source before writing — Q5 (HPA lag) and others requiring a live cluster are honestly marked "not yet measured" rather than fabricated, matching this session's own Phase-7-is-out-of-scope discipline | `docs/ENGINEERING-NOTES.md` §"The eight viva questions" | ☑ — the structure and honesty standard are both met; a couple of sub-answers (Q5/Q6) will get real numbers once Phase 7 evidence lands, which is expected and disclosed, not a defect in this row |

---

## Bonus — capped at +15 (the five listed items sum to exactly +15)

| Item | Marks | Implemented in | Evidence | Cut order | Status |
|---|---|---|---|---|---|
| Zero-downtime rollout under live load, **zero failed requests** | +4 | `14 §6`, `13 §6` | `zero-downtime-rollout.txt` (`rate==0` threshold) | keep — it is cheap once `preStop` exists | ☐ |
| GitOps (Argo CD / Flux) reconciling from the repo | +4 | not in this package — add `k8s/argocd/application.yaml` | Argo UI screenshot | cut 3rd | ☐ |
| Digest deploy + Cosign sign **and verify** in CI | +3 | `15 §4`, `§4.2` | `cosign verify` step log | cut 2nd | ☐ |
| Prometheus scraping `/metrics` + Grafana dashboard | +2 | `10 §5` | `grafana.png`, `docs/dashboards/civicpulse.json` | cut 1st | ☐ |
| OpenTelemetry tracing frontend → backend → LLM | +2 | `10 §6` | trace screenshot | **cut first** | ☐ |

---

## Deduction armour — the −101 column

Tick means *the guard exists **and** its detector runs in CI*.

| § | Violation | −  | Guard | Detector | Safe? |
|---|---|---|---|---|---|
| 5.3 | secret anywhere in git history | 20 | `.gitignore` first commit + pre-commit gitleaks | `make history-scan`, `SEC-ENV-HISTORY` | ☐ — gitleaks not installed in this sandbox, could not run a real history scan; `precommit-secret-block.txt` proves the pre-commit hook itself works, but that is a different guard from a full-history scan |
| 5.3 | key in a committed k8s manifest | 15 | `stringData` placeholders; deploy-time secret creation | `k8s-secret-nonplaceholder`, `manifests` grep | ☑ — read `secret.yaml` directly, every value is a literal placeholder string; `check_submission.py::SEC-K8S-SECRET` PASS |
| 5.3 | unpinned base image | 8 | explicit minor tags everywhere; digests for bonus | `IMG-UNPINNED` | ☑ — `check_submission.py::IMG-UNPINNED` PASS, 23 manifests all pinned; both Dockerfiles read directly, confirmed pinned |
| 5.3 | `localhost` service-to-service | 8 | service names; `.env.example` defaults | `make lint-localhost` in pre-commit **and** CI | ☑ — ran `make lint-localhost` live, exit 0, no hits outside healthchecks/comments |
| 5.3 | frontend can reach the DB | 8 | `internal: true`; NetworkPolicy | `integration` job asserts `nc` **fails**; `NET-SEGMENT` | ☑ — re-verified live this session on both compose (DNS resolution fails) and a real k3d cluster: frontend blocked from postgres's raw pod IP (removes DNS as a confound), backend correctly still allowed (positive control) — proves the NetworkPolicy is genuinely enforced and selective, not a blanket network failure |
| 5.3 | DB/cache port published in prod, or NodePort/LB on DB | 8 | no `ports:`; ClusterIP only | `PORT-EXPOSED-PROD`, `assert_k8s_invariants.py` | ☑ — `check_submission.py::PORT-EXPOSED-PROD` PASS; code read confirms ClusterIP on postgres/redis Services |
| 5.3 | publish/deploy job not `needs:`-gated | 8 | `needs: test` / `needs: build-push` | `CI-NEEDS` | ☑ — read `cd.yml` directly: `build-push` has `needs: test`, `deploy-k8s` has `needs: build-push`, both with an explanatory comment citing this exact deduction row |
| 5.3 | deploying `:latest` | 8 | `kustomize edit set image` to SHA/digest | `kustomize build \| grep :latest` | ☑ — `check_submission.py::CD-LATEST-DEPLOY` PASS; `cd.yml`'s deploy step pins to a content digest via `kustomize edit set image`, not the `:latest` tag it also pushes for informational purposes |
| 5.3 | Postgres as a Deployment with no PVC | 8 | StatefulSet + `volumeClaimTemplates` | `K8S-DB-DEPLOYMENT` | ☑ — `check_submission.py::K8S-DB-DEPLOYMENT` PASS; code read confirms `kind: StatefulSet` + `volumeClaimTemplates` |
| 5.3 | commits direct to `main` | 5 | protection with **no bypass** | `VCS-DIRECT-MAIN` | ☑ — `check_submission.py::VCS-DIRECT-MAIN` PASS; live ruleset API confirms `current_user_can_bypass: "never"` |
| 5.3 | README quickstart fails from clean clone | 5 | `make up` is the quickstart; CI runs it | `DOC-QUICKSTART` + cross-executed test | ☐ — `check_submission.py::DOC-QUICKSTART` only confirms the commands resolve against the Makefile; a REAL clean-clone `make up` was never executed (no Docker in this sandbox) — see handover for the exact command to close this |

---

## Contradiction decisions — the record a marker may ask about

| # | Contradiction | Our resolution | Where documented |
|---|---|---|---|
| A1 | rubric sums to 175, cover says 150 | build to all 175 lines, optimise marks/hour | `00-SPEC.md` Appendix A, `02 §7` |
| A3 | nine endpoints tabled, rubric says ten | tenth = OpenAPI surface, shipped and mapped | `04 §6.10`, README §API |
| A4 | `triaged_by` has no `simulated`/`gemini` value | enum extended (superset) | `04 §1`, `docs/TRIAGE.md` |
| A5 | `confidence` validated then discarded | persisted as `triage_confidence NUMERIC(3,2)` + low-confidence guard | `05 §2`, ADR-0001 |
| A6 | 2 weeks vs 4 weeks | 14-day critical path, 28-day expansion | `02 §5` |
| A7 | CORS "forced" then designed away | proxy primary **and** a tested CORSMiddleware for dev | ADR-0002, `06 §3.3` |
| A8 | `internal: true` vs hosted LLM | backend dual-homed keeps egress; Ollama fixed by `ollama-pull` on edge | `12 §4.1`, NOTES Q7 |
| A9 | IP-keyed limiter behind two proxies | XFF counted from the right, `TRUSTED_PROXY_HOPS` | `09 §4.3` |
| A10 | `docs/TRIAGE.md` listed, never described | written anyway, seven sections | `08 §7` |
| A12 | provider limits are second-hand in the brief | screenshot the live page, dated | `provider-limits-groq.png` |
| A13 | K8s never mentions NetworkPolicy; kindnet does not enforce | ship it, use k3d, **verify empirically or disclose** | `13 §9`, `netpol-enforcement.txt` |
| A14 | schema failure is not retryable | hard rule: straight to `rules:fallback` | `08 §5`, ADR-0001 |

---

## How to use this file

1. **At every phase gate**, tick the rows the gate produced. A row is `PROVEN` only with a green
   test **and** a real artefact — never on the strength of "the code does it."
2. **Before submission**, every A–J row must be ticked and every deduction row must be safe.
   Untickable rows become known gaps you state in README §Known limitations rather than hide.
3. **In the viva**, this is the sheet you keep open. Any question of the form *"where is X?"* has a
   row with a file path, a test name and an artefact. §5.4's factor `1.0` is *"explains any part of
   the submission"* — this table is the index into that.
