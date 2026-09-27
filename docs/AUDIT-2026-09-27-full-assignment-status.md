# Full assignment audit — 2026-09-27, post PR #58 merge

<!-- Written at the user's explicit request for an end-to-end, phase-by-phase, chunk-by-chunk
     breakdown of the entire assignment, leaving no detail unturned. Verified against real repo
     state (git log, file contents, docs/20-RUBRIC-TRACEABILITY.md), not reconstructed from
     memory. Snapshot in time — re-verify before relying on it if much time has passed. -->

## 0. Headline numbers

| | Earned | Max | % |
|---|---|---|---|
| **Rubric body (A–J)** | **155** | **175** | **88.6%** |
| **Bonus (capped)** | **4** | **15** | **26.7%** |
| **Grand total if submitted right now** | **159** | **190** | **83.7%** |
| **Deduction risk currently live** | **0 confirmed tripped** | −101 max | — |

Of **64 individually tracked rubric rows** (A1–J5 across sections A–J), **58 are ☑ (proven with
real evidence)** and **6 are ☐ (open)**. Every ☐ row has a specific, named reason it's open — none
are silently skipped or unknown-status.

---

## 1. Section-by-section breakdown (the 175-mark body)

### A · Collaboration and version control — 5/15 (33%)

| Row | Marks | Status | What's actually missing |
|---|---|---|---|
| A1 | 3 | ☑ | `main` branch protection live-verified (ruleset API, no-bypass, 7 required CI checks) |
| A2 | 2 | ☑ | Two-branch model discipline holds; **caveat**: `main` is now **82 commits behind `dev`** (grew from 78 since Phase 7 landed only on `dev`) — cosmetic per `check_submission.py`, but will need a `dev→main` promotion PR before final submission |
| A3 | 4 | ☐ | **26+ of the last 42+ merged PRs have zero review; a further 10 are empty-body rubber-stamps.** Cannot be fixed retroactively. Every PR from here forward (including #58, #59) needs a real review comment from whoever didn't write it, or the ratio keeps getting worse. |
| A4 | 3 | ☐ | Commit-share floor (35% each) is contested depending on counting method: 35.9% (`--all` refs, passes) vs 22.6% (`--no-merges HEAD`, fails). Needs a joint decision on which number you'll defend at viva — **deferred per your instruction, not attempted.** |
| A5 | 3 | ☐ | The deliberate merge-conflict exercise (`01-WORKFLOW.md §2.4`) — both partners independently branch from the same `dev` SHA, each add a different field to `schemas/stats.py`'s `StatsResponse`, merge, capture the real conflict. **Genuinely requires both of you in one sitting** (~30-45 min) — cannot be produced by a solo session without fabricating the exact thing this row tests. Exact commands are in `docs/handover/HANDOVER-to-ifbilal-phases-0-6-close-and-next-steps.md §2`, ready to run. **This is the one you said you'd do next.** |

**A-section total possible if A3/A4/A5 all close: 15/15.** Realistically, A3 cannot be fully
recovered (past PRs can't be retroactively reviewed) — expect this section's practical ceiling to
land around 11-12/15 even after A5 and future-PR review discipline improve things.

### B · Frontend — 18/18 (100%) ✅ complete

All five rows (B1–B5: Submit form, Dashboard, Stats/cache badge, runtime config, component tests)
are ☑, each with a live Playwright screenshot or live `curl`/test-run artifact. Nothing open here.

### C · Backend — 25/25 (100%) ✅ complete

All seven rows (C1–C7: 10 endpoints to contract, 4-layer separation, state machine table, health
vs ready, structured logging, SIGTERM drain, ≥14 tests/65% coverage) are ☑. 275+ tests passing,
90.11% coverage. Nothing open here.

### D · Data layer — 12/12 (100%) ✅ complete

All four rows (D1–D4: Alembic migrations, schema completeness, justified indexes, idempotent
seed) are ☑, each with live Postgres introspection evidence. Nothing open here.

### E · Cache layer — 10/10 (100%) ✅ complete

All four rows (E1–E4: read-through cache, invalidation-on-write, distributed rate limiter, AOF
justification) are ☑, each with live Redis-backed evidence. Nothing open here.

### F · AI layer — 25/25 (100%) ✅ complete

All seven rows (F1–F7: 4 triage providers, validated structured output, timeout/retry/fallback
ladder, content-hash caching with a measured hit rate, prompt-injection guardrail, latency
recording, PII/data-governance ADR) are ☑. This includes the single most safety-critical test in
the codebase (`fallback-test-live.txt` — provider always raises, still returns 201). Nothing open
here.

### G · Docker and Compose — 15/15 (100%) ✅ complete

All six rows (G1–G6: multi-stage/pinned/non-root images, `.dockerignore` sizing,
network-segmented compose, justified volumes, healthchecks, prod compose hygiene) are ☑. Nothing
open here.

### H · Kubernetes — 20/20 (100%) ✅ complete

All six rows (H1–H6) are ☑, including **H6 (VPA loop), which this session's Phase 7 work just
closed** — the two-run VPA loop (Target 813m → applied → re-measured at 763m, confirming
convergence) with real evidence on both runs. Nothing open here.

**One stale-evidence note, not a status change:** H5's "Proven by" column still describes the
*older* Python thread-pool load generator capture from a prior session (before k6 was available),
not this session's real `k6 run` capture that produced `docs/evidence/k6-summary.json` and the
regenerated `hpa-replicas-vs-load.png`. The row is still correctly ☑ either way (both captures
independently prove the same claim), but the traceability doc's own citation text should be
refreshed to point at the newer, better evidence rather than describing the superseded capture.
**This is a 2-minute doc-polish item, not a gap in what's proven.**

### I · CI/CD — 13/20 (65%)

| Row | Marks | Status | What's actually missing |
|---|---|---|---|
| I1 | 4 | ☑ | `ci.yml` required-checks wired correctly, live-verified |
| I2 | 3 | ☑ | Compose integration smoke test (6 assertions), verified by code read + recent green runs |
| I3 | 3 | ☑ | Trivy scan + kubeconform, verified by code read + real red→green history |
| I4 | 4 | ☐ | `cd.yml` structurally correct (`needs: test` gating, SHA-tagged images) but **has never actually run** — it only triggers on push to `main`, and `main` is 82 commits behind `dev`. No GHCR package page exists yet. **Blocked on a `dev→main` promotion, which is Phase 8 scope.** |
| I5 | 3 | ☐ | Same root cause as I4 — the `deploy-k8s` job (ephemeral cluster, `rollout status` wait, ingress smoke test) is structurally correct but has never executed for the same reason. |
| I6 | 2 | ☑ | Least-privilege `permissions:` blocks on every job, verified by code read |
| I7 | 1 | ☑ | Real red→green CI history reconstructed from GitHub Actions API (PR #43's `scan` job failure → PR #45's fix) |

**I4/I5 together are 7 marks that will very likely close automatically once Phase 8 promotes a
PR to `main` for the first time since Phase 7 landed** — this isn't new work, it's confirming
already-correct YAML actually fires. Flagging this as the **highest-leverage single action** in
the entire remaining list: 7 marks for essentially the cost of one clean merge to `main`.

### J · Documentation, portfolio, reflection — 12/15 (80%)

| Row | Marks | Status | What's actually missing |
|---|---|---|---|
| J1 | 4 | ☑ | README complete (problem, badges, Mermaid diagram, quickstart, API table, 5 real screenshots, evidence index, ADR links, known-limitations, AI-usage link, team section) — one sub-clause (clean-clone execution by the *non-authoring* partner) tracked separately in the deduction-armour row, not blocking this row's ☑ |
| J2 | 4 | ☑ | Four ADRs, all >40 lines, substantive |
| J3 | 2 | ☑ | RUNBOOK.md (317 lines) covers deploy/rollback/logs/triage-failure plus bonus sections |
| J4 | 3 | ☐ | **The demo video** — ≤5 min, both partners speaking, six required beats (`18-DOCS-EVIDENCE-VIVA.md §7`). **This is NOT a bonus row — it's a required 3-mark row in section J.** Cannot be done solo; needs a joint recording session. |
| J5 | 2 | ☑ | ENGINEERING-NOTES.md has all 8 viva questions answered with real file:line citations; Q5/Q6 now have real numbers from Phase 7 (this session), not placeholders |

---

## 2. Bonus section — 4/15 banked (capped pool, separate from the 175)

| Item | Marks | Status | Solo-doable? |
|---|---|---|---|
| Zero-downtime rollout, zero failed requests | +4 | ☑ **closed this session** (PR #58) — real `kubectl set image` rolling update mid-traffic, `http_req_failed rate==0.00%`, 7200/7200 succeeded | — |
| GitOps (Argo CD / Flux) reconciling from the repo | +4 | ☐ | Yes |
| Digest deploy + Cosign sign **and** verify in CI | +3 | ☐ | Yes |
| Prometheus scraping `/metrics` + Grafana dashboard | +2 | ☐ | Yes |
| OpenTelemetry tracing frontend → backend → LLM | +2 | ☐ | Yes |

**The doc's own cut-order** (if time runs out, cut in this order, meaning do these last-to-first
if only some get attempted): OpenTelemetry tracing (cut first, i.e. lowest priority) → Grafana
dashboard → Cosign sign/verify → GitOps. **In priority order for doing them: GitOps first, then
Cosign, then Grafana, then OTel** — inverse of the cut order, since the doc explicitly protects
the ones it lists as "cut last" by implication of ranking them higher.

All four remaining bonus items are genuinely solo-doable by me once Phase 8 core work is done or
in parallel with it, time permitting. None require the two of you together.

---

## 3. Deduction armour — the −101 risk column

11 tracked violations, each worth −5 to −20 marks if tripped. **9 of 11 are ☑ (guard verified
safe)**, **2 are ☐**:

| Violation | Cost | Status | Detail |
|---|---|---|---|
| Secret anywhere in git history | −20 | ☐ | `gitleaks` is not installed in this environment, so a **real full-history scan has never actually been run** this session or in recent sessions. The pre-commit hook itself is proven to work (`precommit-secret-block.txt`), which is a *different, narrower* guard than a full history scan. **This is worth fixing before submission** — install `gitleaks` (or ask IfBilal to run it on his machine) and run `make history-scan` for real, since a −20 risk sitting unverified is the single largest deduction-armour gap left. |
| README quickstart fails from clean clone | −5 | ☐ | `check_submission.py::DOC-QUICKSTART` only confirms the Makefile commands *resolve*, not that `make up` actually succeeds from a genuinely fresh `git clone` with no prior Docker state. **Also worth doing for real before submission** — costs one clean-clone `make up` run, ~10-15 minutes. |

All 9 other rows (unpinned images, `localhost` service-to-service, frontend-reaches-DB, exposed
DB/cache ports, ungated publish/deploy jobs, `:latest` deploys, Postgres-as-Deployment, direct
commits to `main`, and the ones already covered above) are verified safe with live evidence.

---

## 4. What's actually left, by who can do it

### Solo (me), any time
- **Refresh H5's stale evidence citation** to point at this session's real k6 capture instead of the superseded Python thread-pool one (2 minutes, cosmetic, doesn't change the ☑).
- **Install `gitleaks` and run a real full-history secret scan** (closes the largest unverified deduction risk, −20 if it were ever tripped).
- **Run a genuinely clean-clone `make up`** to close the README-quickstart deduction row for real.
- **Bonus items**: GitOps, Cosign sign+verify, Prometheus/Grafana, OpenTelemetry tracing (4 items, +11 marks total available, all solo-doable).
- **Phase 8** (CD/rollback) — the next real phase of implementation work, once you say go.

### Needs both of you, together, one sitting
- **A5** — the deliberate merge-conflict exercise. Cheapest remaining joint item (~30-45 min). You said this is next.
- **J4** — the demo video (≤5 min, both speaking, six beats). Not a bonus — a required 3-mark row.
- **A3/A4** — not code work, just deciding (a) how you'll defend the commit-share number at viva, and (b) accepting that A3's review-rigor score is now capped by history and can only improve going forward, never fully recovered. Explicitly deferred per your instruction.

### Needs a `dev→main` promotion (blocks 7 marks, otherwise ready)
- **I4/I5** — `cd.yml` has never fired because `main` is 82 commits stale. The very first PR that lands on `main` after Phase 8 starts should be watched closely to confirm `cd.yml` actually runs green end-to-end (build-push → deploy-k8s), which converts two structurally-verified-but-never-executed rows into fully proven ones.

---

## 5. Bottom line

- **You are at 159/190 (83.7%) if the assignment were frozen and submitted exactly as it stands right now**, with every open gap individually named and none silently missing.
- **Every remaining rubric-body gap (A3, A4, A5, I4, I5, J4) is either genuinely joint-only work or blocked on one clean `main` promotion** — there is no remaining backend/frontend/data/cache/AI/Docker/Kubernetes implementation work outstanding. Sections B through H are 100% complete.
- **The single highest-leverage remaining action is getting a PR onto `main`** (unlocks I4+I5, 7 marks, essentially free once Phase 8 starts).
- **The single cheapest remaining action is A5** (3 marks, ~30-45 minutes, needs both of you) — which is exactly what you said you're doing next.
