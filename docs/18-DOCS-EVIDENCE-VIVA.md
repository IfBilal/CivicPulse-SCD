# 18 — DOCUMENTATION, EVIDENCE, VIDEO AND VIVA

> **Owner:** both · **Days:** 13–14 · **Gate:** Gate 8 · **Rubric:** J (15) + the evidence that
> substantiates A, H and I
> §1.4: *"Everything a claim in your README asserts, you can demonstrate."* This file is how you
> make that sentence true, and how you survive §5.4's **multiplier**.

---

## 1. `README.md` (Rubric J, 4 marks)

Required sections, in this order. A marker reads the README first and forms an opinion in ninety
seconds.

```markdown
# CivicPulse
[![ci](badge)](link) [![cd](badge)](link) [![coverage](badge)](link)
[![trivy](badge)](link) [![ghcr backend](badge)](link) [![ghcr frontend](badge)](link)

> Municipal complaint intake, AI triage and operations platform.
> Built so the reader is replaceable: keyword rule today, LLM tomorrow, classifier next year.

## The problem            ← §1.1 in three sentences, in your own words
## Architecture           ← the Mermaid diagram (21-ARCHITECTURE-DIAGRAMS.md §1)
## Quickstart             ← THE one-command promise. Tested from a clean clone. §5.3 −5 lives here.
## Second command         ← Kubernetes. §1.4's "a second command puts it on a cluster"
## API                    ← the ten-endpoint table
## Triage providers       ← the four implementations + the TRIAGE_PROVIDER switch
## Screenshots            ← Submit, Dashboard (with a 409), Stats (with X-Cache HIT), Grafana
## Configuration          ← the .env.example table
## Testing                ← how to run each suite, and the counts
## Evidence               ← index of docs/evidence/ with one line each
## ADRs                   ← the four, linked, one-line summary each
## Known limitations      ← unauthenticated dashboard, fixed-window limiter, single-region, no retention policy
## AI usage               ← link to docs/AI-USAGE.md (§5.5)
## Team                   ← both names, `git shortlog -sn` pasted
```

### 1.1 The quickstart, and why it is worth −5

```markdown
## Quickstart

Requires Docker 24+ and GNU Make. No API key needed — the default triage provider is a
deterministic local simulation.

```bash
git clone https://github.com/ORG/civicpulse.git && cd civicpulse
make up
```

Then open http://localhost:8080. `make up` builds both images, starts five containers, waits on
every healthcheck, applies migrations and seeds 36 complaints.

To use a real LLM: copy `.env.example` to `.env`, set `TRIAGE_PROVIDER=llm` and `LLM_API_KEY`,
then `make up` again.
```

**Three properties that make this survive a marker's laptop:**
1. **No key required.** `TRIAGE_PROVIDER=simulated` is the default, so a clean clone runs with no
   network and no signup. This is §1.4 taken literally.
2. **`make up` copies `.env.example` to `.env` if missing**, so step zero cannot be forgotten.
3. **`docker compose up --wait`** blocks on healthchecks, so the command returns only when the
   stack is genuinely usable — no "wait a bit then refresh" folklore.

**Test it the only way that counts** (Gate 8): the developer who did **not** write the README
clones into an empty directory on a machine with no project caches and runs exactly the pasted
commands. Record the terminal. Any manual step you discover is a −5 you just avoided.

---

## 2. The four ADRs (Rubric J, 4 marks)

Format: Context → Options considered (with a table) → Decision → Consequences → **Rejected
alternatives and why**. The last section is where the marks are; an ADR without rejected options is
a design note.

| ADR | Title | Must contain |
|---|---|---|
| **0001** | Triage provider interface | The `Protocol` shape; the **async deviation** from the spec's sync signature and why (`08-AI-TRIAGE.md §1`); retry policy incl. **why `ValidationError` is not retryable** (contradiction A14); the 12 s total budget; **why fallbacks are not cached**; the low-confidence→`other` guard; the fail-open-bounded rate-limit posture; the Groq-vs-Ollama measurement table from `docs/TRIAGE.md §4` |
| **0002** | Frontend runtime configuration | Build-time baking vs `/config.js` vs nginx proxy; **decision: proxy primary, config.js for non-URL flags**; the exact line (`API_BASE = "/api"`) that guarantees build-once-deploy-many; **and the CORS consequence** (contradiction A7) — we keep a tested `CORSMiddleware` for the direct-origin dev path so the competency §1.3 promised is still demonstrable |
| **0003** | Deploy by commit SHA / digest | Tag mutability vs digest immutability; the `needs:` gate; why `:latest` is pushed but never deployed; the rollback consequence (two mechanisms, `15-CICD.md §7`); **and the migration caveat** — a schema change makes rollback a two-artefact problem |
| **0004** | PII and data governance | The full content of `17-SECURITY-SECRETS.md §4` — inventory, egress table, four options, decision, honest limitations, deferred retention policy |

Write each ADR **when the decision is made**, not on day 13. A reconstructed ADR reads like one,
and the viva will ask *"when did you decide this?"*

---

## 3. `docs/evidence/` — the exact filename manifest

Other files in this package reference these names. `scripts/check_submission.py::RUBRIC-EVIDENCE`
asserts each exists and is non-empty.

| Filename | Produced by | Proves |
|---|---|---|
| `branch-protection.png` | Gate 0 | A1 — PR required, 1 approval, required checks, no bypass |
| `shortlog.txt` | `make evidence-shortlog` | A4 — ≥35 commits, ≥35% each (§5.8 item 5) |
| `merge-conflict-markers.txt` | Gate 4 drill | A5 — the raw `<<<<<<<` markers |
| `merge-conflict-raw.py` | Gate 4 drill | A5 — the conflicted file |
| `merge-conflict-graph.txt` | Gate 4 drill | A5 — `git log --graph` showing the merge |
| `merge-conflict.md` | Gate 4 drill | A5 — **the 2–4 sentences on why that version won** |
| `dockerignore-context-sizes.txt` | `make evidence-context` | G2 — before/after with numbers |
| `network-isolation.txt` | `make evidence-isolation` | G3, §5.3 −8 — the **failing** ping + the passing one |
| `netpol-enforcement.txt` | Gate 6 | A13 — NetworkPolicy actually enforced (or honestly not) |
| `persistence-compose.txt` | Gate 3 | D — row count survives `down`/`up` |
| `persistence-k8s.txt` | Gate 6 | H1 — row count survives `delete pod postgres-0` |
| `cache-behaviour.txt` | Gate 5 | E1, E2 — MISS→HIT→(write)→MISS→(TTL)→MISS |
| `ratelimit-distributed.txt` | Gate 5 | E3 — 429 across two replicas + the in-process negative control |
| `sigterm-drain.txt` | Gate 3 | C6 — zero 5xx during SIGTERM under load |
| `ci-red.png` | Gate 5 | I7 — red check **and greyed merge button** |
| `ci-green.png` | Gate 5 | I7 — all seven checks green |
| `ci-gate-pr-url.txt` | Gate 5 | I7 — the PR permalink for timeline verification |
| `hpa-watch.txt` | Gate 7 | H5 — `kubectl get hpa -w` with REPLICAS rising (§5.8 item 6) |
| `hpa-samples.txt` | Gate 7 | H5 — raw data behind the chart |
| `hpa-replicas-vs-load.png` | Gate 7 | H5 — **the chart**, one time axis, lag annotated |
| `k6-summary.json` | Gate 7 | H5 — thresholds passing |
| `vpa-describe-run1.txt` | Gate 7 | H6 — Target/Lower/Upper before |
| `vpa-describe-run2.txt` | Gate 7 | H6 — after the requests update |
| `vpa-step1-guess.txt` | Gate 7 | H6 — the requests you originally guessed |
| `zero-downtime-rollout.txt` | Gate 8 | bonus +4 — `http_req_failed rate==0` |
| `provider-limits-groq.png` | Day 0 | F, A12 — the live limits page **as you saw it**, dated |
| `alembic-history.txt` | Gate 2 | D1 — the migration chain |
| `explain-q-dash-filter.txt` | Gate 2 | D3 — `EXPLAIN ANALYZE` before/after the index |
| `test-stability.txt` | Gate 8 | C7 — three clean consecutive runs |
| `runtime-config.txt` | Gate 8 | B4 — one image digest, two environments |
| `grafana.png` | optional | bonus +2 |
| `incident-secret-exposure.md` | only if it happened | §5.3 rotation + note |

**Capture evidence at the moment it is true, not at the end.** A `hpa -w` capture cannot be
recreated after the cluster is deleted, and a screenshot of a green pipeline taken on day 14 does
not prove the gate blocked a merge on day 8.

---

## 4. `docs/ENGINEERING-NOTES.md` — the eight questions (Rubric J, 2 marks)

> §5.2: *"with references to your own files and lines. **Generic answers score zero.**"*

Structure each answer as: **claim → file:line → the mechanism → what breaks without it**.

| Q | The answer must contain | Source in this package |
|---|---|---|
| **1** Three laptop-vs-CI differences + the exact freezing line | e.g. (a) CPU count → `ubuntu-24.04` runner is 4-core vs your 8, frozen by `resources.limits.cpu` in `k8s/base/backend.yaml:L47`; (b) base image contents → frozen by `FROM python:3.12.7-slim-bookworm` in `backend/Dockerfile:L2`; (c) service startup order → frozen by `depends_on: condition: service_healthy` in `compose.yaml:L61`. Also legitimate: locale, timezone, filesystem case-sensitivity, Docker storage driver | `12-DOCKER-COMPOSE.md §8`, `16-TESTING.md §2` |
| **2** Maturity rung + next rung | The seven-row table with ✅/❌, then *"the next rung is automated rollback on a post-deploy SLO breach, which buys MTTR in minutes without a human"* | `15-CICD.md §8` |
| **3** The build-once-deploy-many line + what breaks | `frontend/src/api/config.ts:L1` → `export const API_BASE = "/api";` plus `proxy_pass` in `frontend/nginx.conf:L14`. Without it the bundle contains an environment as a string literal, so the SHA tag no longer identifies what is running | `11-FRONTEND.md §2`, ADR-0002 |
| **4** What "correct" means for a probabilistic component + CI determinism | *Correct* = the **contract around** the model holds: output validates against `TriageResult`, category ∈ enum, summary ≤ 140, a failure yields 201 with `rules:fallback`, latency is bounded by the budget. It does **not** mean a particular label. CI determinism via `TRIAGE_PROVIDER=simulated` seeded by `seed ^ crc32(text)`, plus injected failure modes — cite `08-AI-TRIAGE.md` F1–F24 | `08-AI-TRIAGE.md §3.2, §8` |
| **5** HPA lag in seconds + where it went + what reduces it | The ten-term table with **your measured total** | `14-LOAD-AUTOSCALING.md §5` |
| **6** Why VPA `Off` + the `Auto` failure mode | The oscillation diagram, **plus** the fact that `Auto` **evicts** to apply requests; plus the correct fix (HPA on a non-CPU metric) | `14-LOAD-AUTOSCALING.md §7.4` |
| **7** Where `internal: true` leaves the hosted-LLM caller | The precise mechanics: `internal: true` removes the gateway **for that network**; the backend is dual-homed so it retains egress; the real casualty is **Ollama**, solved with the one-shot `ollama-pull` service on `edge` sharing the volume; and the Kubernetes expression of the same intent as a NetworkPolicy | `12-DOCKER-COMPOSE.md §4.1`, `13-KUBERNETES.md §9` |
| **8** The >1h failure | **Symptoms → what you wrongly believed → the exact command or log line that told you the truth.** Candidates from this build: the `$$` escaping in the compose healthcheck; kindnet not enforcing NetworkPolicy; `<unknown>/60%` from missing requests; two Alembic heads after a merge; shell-form `CMD` swallowing SIGTERM; `kubeconform` failing on the VPA CRD; `PGDATA` and `lost+found` | pick the real one |

**Question 8 is the highest-signal answer in the document.** Write it as a narrative with the
diagnostic command quoted verbatim, e.g.: *"Symptom: `make up` hung for 300 s then timed out
on `database`. Belief: Postgres was failing to start, so I read its logs — which were clean, and that
was the clue I ignored for forty minutes. Truth: `docker inspect --format '{{json .State.Health}}'
civicpulse-database-1 | jq` showed `pg_isready -U -d`, with the variables empty. Compose had
interpolated `${POSTGRES_USER}` at parse time. The fix was `$$` in `compose.yaml:L74`. The general
lesson: a healthcheck failure and a service failure look identical from the outside, and
`docker inspect .State.Health.Log` distinguishes them in one command."*

---

## 5. `docs/RUNBOOK.md` (Rubric J, 2 marks)

Sections, each written as *commands a stranger can run at 3 a.m.*:

1. **Deploy** — normal path (merge to `main` → `cd.yml`), and manual (`kubectl apply -k`).
2. **Roll back** — both mechanisms, the decision table (`15-CICD.md §7.3`), and the migration caveat.
3. **Read the logs** — `kubectl logs -l app=backend --all-containers | jq 'select(.request_id=="…")'`;
   how a citizen's `X-Request-ID` reaches you; what each log level means here.
4. **Triage is failing** — §J names this explicitly. Trigger: the fallback-rate PromQL
   (`10-OBSERVABILITY.md §4`). Steps: check `/api/meta/providers.recent` for `error_class`; if 429 →
   the org-level limit is exhausted, switch `TRIAGE_PROVIDER=ollama` via ConfigMap + rollout
   restart; if timeout → check the provider status page; if `ValidationError` → the model changed
   its output shape, inspect `docs/TRIAGE.md §7` and bump the prompt version. **Expected impact:**
   classification quality degrades, intake does not stop.
5. **Database is down** — readiness goes 503 cluster-wide, pods leave the Service, `/health` stays
   200 so nothing restart-loops (this is the design, say so); check `postgres-0`, check the PVC is
   bound, check connection count against `max_connections`.
6. **Redis is down** — stats degrade to MISS, limiter fails open with forced `rules` provider,
   readiness 503. Check `maxmemory` evictions first.
7. **Scale-out is not happening** — `kubectl top pods` first, then `describe hpa`, then check
   `resources.requests` exists. The three-step order is the whole runbook entry.
8. **Rotate a credential** — the seven-step incident procedure (`17-SECURITY-SECRETS.md §3`).
9. **Restore from backup** — `make db-dump` output, `psql < dump.sql`, and the honest note that
   there is no automated backup schedule in v1.

---

## 6. `docs/AI-USAGE.md` (§5.5)

Append **as you go**, one entry per session, with the format in `01-WORKFLOW.md §4`.
Required fields: date, branch, tool, what it **shaped**, what it **wrote** (with file:line), **what you
changed afterwards and why**.

> §5.5: *"Specific disclosure carries no penalty whatsoever."* And: *"the viva does not care who
> wrote a line, only whether you can defend it."*

End with a summary table so a marker can see the shape at a glance:

| Area | AI-shaped | AI-written (reviewed) | Hand-written | Notes |
|---|---|---|---|---|
| Backend routes/services | planning | ~40% scaffolding | ~60% | all retry/fallback logic hand-verified against §2.5 |
| Alembic migrations | — | 0% | 100% | autogenerate rejected for native enums and the trigger |
| k8s manifests | review | ~50% | ~50% | probe tuning and NetworkPolicy hand-written |
| CI/CD | planning | ~60% | ~40% | `needs:` gating and permissions hand-audited against §5.3 |
| Tests | decomposition | ~30% | ~70% | every assertion hand-checked by stashing the implementation |
| Docs/ADRs | outline | ~20% | ~80% | all decisions are ours; ADR-0004 entirely hand-written |

**The most valuable entries are the ones where you overruled the tool.** Keep at least three, with
the spec clause you cited when overruling. That is the artefact that converts §5.5 from a
compliance chore into evidence of judgement.

---

## 7. The demo video (Rubric J, 3 marks · ≤ 5:00 · **both partners speaking**)

### 7.1 Timing budget

| # | Beat | Time | Who | Shot |
|---|---|---|---|---|
| 0 | Title + one-sentence problem | 0:00–0:15 | A | slide |
| 1 | **Clean clone → running system** | 0:15–1:00 | A | terminal: `git clone`, `make up`, healthchecks going healthy, browser at :8080 with seeded dashboard |
| 2 | **AI triage** | 1:00–1:40 | A | Submit a burst-main complaint in Urdu-influenced English → result card shows `water`, `high`, summary, `llm:groq`, latency. Then submit it **again** → cache hit, near-zero latency |
| 3 | **Fallback** | 1:40–2:20 | B | Break the key (`kubectl set env` or compose env), submit again → **still 201**, badge shows `rules:fallback`, and the WARNING log line on screen. *"A user never sees a 500 because a third party was rate-limited."* |
| 4 | **Network isolation failing** | 2:20–2:50 | B | `docker compose exec frontend ping database` → fails. Then the same from `backend` → succeeds. Two commands, one point |
| 5 | **HPA scaling** | 2:50–3:40 | A | `kubectl get hpa -w` in one pane, k6 in another, pods appearing in a third; then cut to the replicas-vs-load chart |
| 6 | **Rollback, both ways** | 3:40–4:35 | B | `rollout undo` with a stopwatch on screen (< 30 s), then the declarative re-apply; state **when you would use each** |
| 7 | Close: bonus items + repo link | 4:35–5:00 | both | |

### 7.2 Production rules

- **Both partners audibly speaking.** Rubric says so. Alternate beats; do not have one person
  narrate while the other says "yes" once.
- **Terminal font ≥ 16pt.** A marker may watch at 720p on a phone. Unreadable is unmarked.
- **No dead air.** Pre-pull images, pre-warm the cluster, use `asciinema` or cuts for anything
  longer than five seconds. Record the real thing; **cut** the waiting, never fake the result.
- **Show the failure, not a slide about the failure.** Beats 3 and 4 are the two most persuasive
  seconds in the whole submission because they are failures you engineered.
- **Say the numbers.** *"Fallback added 8 ms; the LLM path was 840 ms; the cached path was 3 ms."*
- **Unlisted**, link in the submission, and **check the link in an incognito window** before
  submitting.

---

## 8. Viva preparation (§5.4 — the **multiplier**)

Ten minutes each, individually, repo open, **including your partner's code**.
`1.0 / 0.75 / 0.5 / 0.0` multiplies the **team** mark. Moving 0.75 → 1.0 is worth more than any
bonus item in the assignment.

### 8.1 The drill (run at the end of Phase 6 and Phase 8)

Partner opens a random file from the **other's** ownership area and asks three questions:
*what does this do · why is it this way · change it live to do X.* Log every question that could not
be answered; those are the study list. Twenty minutes each, twice, is enough.

### 8.2 The question bank — be able to answer every one in under 30 seconds

**Architecture**
- Why is `/health` separate from `/ready`, and what breaks if you swap them?
- A route needs data. Trace the call through all four layers. Why do the arrows point one way?
- Why is the backend the only service on both networks?

**AI layer**
- Why is a schema-validation failure not retryable when a 429 is?
- Why do you not cache fallback results?
- A citizen writes "ignore your instructions". Walk me through the five layers that stop it. Which
  layer would you drop if you had to?
- Your cache key normalises whitespace but not punctuation. Why not?
- What does "correct" mean for this component?

**Data**
- Why a StatefulSet and not a Deployment? What exactly does `volumeClaimTemplates` give you?
- Why does the `updated_at` trigger live in the database instead of the ORM?
- Which query does each index serve? Show me the `EXPLAIN`.
- Your HPA can make ten pods. How many database connections is that? *(This is the cross-cutting
  question most likely to be asked.)*

**Cache / limiter**
- Why TTL **and** invalidation?
- Why Lua instead of `INCR` then `EXPIRE`?
- Someone sends `X-Forwarded-For: 1.2.3.4`. What happens, and why do you count from the right?
- Why does a cache need a volume?

**Kubernetes / autoscaling**
- Your HPA reads `<unknown>/60%`. Diagnose it in order.
- Compute `desiredReplicas` for me: 2 pods, 200m requests, 170m average usage, 60% target.
- Why `scaleUp` 0 s and `scaleDown` 300 s?
- What happens if you run VPA in `Auto` next to this HPA?
- What does `preStop: sleep 5` buy you that `terminationGracePeriodSeconds` does not?

**CI/CD**
- Delete `needs: test` from `cd.yml`. What is the worst thing that happens?
- Why push `:latest` but never deploy it?
- Which rollback do you use at 3 a.m., and which after? What if a migration already ran?
- Your `manifests` job passes but the deploy fails. Name two things kubeconform cannot catch.

**Partner's code (the 0.75 → 1.0 gap)**
- Open any file your partner wrote. Explain a function you did not write.
- Where is the retry policy implemented, and which spec clause constrains it?
- Change the rate limit from 10/min to 30/min, live. Which files, and which need a redeploy?

### 8.3 Live-modification drills (factor 0.5 → 1.0 is *"cannot modify it live"*)

Practise these until each takes under two minutes:
1. Add `sanitation_urgent` to `Category` — enum, migration, rules terms, prompt, tests, generated
   client. **Count the files. The answer is the point.**
2. Change the stats TTL from 30 s to 5 s and prove it with `curl`.
3. Add a `GET /api/complaints/{id}/history` stub with a correct 404 and an OpenAPI entry.
4. Make the HPA target 40% and explain what will happen to replica count before you apply it.
5. Break `/ready` deliberately and show what Kubernetes does, then fix it.

> Drill 1 is the best single preparation exercise in the list: it walks every layer of the system and
> it is exactly the kind of "change it live" task §5.4 describes.
