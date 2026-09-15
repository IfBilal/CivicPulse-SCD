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
| A1 | 3 | `main` protected: no direct push, PR required, CI required, ≥1 approval | GitHub ruleset, `03-REPO-BOOTSTRAP.md §9` | `check_submission.py::VCS-DIRECT-MAIN` | `branch-protection.png` | ☐ |
| A2 | 2 | Two-branch model + feature branches; nothing direct to `main` | `01-WORKFLOW.md §2` | `git log --first-parent main` has only merge commits | `shortlog.txt`, PR list | ☐ |
| A3 | 4 | ≥5 merged PRs, each Issue-linked, each with a substantive partner review | 8 phase-gate PRs, `01-WORKFLOW.md §2.3` | `check_submission.py::RUBRIC-PRS` | PR URLs in README §Team | ☐ |
| A4 | 3 | ≥35 commits, conventional prefixes, neither partner <35% | `01-WORKFLOW.md §2.2` | `RUBRIC-COMMITS` | `shortlog.txt` (§5.8 item 5) | ☐ |
| A5 | 3 | One deliberate merge conflict, resolved, + 2–4 sentences on why | `01-WORKFLOW.md §2.4`, on `schemas/stats.py` | manual | `merge-conflict-markers.txt`, `-raw.py`, `-graph.txt`, `merge-conflict.md` | ☐ |

## B · Frontend — 18

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| B1 | 5 | Submit: validation, honest loading, renders category/priority/summary **and provider** | `11-FRONTEND.md §3.1` · `pages/Submit.tsx` | FE-1, FE-2, FE-3 | screenshot in README | ☐ |
| B2 | 5 | Dashboard: pagination, filters, transitions, **409 verbatim** | `11-FRONTEND.md §3.2` · `pages/Dashboard.tsx` | FE-4 (exact-string assert), FE-7 | screenshot showing a 409 banner | ☐ |
| B3 | 3 | Stats view + cache-hit state from `X-Cache` | `11-FRONTEND.md §3.3` · `components/CacheBadge.tsx` | FE-5, FE-11 | screenshot with `HIT / cached 12s ago` | ☐ |
| B4 | 3 | Runtime configuration — one image, any environment | ADR-0002 · `api/config.ts:L1` · `nginx.conf` proxy | `runtime-config.txt` procedure | `runtime-config.txt` | ☐ |
| B5 | 2 | ≥5 meaningful component tests passing in CI | `16-TESTING.md §6` (11 tests) | `ci.yml::test-frontend` asserts count ≥5 | CI run link | ☐ |

## C · Backend — 25

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| C1 | 7 | **All ten endpoints** to contract, correct codes, field-level errors | `07-BACKEND-API.md` · `routes/*` | 19 contract tests (`04-CONTRACTS.md §9` + `07 §7`) | CI run; `/docs` screenshot | ☐ |
| C2 | 4 | Four-layer separation; **no SQL outside `repositories`** | `05 §5`, `06 §4`, `07 §1` | `make lint-layers` in `ci.yml::lint-and-type` | CI log line | ☐ |
| C3 | 3 | State machine as an **explicit transition table**; invalid → 409 | `domain/transitions.py` | C-T01…C-T20 (**16-cell matrix** + coverage + AST no-if-chain) | 409 body in the video | ☐ |
| C4 | 3 | `/health` vs `/ready`; `/health` does not touch the DB | `06 §5` · `routes/health.py` | C-C11, C-C12, C-C13, C-C14 | `kubectl describe pod` probe config | ☐ |
| C5 | 3 | Structured JSON logging to stdout with propagated `request_id` | `06 §3.1–3.2` | C-C04…C-C09, F20 | log sample in RUNBOOK §3 | ☐ |
| C6 | 2 | **SIGTERM handled**; in-flight requests drain | `06 §6` | C-S01, C-S02, C-S03 | `sigterm-drain.txt` | ☐ |
| C7 | 3 | ≥14 backend tests, deterministic, coverage ≥65% | `16-TESTING.md` (**121 tests**) | `--cov-fail-under=65` in `pyproject.toml` | `test-stability.txt`, coverage badge | ☐ |

## D · Data layer — 12

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| D1 | 4 | Alembic migrations; **zero DDL in startup code** | `05 §3` · `alembic/versions/0001_initial.py` | D1, D2, D3 | `alembic-history.txt` | ☐ |
| D2 | 3 | Schema complete incl. `triaged_by`, `ai_summary`, `triage_latency_ms`, `timestamptz` | `05 §2` · `db/models.py` | D4, D5, D6 | `\d+ complaints` output | ☐ |
| D3 | 2 | Two indexes, **each justified by a named query** | `05 §4` — Q-DASH-FILTER, Q-LIST-RECENT | D10 | `explain-q-dash-filter.txt` | ☐ |
| D4 | 3 | Idempotent seed ≥30; twice changes nothing | `05 §6` — UUIDv5 + `ON CONFLICT (id) DO NOTHING` | 6 seed tests | `RUBRIC-SEED` in check_submission | ☐ |

## E · Cache layer — 10

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| E1 | 3 | `/api/stats` read-through, 30 s TTL, correct `X-Cache` | `09 §2` | E1, E2, E3, E7, E8 | `cache-behaviour.txt` | ☐ |
| E2 | 2 | Cache **invalidated on write** | `09 §2.3` · `complaint_service.py` | E4, E5, E6 (after-commit ordering) | `cache-behaviour.txt` line 3 | ☐ |
| E3 | 4 | **Distributed** Redis limiter, 429 + `Retry-After` | `09 §4` · `lua/fixed_window.lua` | E9…E16 | `ratelimit-distributed.txt` (+ in-process negative control) | ☐ |
| E4 | 1 | Redis AOF on a named volume, **with your justification** | `09 §5` (five-part argument) | E17 | ENGINEERING-NOTES §AOF | ☐ |

## F · AI layer — 25

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| F1 | 5 | `TriageProvider` + ≥3 implementations, env-selected | `08 §1–§3` (**four** impls) | F23, F24 | `/api/meta/providers.available` | ☐ |
| F2 | 5 | Structured output requested **and validated**; malformed rejected safely | `08 §3.3`, `§5` | F2, F3, F4, F22 (no `eval`) | `docs/TRIAGE.md §7` failure log | ☐ |
| F3 | 6 | Timeout, **single jittered retry on retryable only**, fallback, `triaged_by` recorded | `08 §5` | **F1**, F5, F6, F7, F8, F9, F10, F20 | video beat 3 | ☐ |
| F4 | 3 | Content-hash caching **with a measured, reported hit rate** | `08 §6` | F11, F12, F13, F14 | `docs/TRIAGE.md §6` real numbers | ☐ |
| F5 | 3 | Prompt-injection guardrail **plus a test** | `08 §4` (five layers) | F15, F16, F17 | `docs/TRIAGE.md §3` | ☐ |
| F6 | 2 | `triage_latency_ms` recorded and surfaced via `/api/meta/providers` | `07 §6`, `10 §2` | F18, F19 | endpoint screenshot | ☐ |
| F7 | 1 | PII / data-governance ADR | ADR-0004, `17 §4` | — | `docs/adr/0004-…md` | ☐ |

## G · Docker and Compose — 15

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| G1 | 4 | Both images multi-stage, pinned, non-root, exec-form `CMD`, cache-correct layers | `12 §1`, `11 §5` | C-S03 (PID 1), `IMG-UNPINNED`, `docker exec id` | build logs; size gate in `ci.yml::build` | ☐ |
| G2 | 2 | `.dockerignore` per context, **before/after sizes reported** | `12 §2` | `measure_context.sh` | `dockerignore-context-sizes.txt` | ☐ |
| G3 | 4 | Two networks, `internal: true`, frontend **provably** cannot reach the DB | `12 §4` | `ci.yml::integration` asserts `nc` fails; `NET-SEGMENT` | `network-isolation.txt`, video beat 4 | ☐ |
| G4 | 2 | Three volumes each justified; dev bind mount present and **absent from prod** | `12 §5–§6` | manual diff of the two compose files | ENGINEERING-NOTES §Volumes | ☐ |
| G5 | 2 | Healthchecks on all services + `depends_on: service_healthy` | `12 §8` | `docker compose ps` all healthy; `up --wait` | CI `integration` log | ☐ |
| G6 | 1 | `compose.prod.yaml`: `image: ${IMAGE_TAG}`, no `build:`, no DB/cache port | `12 §7` | `PORT-EXPOSED-PROD` | the file itself | ☐ |

## H · Kubernetes — 20

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| H1 | 5 | Namespace, Deployments, **StatefulSet+PVC**, ClusterIP, Ingress `/` and `/api` | `13 §1–§3, §7` | `K8S-DB-DEPLOYMENT`, `assert_k8s_invariants.py` | `persistence-k8s.txt`, `kubectl get all` | ☐ |
| H2 | 2 | ConfigMap/Secret separated; **placeholders only** | `13 §8` | `.gitleaks.toml::k8s-secret-nonplaceholder`, `ci.yml::manifests` grep | the manifests | ☐ |
| H3 | 4 | All three probes correct; liveness DB-independent, readiness DB-dependent | `13 §5` | C-C11…C-C14 + `kubectl get pod -o jsonpath` | probe config output | ☐ |
| H4 | 2 | `requests` **and** `limits` on every container | `13 §4` | `assert_k8s_invariants.py` walks every container | `describe deploy` output | ☐ |
| H5 | 4 | HPA v2 with tuned `behavior` + `hpa -w` capture + **replicas-vs-load chart** | `14 §3–§4` | `kubectl get hpa` never `<unknown>` | `hpa-watch.txt`, `hpa-replicas-vs-load.png`, `k6-summary.json` | ☐ |
| H6 | 3 | VPA recommender mode, recommendations committed, **requests updated**, conflict explained | `14 §7` | the two describe files + the requests commit | `vpa-describe-run1/2.txt`, ENGINEERING-NOTES Q6 | ☐ |

## I · CI/CD — 20

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| I1 | 4 | `ci.yml` lint/type/tests on every PR, **configured as required checks** | `15 §3` | seven job names in branch protection | `branch-protection.png` | ☐ |
| I2 | 3 | Compose integration smoke asserting a real request path | `15 §3.7` (six assertions in one job) | the job itself | CI run link | ☐ |
| I3 | 3 | Trivy scan + `kubeconform` validation in CI | `15 §3.5–3.6` | both jobs green; SARIF in Security tab | CI run link | ☐ |
| I4 | 4 | `cd.yml` with **`needs:` gating publish**, GHCR tagged by commit SHA | `15 §4` | `CI-NEEDS` | GHCR package page with SHA tags (§5.8 item 3) | ☐ |
| I5 | 3 | Deploy job on an ephemeral cluster, waits on `rollout status`, smoke-tests Ingress | `15 §4` `deploy-k8s` | the job itself | successful `cd.yml` run (§5.8 item 2) | ☐ |
| I6 | 2 | Secrets from GitHub Secrets, scoped token, least-privilege `permissions:` | `15 §4.3`, `17 §2` | manual audit + `permissions` blocks | workflow files | ☐ |
| I7 | 1 | **Evidence of a red pipeline blocking a merge, then green** | `15 §6` | manual | `ci-red.png`, `ci-green.png`, `ci-gate-pr-url.txt` | ☐ |

## J · Documentation, portfolio, reflection — 15

| # | Marks | Rubric line | Implemented in | Proven by | Evidence | Status |
|---|---|---|---|---|---|---|
| J1 | 4 | README: problem, badges, **Mermaid diagram**, working quickstart, API table, screenshots | `18 §1`, diagram from `21 §1` | `DOC-QUICKSTART` + the cross-executed clean-clone test | README + screenshots | ☐ |
| J2 | 4 | **Four ADRs** | `18 §2` | `RUBRIC-ADR` (each >40 lines) | `docs/adr/*` | ☐ |
| J3 | 2 | RUNBOOK: deploy, roll back, read logs, **what to do when triage fails** | `18 §5` | — | `docs/RUNBOOK.md` | ☐ |
| J4 | 3 | Video ≤5 min, **both partners speaking**, six required beats | `18 §7` | — | unlisted link (§5.8 item 4) | ☐ |
| J5 | 2 | ENGINEERING-NOTES answering **all eight** §5.2 questions with file:line | `18 §4` | — | `docs/ENGINEERING-NOTES.md` | ☐ |

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
| 5.3 | secret anywhere in git history | 20 | `.gitignore` first commit + pre-commit gitleaks | `make history-scan`, `SEC-ENV-HISTORY` | ☐ |
| 5.3 | key in a committed k8s manifest | 15 | `stringData` placeholders; deploy-time secret creation | `k8s-secret-nonplaceholder`, `manifests` grep | ☐ |
| 5.3 | unpinned base image | 8 | explicit minor tags everywhere; digests for bonus | `IMG-UNPINNED` | ☐ |
| 5.3 | `localhost` service-to-service | 8 | service names; `.env.example` defaults | `make lint-localhost` in pre-commit **and** CI | ☐ |
| 5.3 | frontend can reach the DB | 8 | `internal: true`; NetworkPolicy | `integration` job asserts `nc` **fails**; `NET-SEGMENT` | ☐ |
| 5.3 | DB/cache port published in prod, or NodePort/LB on DB | 8 | no `ports:`; ClusterIP only | `PORT-EXPOSED-PROD`, `assert_k8s_invariants.py` | ☐ |
| 5.3 | publish/deploy job not `needs:`-gated | 8 | `needs: test` / `needs: build-push` | `CI-NEEDS` | ☐ |
| 5.3 | deploying `:latest` | 8 | `kustomize edit set image` to SHA/digest | `kustomize build \| grep :latest` | ☐ |
| 5.3 | Postgres as a Deployment with no PVC | 8 | StatefulSet + `volumeClaimTemplates` | `K8S-DB-DEPLOYMENT` | ☐ |
| 5.3 | commits direct to `main` | 5 | protection with **no bypass** | `VCS-DIRECT-MAIN` | ☐ |
| 5.3 | README quickstart fails from clean clone | 5 | `make up` is the quickstart; CI runs it | `DOC-QUICKSTART` + cross-executed test | ☐ |

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
