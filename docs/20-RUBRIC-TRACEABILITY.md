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
| A3 | 4 | ≥5 merged PRs, each Issue-linked, each with a substantive partner review | 8 phase-gate PRs, `01-WORKFLOW.md §2.3` | live audit of all 35 merged PRs' `reviews` via `gh pr list --json reviews`: PR count clears the floor (35 ≥ 5) but 12 PRs have ZERO reviews and all reviews except 6 early ones have an EMPTY body (rubber-stamp `APPROVED`, no text) | `pr-review-audit.txt` | ☐ — PR-count sub-clause proven, "substantive partner review" sub-clause disproven |
| A4 | 3 | ≥35 commits, conventional prefixes, neither partner <35% | `01-WORKFLOW.md §2.2` | identity-merged shortlog; result depends on counting method: 35.9% (`--all` refs) vs 22.6% (`--no-merges HEAD`) — contested, not safely provable either way | `shortlog.txt` | ☐ |
| A5 | 3 | One deliberate merge conflict, resolved, + 2–4 sentences on why | `01-WORKFLOW.md §2.4`, on `schemas/stats.py` | a real merge-conflict-resolution commit exists (`0b3aad6`, frontend scaffold conflict) but NOT the specific deliberate `schemas/stats.py` exercise the row names, and none of the four named evidence files exist | none of `merge-conflict-markers.txt`/`-raw.py`/`-graph.txt`/`merge-conflict.md` exist | ☐ |

## B · Frontend — 18

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| B1 | 5 | Submit: validation, honest loading, renders category/priority/summary **and provider** | `11-FRONTEND.md §3.1` · `pages/Submit.tsx` | FE-1, FE-2, FE-3 | screenshot in README | ☐ — code exists (Submit.errors/.loading/.result tests pass, see `frontend-test-run.txt`) but no README screenshot artefact |
| B2 | 5 | Dashboard: pagination, filters, transitions, **409 verbatim** | `11-FRONTEND.md §3.2` · `pages/Dashboard.tsx` | FE-4 (exact-string assert), FE-7 | screenshot showing a 409 banner | ☐ — no screenshot artefact |
| B3 | 3 | Stats view + cache-hit state from `X-Cache` | `11-FRONTEND.md §3.3` · `components/CacheBadge.tsx` | FE-5, FE-11 | screenshot with `HIT / cached 12s ago` | ☐ — no screenshot artefact |
| B4 | 3 | Runtime configuration — one image, any environment | ADR-0002 · `api/config.ts:L1` · `nginx.conf` proxy | `runtime-config.txt` procedure | `runtime-config.txt` | ☐ — file pre-existed this session and shows the right shape (same digest, two `config.js` env blocks) but this session could not independently reproduce it (no Docker) so its authenticity as a real captured run is unverified, not confirmed |
| B5 | 2 | ≥5 meaningful component tests passing in CI | `16-TESTING.md §6` (11 tests) | ran live: 14 tests / 11 files passed; `ci.yml::test-frontend`'s own `[ "$n" -ge 5 ]` guard matches | `frontend-test-run.txt` | ☑ |

## C · Backend — 25

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| C1 | 7 | **All ten endpoints** to contract, correct codes, field-level errors | `07-BACKEND-API.md` · `routes/*` | 19 contract tests (`04-CONTRACTS.md §9` + `07 §7`); 275 unit+contract tests pass live (`test-stability.txt`) | CI run; `/docs` screenshot | ☐ — tests proven green; no `/docs` screenshot artefact exists |
| C2 | 4 | Four-layer separation; **no SQL outside `repositories`** | `05 §5`, `06 §4`, `07 §1` | ran `make lint-layers` live: exit 0, all three grep guards clean | `layer-lint-and-typecheck.txt` | ☑ |
| C3 | 3 | State machine as an **explicit transition table**; invalid → 409 | `domain/transitions.py` | read `transitions.py` directly: a real `dict[Status, frozenset[Status]]`, zero if/elif; `test_transitions.py` (4 parametrized tests) passes live | none (no `sigterm-drain.txt`-style capture; no video) | ☐ — table-not-if-chain claim verified in code; the rubric's own "AST no-if-chain" sub-claim has no matching test found, and there is no 409-body video artefact |
| C4 | 3 | `/health` vs `/ready`; `/health` does not touch the DB | `06 §5` · `routes/health.py` | unit tests for `/health`/`/ready` pass live (part of the 275); code read confirms `/health` has no DB dependency | no `kubectl describe pod` output (needs live k8s) | ☐ |
| C5 | 3 | Structured JSON logging to stdout with propagated `request_id` | `06 §3.1–3.2` | tests pass live; no log-sample artefact produced this session | RUNBOOK §3 does not exist — `docs/RUNBOOK.md` is missing from the repo entirely | ☐ |
| C6 | 2 | **SIGTERM handled**; in-flight requests drain | `06 §6` | tests pass live (part of the 275) | no `sigterm-drain.txt` exists | ☐ |
| C7 | 3 | ≥14 backend tests, deterministic, coverage ≥65% | `16-TESTING.md` (doc says 121; real count is higher) | ran `pytest -m "unit or contract"` 3x independently: 275/275 pass every time, 90.11% coverage every time (floor is 65%) | `test-stability.txt` | ☑ |

## D · Data layer — 12

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| D1 | 4 | Alembic migrations; **zero DDL in startup code** | `05 §3` · `alembic/versions/0001_initial.py` | code read: `0001_initial.py` has real DDL; `main.py` docstring + grep confirm zero DDL at startup | `static-code-audit-DEFGH.txt` (no `alembic-history.txt` — `alembic history` needs a configured DB URL, not attempted) | ☐ — implementation verified, no `alembic-history.txt` artefact |
| D2 | 3 | Schema complete incl. `triaged_by`, `ai_summary`, `triage_latency_ms`, `timestamptz` | `05 §2` · `db/models.py` | code read: all four columns/types confirmed present at `models.py:82-93` | `static-code-audit-DEFGH.txt` (no live `\d+ complaints` — needs live Postgres) | ☐ — implementation verified, no live-DB artefact |
| D3 | 2 | Two indexes, **each justified by a named query** | `05 §4` — Q-DASH-FILTER, Q-LIST-RECENT | code read: exactly 2 indexes exist (`models.py:113-114`); justified BY NAME only in `05-DATA-LAYER.md`, not as an inline code comment | `static-code-audit-DEFGH.txt` (no `explain-q-dash-filter.txt` — needs live Postgres) | ☐ |
| D4 | 3 | Idempotent seed ≥30; twice changes nothing | `05 §6` — UUIDv5 + `ON CONFLICT (id) DO NOTHING` | code read confirms UUIDv5 + `on_conflict_do_nothing`; 6 seed tests exist (`test_seed_is_idempotent`, `test_seed_ids_are_stable`, +4) but these are `integration`-marked and were NOT run live (need testcontainers Postgres, no Docker here) | `static-code-audit-DEFGH.txt` | ☐ — implementation verified in code; tests exist but unexecuted this session |

## E · Cache layer — 10

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| E1 | 3 | `/api/stats` read-through, 30 s TTL, correct `X-Cache` | `09 §2` | code read confirms literal `ttl_s: int = 30` and real hit/miss-driven header; unit tests pass live (part of the 275) | no `cache-behaviour.txt` (needs live Redis+HTTP round-trip; ci.yml's own `integration` job asserts MISS→HIT live but was not run here — no Docker) | ☐ |
| E2 | 2 | Cache **invalidated on write** | `09 §2.3` · `complaint_service.py` | code read confirms commit-then-invalidate ordering at `complaint_service.py:73-75,119-121` (the exact ordering bug PR #41 fixed) | `static-code-audit-DEFGH.txt` | ☐ — implementation verified in code; no live cache-behaviour capture |
| E3 | 4 | **Distributed** Redis limiter, 429 + `Retry-After` | `09 §4` · `lua/fixed_window.lua` | code read confirms a real atomic Lua script + shared-Redis-backed middleware (genuinely distributed, not in-process) | `static-code-audit-DEFGH.txt` (no `ratelimit-distributed.txt` — needs live Redis under concurrent load) | ☐ |
| E4 | 1 | Redis AOF on a named volume, **with your justification** | `09 §5` (five-part argument) | code read confirms `--appendonly yes --appendfsync everysec` + named volume in `compose.yaml`; `docs/ENGINEERING-NOTES.md` line 784 has a real "AOF justification" section (not literally headed `§AOF` but matching content) | `static-code-audit-DEFGH.txt` | ☑ |

## F · AI layer — 25

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| F1 | 5 | `TriageProvider` + ≥3 implementations, env-selected | `08 §1–§3` (**four** impls) | code read confirms 4 real implementations (llm/ollama/rules/simulated) + Pydantic-validated env selection in `factory.py` | `static-code-audit-DEFGH.txt` (no live `/api/meta/providers.available` capture) | ☐ — implementation verified in code; no live endpoint capture |
| F2 | 5 | Structured output requested **and validated**; malformed rejected safely | `08 §3.3`, `§5` | code read confirms `llm.py` always runs `TriageResult.model_validate_json(...)` and catches both `ValidationError`/JSON errors, never propagating raw | `static-code-audit-DEFGH.txt` (no `docs/TRIAGE.md §7` failure-log artefact checked this session) | ☐ |
| F3 | 6 | Timeout, **single jittered retry on retryable only**, fallback, `triaged_by` recorded | `08 §5` | code read confirms exactly-one retry, jittered, only on the RETRYABLE tuple (timeout/429/5xx), non-retryable breaks immediately with zero sleep, all inside a 12s budget — matches CLAUDE.md HARD rules 5/6 exactly | `static-code-audit-DEFGH.txt` (no video artefact) | ☐ — logic verified in code; no video beat |
| F4 | 3 | Content-hash caching **with a measured, reported hit rate** | `08 §6` | code read confirms real SHA-256 content-hash caching; `docs/TRIAGE.md` HONESTLY marks the hit-rate as "BLOCKED — needs a real k6 load run", no fabricated number found | `static-code-audit-DEFGH.txt` | ☐ — caching mechanism real; the rubric's specific "measured, reported hit rate" clause is not met (by design, not concealed) |
| F5 | 3 | Prompt-injection guardrail **plus a test** | `08 §4` (five layers) | code read confirms 5 documented defence layers in `prompt.py` + a 6th soft layer; injection-scenario tests exist in `test_triage_service.py`/`test_llm.py`/`test_simulated.py` and pass live (part of the 275) | `static-code-audit-DEFGH.txt` | ☑ |
| F6 | 2 | `triage_latency_ms` recorded and surfaced via `/api/meta/providers` | `07 §6`, `10 §2` | code read confirms latency recorded throughout `triage_service.py` and returned by `GET /api/meta/providers` (`routes/meta.py`) | `static-code-audit-DEFGH.txt` (no endpoint screenshot) | ☐ — implementation verified; no screenshot artefact |
| F7 | 1 | PII / data-governance ADR | ADR-0004, `17 §4` | read the file directly: 127 lines, real data-classification table, explicit provider-egress decision citing exact code paths — not a stub | `docs/adr/0004-pii-and-data-governance.md` (file itself, already existed) | ☑ |

## G · Docker and Compose — 15

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| G1 | 4 | Both images multi-stage, pinned, non-root, exec-form `CMD`, cache-correct layers | `12 §1`, `11 §5` | code read confirms both Dockerfiles: 2 stages, pinned base images, non-root `USER`, exec-form `CMD`; `check_submission.py::IMG-UNPINNED` PASS (23 manifests) | `check-submission-run.txt`, `static-code-audit-DEFGH.txt` (no real build log — no Docker) | ☐ — manifest verified in code; no actual build executed |
| G2 | 2 | `.dockerignore` per context, **before/after sizes reported** | `12 §2` | both `.dockerignore` files confirmed to exist; pre-existing `dockerignore-context-sizes.txt` has specific before/after byte counts with a commit SHA | `dockerignore-context-sizes.txt` (pre-existing, not reproduced this session — no Docker to re-measure) | ☑ (evidence pre-dates this session but is internally consistent — real SHA + specific numbers, not round/suspicious) |
| G3 | 4 | Two networks, `internal: true`, frontend **provably** cannot reach the DB | `12 §4` | code read confirms `internal: true` on the right network in `compose.yaml`; pre-existing `network-isolation.txt` shows a real failed connection attempt + a positive control | `network-isolation.txt` (pre-existing) | ☑ (config verified in code; the runtime capture is pre-existing and reads as genuine, not re-executed this session) |
| G4 | 2 | Three volumes each justified; dev bind mount present and **absent from prod** | `12 §5–§6` | code read confirms 3 named volumes (pgdata, redisdata, ollama_models), each justified by a comment (on the mount line, not the top-level declaration); confirmed dev-only bind mount in `compose.yaml` absent from `compose.prod.yaml` | `static-code-audit-DEFGH.txt` | ☑ |
| G5 | 2 | Healthchecks on all services + `depends_on: service_healthy` | `12 §8` | code read confirms all 5 long-running services have `healthcheck:` blocks and `depends_on` uses `condition: service_healthy` | `static-code-audit-DEFGH.txt` (no live `docker compose ps` — no Docker) | ☐ — config verified; not run live this session |
| G6 | 1 | `compose.prod.yaml`: `image: ${IMAGE_TAG}`, no `build:`, no DB/cache port | `12 §7` | code read + `check_submission.py::PORT-EXPOSED-PROD` PASS confirm the pattern, no `build:` key, explicit "NO ports:" comments | `check-submission-run.txt` | ☑ |

## H · Kubernetes — 20

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| H1 | 5 | Namespace, Deployments, **StatefulSet+PVC**, ClusterIP, Ingress `/` and `/api` | `13 §1–§3, §7` | code read confirms `postgres-statefulset.yaml` is `kind: StatefulSet` with `volumeClaimTemplates`, headless Service; redis/backend/frontend all `ClusterIP`; ingress has both paths; pre-existing `persistence-k8s.txt` shows a real pod-delete-and-recover test (36 rows survive) against a live k3d cluster | `persistence-k8s.txt` (pre-existing), `static-code-audit-DEFGH.txt` | ☑ (manifest verified in code; the live-cluster capture is pre-existing, not re-run this session) |
| H2 | 2 | ConfigMap/Secret separated; **placeholders only** | `13 §8` | read `secret.yaml` directly: every value is literally `PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUES`; `configmap.yaml` has no secret-shaped values; `check_submission.py::SEC-K8S-SECRET` PASS | `check-submission-run.txt` | ☑ |
| H3 | 4 | All three probes correct; liveness DB-independent, readiness DB-dependent | `13 §5` | code read confirms `backend-deployment.yaml` livenessProbe hits `/health` (comment: must not depend on DB), readinessProbe hits `/ready` (comment: should depend on it) | `static-code-audit-DEFGH.txt` (no live `kubectl get pod -o jsonpath` — no cluster) | ☐ — manifest verified; not confirmed live |
| H4 | 2 | `requests` **and** `limits` on every container | `13 §4` | walked every container spec across `k8s/base/*.yaml` and `k8s/overlays/**/*.yaml` by hand (migrate initContainer, backend, frontend, postgres, redis, prod overlay patch) — all have both `requests:` and `limits:`, no gaps found | `static-code-audit-DEFGH.txt` | ☑ |
| H5 | 4 | HPA v2 with tuned `behavior` + `hpa -w` capture + **replicas-vs-load chart** | `14 §3–§4` | code read confirms `hpa.yaml` is `autoscaling/v2` with a real tuned `behavior:` block (distinct scaleUp/scaleDown stabilization) | `static-code-audit-DEFGH.txt` — no `hpa-watch.txt`/chart/`k6-summary.json` exist; these need a live k3d/kind cluster + metrics-server + load generator | ☐ — manifest verified; the load-test artefacts are genuinely absent, BLOCKED on a live cluster |
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
| J1 | 4 | README: problem, badges, **Mermaid diagram**, working quickstart, API table, screenshots | `18 §1`, diagram from `21 §1` | read `README.md` directly: has problem statement + working quickstart (`make up`) + a second-command k8s path, but is MISSING the Mermaid diagram, badges, API table, screenshots, evidence index, ADR links, known-limitations, AI-usage link, and team/shortlog sections `18-DOCS-EVIDENCE-VIVA.md §1` requires | none — `check_submission.py::DOC-QUICKSTART` only checks that quickstart commands resolve against the Makefile, not that the README has the required sections | ☐ — quickstart genuinely works structurally; most of J1's other required sections are absent |
| J2 | 4 | **Four ADRs** | `18 §2` | read all four ADR files directly: 102 / 74 / 103 / 127 lines respectively — all comfortably over the ">40 lines" substantiveness bar; `check_submission.py::RUBRIC-ADR` PASS | `check-submission-run.txt`, `docs/adr/*` (files themselves) | ☑ |
| J3 | 2 | RUNBOOK: deploy, roll back, read logs, **what to do when triage fails** | `18 §5` | searched the entire repo (`find . -iname "*runbook*"`) — `docs/RUNBOOK.md` does not exist anywhere | none | ☐ — genuinely not written, not just missing evidence |
| J4 | 3 | Video ≤5 min, **both partners speaking**, six required beats | `18 §7` | not applicable to static evidence-closure work — this needs an actual recording session with both partners | none | ☐ — not attempted this session (requires the two human contributors) |
| J5 | 2 | ENGINEERING-NOTES answering **all eight** §5.2 questions with file:line | `18 §4` | read `docs/ENGINEERING-NOTES.md` in full (978 lines): it is a substantial, genuine running decision-log (caveman/ponytail entries, real bugs found and fixed) but does NOT contain the specific 8-question §5.2 structure (laptop-vs-CI diffs, maturity rung, build-once-deploy-many, probabilistic-component correctness, HPA lag, VPA Off rationale, `internal:true` mechanics, the >1h failure narrative) — grepped for each topic, zero matches | none | ☐ — the file is real and useful, but does not answer the specific required questions |

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
| 5.3 | frontend can reach the DB | 8 | `internal: true`; NetworkPolicy | `integration` job asserts `nc` **fails**; `NET-SEGMENT` | ☑ — `internal: true` confirmed in code; pre-existing `network-isolation.txt`/`netpol-enforcement.txt` show real failed-connection captures on both compose and k3d |
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
