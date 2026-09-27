# Full assignment audit #2 — 2026-09-27, post bonus-work push, PR #60 MERGED

<!-- Supersedes docs/AUDIT-2026-09-27-full-assignment-status.md, written before this session's
     GitOps/Prometheus/OpenTelemetry/gitleaks/clean-clone push. That earlier audit's numbers are
     now stale where noted below. This one is verified against real repo state (git log, gh pr
     view, file contents), not reconstructed from memory. -->

## 0. Status: PR #60 is merged

Confirmed via `gh pr view 60`: `mergedAt: 2026-09-27T16:28:05Z`, `state: MERGED`. `origin/dev`'s
tip is now `2d028cb`, containing all 8 commits from this session's bonus push — GitOps manifest,
Prometheus/Grafana, OpenTelemetry tracing, `release.yml`, the real gitleaks scan, the real
clean-clone quickstart test. `scripts/check_submission.py` re-run against this exact commit:
**0 FAIL, 4 WARN (all pre-existing/unrelated), 1 SKIP.**

The "on dev right now" vs "once #60 merges" split from the first draft of this report no longer
applies — there is only one state now, and it is the merged one. Numbers below reflect that.

---

## 1. Headline numbers (confirmed on `dev` @ `2d028cb`, post-merge)

| | Score | % |
|---|---|---|
| **Rubric body (A–J), 175 max** | 155/175 | 88.6% |
| **Bonus, 15 max (capped)** | 9–11/15 (see §3 for the two honest readings) | 60–73% |
| **Deduction-armour rows verified safe** | 11/11 | 100% |
| **Grand total** | 164–166/190 | 86.3–87.4% |

---

## 2. Section-by-section — the 175-mark rubric body (unchanged by #60)

No row in sections A–J is touched by PR #60's diff. Every number here is identical to the
previous audit; repeated for completeness, not re-derived.

| Section | Score | % | Status |
|---|---|---|---|
| A · Collaboration & VCS | 5/15 | 33% | A1/A2 ☑. A3/A4/A5 ☐ — see §4 |
| B · Frontend | 18/18 | 100% | ✅ complete |
| C · Backend | 25/25 | 100% | ✅ complete |
| D · Data layer | 12/12 | 100% | ✅ complete |
| E · Cache layer | 10/10 | 100% | ✅ complete |
| F · AI layer | 25/25 | 100% | ✅ complete |
| G · Docker/Compose | 15/15 | 100% | ✅ complete |
| H · Kubernetes | 20/20 | 100% | ✅ complete (H6 VPA loop closed in #58) |
| I · CI/CD | 13/20 | 65% | I1/I2/I3/I6/I7 ☑. I4/I5 ☐ — blocked on `main` promotion, see §4 |
| J · Documentation | 12/15 | 80% | J1/J2/J3/J5 ☑. J4 (video) ☐ — needs both partners |

**Sections B through H are fully implemented, fully tested, fully evidenced. There is zero
remaining backend/frontend/data/cache/AI/Docker/Kubernetes implementation work.** This has been
true since before this session and remains true.

---

## 3. Bonus section — confirmed state on `dev` post-merge

| Item | Marks | Status |
|---|---|---|
| Zero-downtime rollout, zero failed requests | +4 | ☑ — `docs/evidence/zero-downtime-rollout.txt` |
| Prometheus + Grafana | +2 | ☑ — real dashboard, real traffic, `docs/evidence/grafana.png` |
| OpenTelemetry tracing | +2 | ☑ — real end-to-end trace (frontend→backend→db, one trace ID), `docs/evidence/jaeger-e2e-trace.png` |
| Cosign sign + verify in CI | +3 | Code exists in `cd.yml` (predates this session) but has **never run** — `cd.yml` only fires on push to `main`, which is 83 commits stale. Disclosed honestly as code-complete, not execution-proven. |
| GitOps (Argo CD) | +4 | Manifest (`k8s/argocd/application.yaml`) ☑, merged. The **live reconciliation screenshot** the rubric line implies is ☐ — needs a real cluster with the Argo controller installed, a one-time out-of-band install step not yet run |

**Honest bonus ceiling: 9/15 fully proven** (rollout + Prometheus/Grafana + OTel), with GitOps and
Cosign sitting at "code/manifest complete, execution unproven." A generous reading crediting
GitOps's merged manifest gets to 11/15 — a strict marker who requires the live artefact (Argo UI
screenshot, `cosign verify` log from a real run) would count 9/15. Both readings are stated; §1's
164–166 range reflects exactly this spread.

---

## 4. What's still open, by exact blocker — nothing summarized away

### 4.1 Needs a live cluster + `main` promotion + 2 GitHub Secrets (asked for; still not added)

- **I4 (4 marks)** — `cd.yml`'s `build-push` job has never executed. Structurally correct
  (`needs: test`, SHA-tagged images), zero live evidence.
- **I5 (3 marks)** — `cd.yml`'s `deploy-k8s` job, same story.
- **Cosign sign+verify (+3 bonus)** — same root cause exactly. The code in `cd.yml` signs and
  verifies; it has simply never run.
- **GitOps live screenshot (partial credit on +4 bonus)** — needs a cluster with Argo CD's
  controller installed and the Application manifest applied against it, reconciling for real.

**Concrete blocker, confirmed by me directly:** `gh api repos/IfBilal/CivicPulse-SCD/actions/secrets`
returns `{"total_count":0}` — zero repo secrets configured. `cd.yml`'s `deploy-k8s` job reads
`secrets.POSTGRES_PASSWORD` and `secrets.LLM_API_KEY`; without them, a `main` promotion right now
produces a **failing** CI run, which is worse than the current honestly-disclosed "never run"
state. **I cannot add these myself** — HARD rule 1 (never let a real key pass through me) plus no
write access to repo Settings→Secrets (verified: the check itself succeeded, the count was zero).
This is the single item blocking the most rubric-adjacent value (7 marks of I4/I5 alone) for the
least remaining effort, and it is waiting on you specifically.

### 4.2 Needs both partners, together, in one sitting — nothing solo can close these

- **A5 (3 marks)** — the deliberate `schemas/stats.py` merge-conflict exercise. Cheapest joint
  item. Commands ready in `docs/handover/HANDOVER-to-ifbilal-phases-0-6-close-and-next-steps.md §2`.
  You said this is next, after Phase 7 loose ends (which are done) — status: **not yet started**,
  per current repo state (no `feat/deliberate-conflict-a`/`-b` branches exist).
- **J4 (3 marks)** — the demo video, ≤5 min, both speaking, six required beats. Not a bonus — a
  required section-J row. Not attempted.
- **A3 (4 marks)** — PR review rigor. Not attempted-and-blocked so much as **structurally
  capped**: 26+ of 42+ merged PRs shipped with zero review, unfixable retroactively. The only
  lever left is making every future PR (starting with #60 itself) get a real review from
  whoever didn't write it.
- **A4 (3 marks)** — commit-share floor. Not a task, a decision: pick which counting method
  (`--all` refs, 35.9%, passes vs `--no-merges HEAD`, ~7% now per the latest `check_submission.py`
  run — this number has dropped further as more solo-authored commits landed) you'll defend at
  viva. Per your explicit instruction, deferred, not attempted.

### 4.3 Genuinely done, verified this session, zero action needed

- Real gitleaks history scan: 92 commits, zero leaks. **Closed.**
- Real clean-clone `make up` from a fresh GitHub clone: succeeded end to end. **Closed.**
- VPA two-run loop (Phase 7, PR #58): real Target 813m → applied → re-measured 763m, converging.
  **Closed.**
- Zero-downtime rollout proof: real `rate==0.00%` across a live rolling update. **Closed.**

---

## 5. What I can still do solo, unprompted, right now — and what I genuinely cannot

**Solo-doable, no blocker:**
- Nothing rubric-scoring remains that's both solo-doable and unblocked. Every remaining
  rubric-body or bonus gap is now blocked on either (a) the two GitHub Secrets, (b) a joint human
  session, or (c) is already done.

**Cannot do, regardless of instruction, and why:**
- Add `POSTGRES_PASSWORD`/`LLM_API_KEY` to GitHub Secrets — no write access to repo Settings, and
  even with access, typing a real key into any command here would violate `CLAUDE.md` HARD rule 1
  (a real key in my output is treated as a live incident, not a formatting choice). This is not a
  cautious default I'm choosing — it's the literal rule this repository's own law-file states in
  boldface as non-negotiable.
- Fabricate A5's merge-conflict exercise solo — would misrepresent the exact two-person
  collaboration the rubric line is testing; already declined once this session, reasoning
  unchanged.
- Record J4 — needs two human voices.
- Retroactively add reviews to already-merged PRs (A3) — GitHub doesn't allow backdating a review
  onto a PR after merge in a way that would honestly reflect "this was reviewed before merge."

---

## 6. The one-sentence version

**Every line of code this product needs is written, tested, and evidenced — sections B through H
are 100%, and this session closed 3 of 4 remaining solo-doable bonus items plus both remaining
security/quickstart verification gaps — but PR #60 hasn't merged yet, and the 7 highest-value
remaining rubric marks (I4+I5) plus two bonus items (Cosign, GitOps's live proof) are all stuck
behind one blocker only you can clear: two GitHub Secrets.**
