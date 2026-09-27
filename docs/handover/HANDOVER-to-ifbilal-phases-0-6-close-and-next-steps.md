# HANDOVER — to IfBilal — Phases 0-6 closed, what's on you, and how Phase 7 starts

<!-- Written 2026-09-26, end of a long Claude Code session (T361's side) that closed out
     live-infra rubric evidence for Phases 0-6. This is the "here's exactly where things
     stand, here's what's on you specifically, here's how to start the next phase" note. -->

## 0. tl;dr

- **Phases 0-6 are done.** Every rubric row in sections B-G (frontend, backend, data layer,
  cache, Docker, Kubernetes) is proven with real, live evidence — not code-inspection guesses.
  See §1.
- **Three rows can't be closed by anyone working alone — they need both of us, together.**
  A3 (PR review rigor), A4 (commit-share number), A5 (the deliberate merge-conflict exercise).
  See §2. This is the most important section for you to read.
- **A real, previously-undetected bug in `cd.yml` was just found** — it's never going to run
  successfully until this is fixed. See §3. This blocks Phase 8 (CD/rollback), not Phase 0-6.
- **`main` and `dev` have identical content but different commit counts** ("78 ahead / 3
  behind") — this is cosmetic, not a bug, and I could not fix it myself (needs your admin
  rights on the ruleset). See §4 if you want it gone.
- **How to start Phase 7** is in §5.

---

## 1. Phases 0-6: what's actually proven, and how

`docs/20-RUBRIC-TRACEABILITY.md` is the source of truth — read it, not this summary, before
making any claim at viva. As of this handover: **58 rows are ☑ (proven with real evidence),
14 rows are ☐ (open)**. Of those 14 open rows, only 3 are inside phases 0-6 (A3/A4/A5, see §2);
the rest (H6, I4, I5, J4, and the bonus rows) are Phase 7/8 scope, correctly left untouched.

The evidence behind the ☑ rows was captured **live**, this session, against a real running
system — not inferred from reading source code:

- **The fallback test, for real**: spun up a disposable backend container on the actual
  compose network with `SIMULATED_FAILURE_MODE=raise` (forces the provider to always throw).
  A real `POST /api/complaints` still returned `201` with `triaged_by:"rules:fallback"`. This
  is the single most safety-critical test in the whole system, and it's now proven against a
  running instance, not just a unit test. Same live treatment for the malformed-JSON failure
  mode (zero retries, one WARNING log line) and the rate-limit failure mode (exactly one
  retry, then fallback). Evidence: `docs/evidence/fallback-test-live.txt`,
  `malformed-provider-test-live.txt`, `ratelimit-provider-test-live.txt`.
- **A real Playwright session against the actual running frontend**: Submit form validation
  errors, a filed complaint's real category/priority/summary/provider appearing on the
  Dashboard, a genuine invalid state transition (`open→resolved`) clicked in the UI producing
  the server's exact 409 message verbatim, and the Stats page's real `X-Cache: MISS`→`HIT`
  badge transition across a reload. 9 new screenshots in `docs/evidence/screenshots/`, also
  now embedded in the README's Screenshots section.
- **Live Postgres introspection**: full `\d+ complaints` schema dump, real `alembic history`,
  a real before/after `EXPLAIN (ANALYZE, BUFFERS)` for the `Q-DASH-FILTER` index — with an
  honest disclosure that the docs' own "Seq Scan → Bitmap Index Scan" viva talking point
  doesn't show up at ~50 seeded rows (correct Postgres planner behaviour at that scale, not a
  broken index — re-run against a bigger table if you want to see the transition for real).
- **A real k3d cluster**: deployed the app, confirmed `StatefulSet`+PVC for Postgres, all
  Services `ClusterIP`-only, all three probes correctly wired, and — the best piece of
  evidence in the whole session — a **full real HPA cycle**: replicas rose 2→4→6→8 under real
  load and fell back to 2 after, with real CPU percentages (`hpa-watch.txt`). Also ran a
  two-sided NetworkPolicy proof (frontend blocked, backend allowed, by raw pod IP to rule out
  DNS as a confound).
- **README rewritten** to match current reality — it had gone stale, claiming "most rubric
  rows still PENDING" and "frontend views not yet built" when neither was true any more.

`python3 scripts/check_submission.py` is `0 FAIL` on current `dev`/`main`.

**PRs merged this session**: #48 through #55 (dev→main promotion twice, rubric evidence,
README rebuild, RUNBOOK.md + the 8 viva questions, live-infra evidence, and the phase-0-6
lock-in pass). All 8 CI checks green on each.

---

## 2. What only you (and I, together) can close — read this section carefully

### A3 — PR review rigor (4 marks). This is the one that actually worries me.

I audited every merged PR's real GitHub review data (`gh pr list --json reviews`), re-run
fresh at the end of this session:

**26 of 42 merged PRs have zero reviews. A further 10 have only empty-body rubber-stamp
approvals. Only 6 of 42 have anything resembling a real review comment.** This includes PRs
from this very session (#49 through #55) — the number got *worse*, not better, as more work
landed without review.

`01-WORKFLOW.md §2.3` and `CLAUDE.md §6` rule 5 are both explicit that a rubber-stamp doesn't
count, and that I (running as one contributor's tool) can't review my own diff and have it
count as satisfying this requirement either.

**This cannot be fixed retroactively.** You can't add a real review to a PR that's already
merged. What actually helps: **every PR from here forward needs a real review comment from
whichever of us didn't write it** — not "LGTM," something that references an actual line or
decision in the diff. If we do that consistently for the remaining PRs (Phase 7/8 will
generate several more), the ratio improves. It will never erase the 36 PRs that already
shipped without real review, and a marker who checks this (trivial: `gh pr list --json
reviews`) will find exactly what I found. Best move is to be ready to explain it honestly at
viva rather than be surprised by it — the README's Known Limitations section already
discloses this plainly.

### A4 — commit-share floor (3 marks)

The rubric wants neither partner under 35% of commits. The real number depends on how you
count:
- **35.9%** if you count `--all` refs (includes every branch, not just what's reachable from
  `main`) — this passes.
- **22.6%** if you count `--no-merges HEAD` only (just `main`'s own linear history, excluding
  merge commits) — this fails.

I didn't pick whichever number is flattering — `docs/evidence/shortlog.txt` has both, and the
honest answer is this is genuinely contested. **Decide together which counting method you'll
defend at viva** before someone asks and you have to improvise. My instinct: the `--all` refs
number is probably closer to what a marker running `git shortlog -sn` against the whole repo
would see, but that's a guess, not a fact — verify it yourself.

### A5 — the deliberate merge-conflict exercise (3 marks)

`01-WORKFLOW.md §2.4` describes a **specific, scheduled, two-person exercise**: both of us
branch independently from the same `dev` SHA, each add a real field to
`backend/app/schemas/stats.py`'s `StatsResponse` model (`by_status` and `cache_age_seconds`),
and then merge, producing a genuine textual conflict with a required evidence bundle
(`merge-conflict-markers.txt`, `-raw.py`, `-graph.txt`, and a `merge-conflict.md` with 2-4
sentences on why the resolution was correct).

**Both fields already exist in the shipped schema** — so the feature work this exercise was
meant to produce is done. What's missing is the ceremony itself and its evidence bundle. I
explicitly declined to fake this alone, because doing so would misrepresent what the rubric is
actually testing (that two people can resolve a real conflict, not that I can write a
plausible-looking one).

**To close this, we need to actually do it — for real, together, one sitting:**
```bash
# both of us, at the same time, both branching from the same dev SHA:
git fetch origin && git switch dev && git pull --ff-only
git switch -c feat/deliberate-conflict-a
# (edit schemas/stats.py: add a field, e.g. avg_resolution_hours: float | None)
git commit -am "feat: add avg_resolution_hours to StatsResponse"
git push -u origin feat/deliberate-conflict-a

# meanwhile, the other partner, from the SAME starting SHA:
git switch -c feat/deliberate-conflict-b
# (edit the SAME region of schemas/stats.py: add a different field)
git commit -am "feat: add median_response_time_ms to StatsResponse"
git push -u origin feat/deliberate-conflict-b

# then merge branch A into branch B (or vice versa) locally, hit the real conflict,
# resolve it keeping both fields, and capture:
git diff > docs/evidence/merge-conflict-markers.txt   # while conflict markers are still present
git log --graph --oneline --all > docs/evidence/merge-conflict-graph.txt
# write docs/evidence/merge-conflict.md: 2-4 sentences on why keeping both fields was correct
```
Budget 30-45 minutes together. This is the cheapest remaining rubric row per hour of effort
in the entire project — do it before Phase 7 eats the calendar.

---

## 3. A real bug, found this session: `cd.yml` cannot succeed as written

`cd.yml` has now run twice against `main` (once after PR #48, once after PR #55) — **both
runs failed in 0 seconds**, meaning GitHub rejected the workflow file itself before starting
any job.

**Root cause, confirmed**: `cd.yml`'s `test` job does `uses: ./.github/workflows/ci.yml` (a
reusable-workflow reference), but `ci.yml` has no `workflow_call:` trigger declared in its
`on:` block — only `pull_request` and `push`. A workflow can only be called by another
workflow if it explicitly opts in with `workflow_call:`. This has been broken since `cd.yml`
was written; it just never surfaced because `cd.yml` never ran until `main` caught up to `dev`
this session.

**The fix** (not applied this session — deliberately out of scope, since it's Phase 8/CD work
and I was told to touch nothing beyond Phase 6):
```yaml
# in .github/workflows/ci.yml, add workflow_call to the existing triggers:
on:
  pull_request:
    branches: [main, dev]
  push:
    branches: [dev]
  workflow_call:   # <-- add this so cd.yml's `uses: ./.github/workflows/ci.yml` works
```
This is a one-line fix, but changing `ci.yml` is exactly the kind of "chore/contract-*"-style
change `CLAUDE.md` wants both of you aware of even for something this small, since it touches
the file every required status check depends on. Do it deliberately when you start Phase 8,
not as a rushed fix.

---

## 4. `main`/`dev` show "78 ahead, 3 behind" — cosmetic, confirmed twice

This is **not missing content**. `git diff origin/main origin/dev` is empty — every file is
byte-identical between the two branches right now. The mismatch is purely in commit history
shape: `main` has 3 "promote dev to main" merge commits that were never replayed onto `dev`
commit-by-commit, and `dev` has 78 individual feature-branch commits that were squashed into
those 3 merges rather than reproduced one-for-one. GitHub's ahead/behind counter counts
commits, not file state.

**This will not go away via a normal PR** — there's no content difference for a PR to bring
over. The only way to actually collapse it to `0/0` is a force-push of `main` to `dev`'s exact
SHA, which:
- Requires **admin** rights on the repo (I only have `push`, not `admin` — confirmed via
  `gh api repos/:owner/:repo --jq '.permissions'`, which is why I couldn't do this myself)
- Requires temporarily disabling `main`'s `non_fast_forward` ruleset rule (Settings → Rules →
  Rulesets → `main-protection` → set enforcement to Disabled), running the force-push, then
  re-enabling it
- Makes `main`'s 3 unique merge commits unreachable (not deleted from GitHub's storage
  immediately, but no longer part of `main`'s history) — **a backup tag already exists**:
  `backup-main-before-ff-reset` points at `main`'s current tip (`37cd8d1`), pushed to origin,
  so this is recoverable if anything looks wrong afterward

If you want to do this:
```bash
git fetch origin
git push origin origin/dev:main --force
```
Run it after temporarily disabling the ruleset. I'd only do this once, right before a final
submission freeze — no reason to do it now if Phase 7/8 will add more commits to `dev` anyway
(you'd just have to redo it later). My actual recommendation: **skip it** — no rubric row, no
CI check, no marker-visible artifact depends on this number, confirmed by reading
`scripts/check_submission.py`'s `VCS-DIRECT-MAIN` check (only cares that `main` was updated
via PRs, never checks ahead/behind count).

---

## 5. How to start Phase 7 (Load + Autoscaling)

Per `02-CRITICAL-PATH.md` PHASE 7 (§4) — this is explicitly **both devs, wall-clock bound**,
meaning it cannot be rushed by working harder; budget real calendar time, not just effort.

### 5.0 Before writing any code — run `caveman` first

`CLAUDE.md §6` requires this: before Phase 7 work starts, run the `caveman` skill against
`02-CRITICAL-PATH.md`'s PHASE 7 section + `14-LOAD-AUTOSCALING.md`, producing a stripped task
list (nouns/verbs only, every item ≤90 min). Log it in `docs/AI-USAGE.md` the moment it
happens — this is non-negotiable per the project's own rules, not optional.

### 5.1 What Phase 7 actually needs (from `02-CRITICAL-PATH.md` PHASE 7 + Gate 7 checklist)

**Build:**
- `metrics-server` installed on a real cluster with `--kubelet-insecure-tls` (k3d/kind quirk)
- `load/k6-script.js` (already exists — written in a prior session, never executed) — a
  ramping-arrival-rate load test
- HPA v2 with tuned `behavior` (already exists as `k8s/base/hpa.yaml` — verified structurally
  correct this session, and I already ran a *real* HPA cycle against it with a Python
  thread-pool load generator since `k6` wasn't available in that sandbox — see
  `docs/evidence/hpa-watch.txt` for a real 2→4→6→8→2 replica cycle. Re-running this with real
  `k6` for the "official" capture would strengthen it, but the mechanism is already proven live)
- Install VPA in `updateMode: "Off"` (manifest already exists: `k8s/base/vpa.yaml`, never
  actually deployed — needs the VPA controller/CRDs installed, which needs either sudo or
  running `kubernetes/autoscaler`'s install script; I declined to run that unreviewed script
  this session per this project's own security posture — you'll need to either review that
  script yourself first or find/write a safer install path)
- Run the VPA two-run loop: `describe` run 1, update `k8s/base/backend.yaml`'s `requests` to
  match VPA's `Target` recommendation **in its own commit citing the number**, `describe` run 2

**Gate 7 checklist** (all must pass before calling Phase 7 done):
- [ ] `kubectl top pods -n civicpulse` returns real numbers (already proven this session on a
      throwaway cluster — re-confirm on whatever cluster you stand up for the "official" run)
- [ ] `kubectl get hpa` shows `<n>%/60%`, never `<unknown>/60%`
- [ ] `docs/evidence/hpa-watch.txt` shows replicas rising 2→≥4 under load and falling after
      (this file already exists with real data from this session — decide if you want to
      re-capture it with real k6 traffic instead of the Python load generator, or keep it)
- [ ] `docs/evidence/hpa-replicas-vs-load.png` — offered RPS and replicas on one time axis
      (needs `load/plot_hpa.py`, which exists but was never run against real k6 output)
- [ ] `docs/evidence/vpa-describe-run1.txt` and `run2.txt` with Target/Lower/Upper Bound
- [ ] `k8s/base/backend.yaml` requests updated to the VPA Target, its own commit, citing the
      real recommendation number
- [ ] `docs/ENGINEERING-NOTES.md` Q5 (HPA lag, decomposed in real seconds) and Q6 (VPA Off-mode
      rationale + what happens if you accidentally run Auto) — **the 8-question structure
      already exists** (`## The eight viva questions`, written in PR #52), but Q5 is honestly
      marked "not yet measured" and needs real numbers once you run the official capture

### 5.2 Practical sequencing suggestion

1. Both of you, together or in parallel: stand up a real k3d cluster on whichever machine will
   do the "official" capture (this doesn't have to be a sandbox — a real laptop with Docker is
   fine and probably easier than fighting a cloud sandbox for Docker permissions, which cost
   most of a session this time around).
2. Install `metrics-server`, patch for k3d's kubelet TLS quirk (the exact patch command is in
   `docs/handover/HANDOVER-live-infra-evidence.md` §2.1 from an earlier session).
3. Deploy the app (`kubectl apply -k k8s/overlays/dev`).
4. Run `load/k6-script.js` for real (install `k6` first — wasn't available in the sandbox that
   produced this session's HPA evidence) while capturing `kubectl get hpa -w`.
5. Decide on the VPA controller install path (review `kubernetes/autoscaler`'s install script
   yourselves, or find an alternative — Helm chart, official YAML manifests, etc.) before
   running it.
6. Do the two-run VPA loop, update `k8s/base/backend.yaml`, write up Q5/Q6 with real numbers.
7. Fix the `cd.yml` bug from §3 as part of this phase's own PR (or a quick preceding one) —
   Phase 8 (CD) can't start cleanly with a broken reusable-workflow reference sitting there.

### 5.3 Don't forget, before or during Phase 7

- The A5 merge-conflict exercise (§2) — cheapest remaining rubric row, do it before Phase 7
  eats your calendar.
- Real PR reviews on every Phase 7 PR (§2, A3) — don't let this phase add to the 26-of-42
  zero-review count.
