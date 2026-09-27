# HANDOVER — everything left, to the minutest detail — 2026-09-27

**From:** Taimoor's side (Claude Code session) · **To:** IfBilal · **As of:** `dev` @ `2d028cb`
(PR #60 merged), `main` @ `37cd8d1` (84 commits behind `dev`)

<!-- Written at Taimoor's explicit request: "make an extensive handover.md about what's left,
     to the minutest detail, no stone unturned." Every number in this document was verified
     directly against the live repo/GitHub state at write time (git log, gh api, gh pr list,
     scripts/check_submission.py, file reads) — not reconstructed from memory or an earlier
     summary. Re-verify before relying on it if much time has passed; state changes fast. -->

---

## 0. tl;dr — read this paragraph if you read nothing else

**Every line of implementation code this product needs is written, tested, and evidenced.**
Sections B through H of the rubric (Frontend, Backend, Data layer, Cache layer, AI layer,
Docker/Compose, Kubernetes) are **100% complete** — zero remaining code work in any of those
areas. This session also closed 3 of 5 Bonus items for real (Prometheus/Grafana, OpenTelemetry
tracing, plus the zero-downtime rollout closed earlier) and both previously-unverified
deduction-armour risks (a real gitleaks history scan, a real clean-clone quickstart test).

**What's left is exactly six things, and every one of them is blocked on something a Claude Code
session cannot do alone:**
1. Two GitHub repo secrets you need to add (5 minutes, unlocks 7+ rubric marks) — §2
2. A `dev`→`main` promotion PR, which then makes `cd.yml` actually run for the first time — §3
3. The A5 deliberate merge-conflict exercise — needs both of you, one sitting, ~30-45 min — §4
4. A3/A4 — not tasks, decisions you two need to make together about how to present two ugly
   numbers at viva — §5
5. The demo video (J4) — needs both of you speaking, not a bonus, a required 3-mark row — §6
6. A live Argo CD screenshot for full GitOps credit — needs a cluster with Argo installed — §7

Current honest score if frozen today: **164–166 / 190 (86–87%)**. Full breakdown below.

---

## 1. Current state, verified fact by fact

- `dev` tip: `2d028cb` ("Bonus items complete: GitOps, Prometheus/Grafana, OpenTelemetry,
  release.yml + security verification", PR #60, merged 2026-09-27T16:28:05Z)
- `main` tip: `37cd8d1` — **84 commits behind `dev`** (confirmed via
  `git rev-list --count origin/main..origin/dev`). This number keeps growing every time work
  lands on `dev` without a corresponding promotion PR. It is not fixed by anything in this
  handover except §3.
- `scripts/check_submission.py` run against `dev` @ `2d028cb`: **0 FAIL, 4 WARN, 1 SKIP**. The 4
  WARNs are: `CI-NEEDS` (the parser can't verify `needs:` automatically, but manual read confirms
  both gates are present — not a real violation), `ENV-PARITY` (pre-existing, minor drift
  unrelated to this session's work), `RUBRIC-COMMITS` (see §5 — real and not cosmetic),
  `RUBRIC-EVIDENCE` (9/30 evidence files the script expects don't exist yet — expected at this
  stage of the project, not a defect).
- 49 merged PRs total (`gh pr list --state merged`, re-counted just now).
- Rubric traceability doc (`docs/20-RUBRIC-TRACEABILITY.md`) is up to date as of PR #60/#61.

---

## 2. The single highest-leverage action — two GitHub secrets (5 minutes, +7 marks minimum)

**Confirmed right now:** `gh api repos/IfBilal/CivicPulse-SCD/actions/secrets` returns
`{"total_count":0}`. **Zero secrets are configured on this repo.**

`cd.yml`'s `deploy-k8s` job reads `secrets.POSTGRES_PASSWORD` and `secrets.LLM_API_KEY`. Without
them, `cd.yml` cannot succeed — and since it only triggers on `push: { branches: [main] }`, it has
**never run once**, on any commit, ever. This blocks:

- **I4 (4 marks)** — `cd.yml`'s `build-push` job has never executed
- **I5 (3 marks)** — `cd.yml`'s `deploy-k8s` job has never executed
- **Cosign sign+verify bonus (+3)** — the code is already in `cd.yml` (predates this session,
  keyless `cosign sign` in `build-push`, `cosign verify` before deploy in `deploy-k8s`) but has
  never run
- Partial credit on the **GitOps bonus (+4)** — the Argo CD Application manifest
  (`k8s/argocd/application.yaml`) is merged and correct, but nothing has applied it against a
  live cluster yet (see §7 for why that's separate from the secrets issue)

**Why a Claude Code session cannot do this itself:** no write access to the repo's
Settings → Secrets → Actions page (verified: the API call above succeeded — meaning read access
exists — but creating a secret requires `admin` on the repo, which the token in use here does not
have). Separately and more fundamentally: `CLAUDE.md`'s HARD rule 1 states that if a real API key
or credential ever appears in a Claude Code session's output, it is treated as **a live security
incident, not a formatting mistake** — so even with write access, typing a real
`LLM_API_KEY` value into a `gh secret set` command would itself be the violation the rule exists
to prevent.

**What you need to do:**

1. Go to `https://github.com/IfBilal/CivicPulse-SCD/settings/secrets/actions`
2. Click "New repository secret" twice:
   - Name: `POSTGRES_PASSWORD` — Value: any strong password you choose (this seeds the prod
     Postgres instance the ephemeral `deploy-k8s` kind cluster spins up; it does not need to
     match anything else, since that cluster is destroyed at the end of the CI run)
   - Name: `LLM_API_KEY` — Value: a real Groq (or whichever provider) API key, **or** a dummy
     placeholder string if you don't want a live LLM call happening from CI. Check
     `k8s/overlays/prod`'s `configmap.yaml`/`TRIAGE_PROVIDER` setting before deciding — if prod
     is configured for `TRIAGE_PROVIDER=simulated` or `rules`, this key is created but never
     actually used by a real HTTP call, and a dummy value is completely safe.
3. Tell whoever's driving (me, next session, or yourself) once both are set.

---

## 3. What happens next, once secrets exist — the `dev`→`main` promotion

This is **separate** from adding the secrets. Adding secrets alone changes nothing until a commit
actually lands on `main`, because `cd.yml`'s trigger is `push: { branches: [main] }`.

**Sequence, once secrets are added:**

```bash
git fetch origin
git switch dev && git pull --ff-only
git switch -c chore/promote-dev-to-main-3
git push -u origin chore/promote-dev-to-main-3
gh pr create --base main --head chore/promote-dev-to-main-3 \
  --title "chore: promote dev to main (post Phase 7/8 bonus work)" \
  --body "Promotes 84 commits from dev, including Phase 7 (HPA/VPA), Phase 8 bonus items (GitOps/Prometheus/OpenTelemetry/release.yml), and this handover."
# get it reviewed (real review, not a rubber stamp — see §5) and merged
```

**Once that PR merges to `main`, watch `cd.yml` run for the first time ever:**

```bash
gh run watch  # or check the Actions tab directly
```

Expected: `test` job reuses `ci.yml` (should be green, since `dev`'s own CI is green), then
`build-push` builds+pushes both images to GHCR under SHA tags, signs them with Cosign, uploads an
SBOM — then `deploy-k8s` spins up an ephemeral `kind` cluster, applies ingress-nginx, creates the
`app-secrets` Secret from the two GitHub Secrets you just added, pins the overlay to the digest
Cosign just signed, verifies the signature, applies the manifests, waits for rollout, smoke-tests
through the Ingress, and prints `kubectl get hpa`.

**If it fails on the first real attempt, that is normal and expected — this exact workflow has
never executed even once, so there will likely be at least one real bug to fix** (a missing
permission, a version mismatch, a manifest reference that doesn't quite match). Do not be
surprised by this; budget time for at least one fix-and-rerun cycle. Once it goes green:

- **I4 and I5 close** — capture the run URL, save it as `docs/evidence/cd-run-green.txt` or
  similar, update `20-RUBRIC-TRACEABILITY.md`'s I4/I5 rows from ☐ to ☑ citing that URL.
- **Cosign sign+verify bonus closes** — same run, the sign/verify steps' logs are the evidence.
- **GHCR should now show both images with real SHA tags** — screenshot the package page for
  §5.8 item 3 of the docs (referenced in the original I4 rubric line).

---

## 4. A5 — the deliberate merge-conflict exercise (3 marks, cheapest joint item, NOT YET STARTED)

**Confirmed right now:** `git branch -a | grep conflict` returns nothing. Neither
`feat/deliberate-conflict-a` nor `-b` exists. **This has not been started**, despite being
flagged as "next" after Phase 7 loose ends in an earlier conversation.

`01-WORKFLOW.md §2.4` requires this be done as **scheduled, two-person, same-sitting work** — a
single Claude Code session cannot honestly produce this alone without fabricating the exact
collaborative exercise the rubric line is testing (this was explicitly declined once already, by
design, not by oversight).

**Exact commands, ready to run, budget 30-45 minutes together:**

```bash
# Both of you, at the same time, both branching from the same dev SHA:
git fetch origin && git switch dev && git pull --ff-only
git switch -c feat/deliberate-conflict-a
# Edit backend/app/schemas/stats.py's StatsResponse — add ONE new field, e.g.:
#   avg_resolution_hours: float | None
git commit -am "feat: add avg_resolution_hours to StatsResponse"
git push -u origin feat/deliberate-conflict-a

# Meanwhile, the OTHER partner, from the SAME starting SHA:
git switch -c feat/deliberate-conflict-b
# Edit the SAME region of schemas/stats.py — add a DIFFERENT field, e.g.:
#   median_response_time_ms: float | None
git commit -am "feat: add median_response_time_ms to StatsResponse"
git push -u origin feat/deliberate-conflict-b

# Then, either of you, merge branch A into branch B locally (or vice versa) — this WILL
# conflict since both edits touch the same region of the same file:
git switch feat/deliberate-conflict-b
git merge feat/deliberate-conflict-a
# → real conflict markers appear in schemas/stats.py

# Resolve by keeping BOTH fields (the log/schema is additive, not exclusive — there's no reason
# to pick one over the other), then capture the required evidence bundle BEFORE finalizing the
# merge commit, while conflict markers are still visible in the diff:
git diff > docs/evidence/merge-conflict-markers.txt   # while markers are present, pre-resolve
# ... resolve the conflict for real, remove the markers, stage the resolved file ...
cp backend/app/schemas/stats.py docs/evidence/merge-conflict-raw.py
git log --graph --oneline --all > docs/evidence/merge-conflict-graph.txt
git commit  # completes the merge

# Write docs/evidence/merge-conflict.md — 2-4 sentences on WHY keeping both fields was the
# correct resolution (not just "no conflict left"), citing the additive-schema reasoning.
```

Note: `by_status` and `cache_age_seconds` — the two fields the original spec example named — are
**already both present** in the shipped `StatsResponse` (confirmed: `grep -n "by_status\|
cache_age_seconds" backend/app/schemas/stats.py` finds both). Use two genuinely new field names
instead (the `avg_resolution_hours`/`median_response_time_ms` example above, or your own choice)
so this is a real, novel conflict, not a re-enactment of work that's already shipped.

---

## 5. A3 and A4 — not tasks, decisions (7 marks combined, structurally hard to fully recover)

### A3 — PR review rigor (4 marks)

**Re-counted just now, fresh:** of 49 merged PRs, **30 have zero reviews, 12 have only
empty-body rubber-stamp approvals, and only 7 have anything resembling a real review comment.**
This is worse than an earlier count (42 PRs: 26/10/6) — the ratio has continued to degrade as
more PRs merged without review, including PRs from this very session (#58 through #61).

**This cannot be fixed retroactively.** GitHub does not support backdating a real review onto an
already-merged PR in any way a marker would find credible. The only lever left: **every PR from
this point forward needs a real review comment** (referencing an actual line or decision in the
diff, not "LGTM") **from whoever didn't write it** — including the `dev`→`main` promotion PR in
§3, and definitely including any future PR either of you opens for A5's exercise. If that
discipline holds from here, the ratio stops getting worse; it will never fully recover the ~35
PRs that already shipped without one.

**Recommendation:** at viva, be ready to say this plainly rather than be caught off guard —
`gh pr list --json reviews` is a trivial command a marker could run themselves. The honest
framing ("we caught this partway through, corrected going forward, here's the exact ratio") reads
far better than being surprised by the question.

### A4 — commit-share floor (3 marks)

**Re-counted just now, fresh, both ways:**

```
git shortlog -sn --all:
    75  T361
    37  Taimoor Shaukat
     8  8BitNinja
     8  IfBilal
     2  copilot-swe-agent[bot]

git shortlog -sn --no-merges HEAD:
    34  T361
    18  Taimoor Shaukat
     8  8BitNinja
     5  IfBilal
```

**This session does NOT assume which names belong to which of you** — that identity mapping is
something only you two can confirm. Two readings, both stated honestly rather than picking
whichever is flattering:

- **If `T361` + `Taimoor Shaukat` are the same person, and `8BitNinja` + `IfBilal` are the same
  person:** combined shares are 112/130 (86.2%) vs 16/130 (12.3%) counting `--all`, or 52/65
  (80.0%) vs 13/65 (20.0%) counting `--no-merges HEAD`. **Both readings put the minority
  contributor well under the 35% floor** — worse than an earlier report's "35.9% vs 22.6%"
  figures, which used a different identity-merge assumption or was measured before more
  Taimoor-authored commits landed.
- **If those identity mappings are wrong**, the real numbers could look completely different —
  this needs the two of you to actually confirm who each git identity belongs to before trusting
  any percentage here.

**This is not a task with a command that fixes it.** It's a decision: agree on (a) the correct
identity mapping, (b) which counting method you'll defend at viva, and (c) whether the honest
answer is simply "the AI-driven session did most of the mechanical commit work, here's how we
split actual decision-making and review instead" — which may be a more defensible framing than
trying to make the raw commit count look balanced after the fact.

---

## 6. J4 — the demo video (3 marks, NOT a bonus, required section-J row)

Per `18-DOCS-EVIDENCE-VIVA.md §7` and `docs/20-RUBRIC-TRACEABILITY.md`'s J4 row: video ≤5:00,
**both partners audibly speaking**, covering six required beats. Status: **not attempted**, needs
an actual recording session with both of you. Not something any Claude Code session can produce.

Suggested prep (can be done solo, before the joint recording session):
- Re-read `18-DOCS-EVIDENCE-VIVA.md §7` for the exact six beats required — write a shared script
  or bullet outline before recording, so the joint session is efficient rather than improvised.
- Have the app running (`make up`) and a k8s cluster with the HPA demo ready (`docs/RUNBOOK.md`
  has the exact commands) so the recording doesn't stall on setup.
- Budget two takes minimum, per the 14-day schedule's own Day 14 plan (`02-CRITICAL-PATH.md`).

---

## 7. GitOps live proof — the Argo CD controller install (partial credit on the +4 bonus)

`k8s/argocd/application.yaml` is merged and correct (points at `k8s/overlays/prod`,
`syncPolicy.automated` with `prune`+`selfHeal`). What's missing is a **live reconciliation
screenshot** — the manifest alone doesn't do anything until it's applied against a cluster that
already has the Argo CD controller installed.

This is a **separate blocker from §2's secrets** — it needs a real cluster (k3d/kind, same as
Phase 7's HPA work), not GitHub Secrets. It is solo-doable by whoever has a working Docker/k3d
environment (see `docs/handover/HANDOVER-phase7-hpa-capture-devb-to-deva.md` and the Phase 7
session's own experience for what a k3d cluster setup involves and what can go wrong with it —
notably, a long-running k3d cluster combined with heavy `docker exec` usage caused a real
Docker-daemon hang in that session that needed a host reboot to clear; budget for that
possibility and don't panic if it recurs).

**Install sequence** (official upstream manifests, not a random script):

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd wait --for=condition=available deploy/argocd-server --timeout=300s
kubectl apply -f k8s/argocd/application.yaml
kubectl -n argocd port-forward svc/argocd-server 8080:443 &
# open https://localhost:8080, default admin password:
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
```

Once the Application shows `Synced`/`Healthy` in the UI, screenshot it as
`docs/evidence/argocd-ui.png` and update the Bonus row in `20-RUBRIC-TRACEABILITY.md` from
"manifest ☑, live proof ☐" to fully ☑.

---

## 8. Everything else — confirmed complete, zero action needed

For completeness, so nothing is left ambiguous: the following are **fully done, tested, and
evidenced**, verified against real repo state at the top of this document, not assumed:

- **Sections B–H of the rubric (Frontend, Backend, Data, Cache, AI, Docker/Compose,
  Kubernetes) — 100%.** No remaining implementation work in any of these areas.
- **Phase 7 (HPA/VPA load testing)** — real k6 captures, real VPA two-run convergence loop, real
  zero-downtime rollout proof. All evidence files exist and are committed.
- **Real gitleaks full-history scan** — 92 commits, zero leaks, `check_submission.py::
  SEC-ENV-HISTORY` now PASSes.
- **Real clean-clone quickstart test** — a genuinely fresh `git clone` + `make up` succeeded end
  to end.
- **Prometheus + Grafana bonus** — real dashboard, real traffic, real screenshot.
- **OpenTelemetry tracing bonus** — real end-to-end distributed trace (frontend → backend →
  database, one trace ID, verified via Jaeger), plus the LLM-call leg proven separately.
- **`release.yml`** — written, matches spec, not yet triggered (needs a `v*` tag push, which
  itself is not currently blocking anything — no rubric row requires a release to have actually
  been cut, only that the workflow exists correctly).

---

## 9. Quick-reference checklist

Copy this into whatever tracker you use and check items off as they close:

- [ ] Add `POSTGRES_PASSWORD` GitHub secret (§2)
- [ ] Add `LLM_API_KEY` GitHub secret (§2)
- [ ] Open and merge a `dev`→`main` promotion PR, get it reviewed for real (§3, §5)
- [ ] Watch `cd.yml` run for the first time; fix whatever breaks on the first attempt (§3)
- [ ] Capture the green `cd.yml` run as evidence; update I4/I5 rows to ☑ (§3)
- [ ] Screenshot GHCR showing both images with real SHA tags (§3)
- [ ] Run the A5 merge-conflict exercise together, capture the full evidence bundle (§4)
- [ ] Agree on identity mapping + counting method for A4; decide your viva framing for A3 (§5)
- [ ] Record the demo video, both speaking, six beats, ≤5:00 (§6)
- [ ] Install Argo CD controller on a cluster, apply the Application manifest, screenshot a
      `Synced`/`Healthy` reconciliation (§7)
- [ ] Re-run `python3 scripts/check_submission.py` after all of the above — confirm 0 FAIL
- [ ] Final pass: every row in `docs/20-RUBRIC-TRACEABILITY.md` should be ☑ except A3/A4 (which
      get a documented, defensible viva answer instead of a checkmark)
