# HANDOVER — Phases 0-6 closed out end-to-end, two PRs waiting on merge

<!-- Written at session close, 2026-09-26. -->

## 0. Position

| | |
|---|---|
| Base | `dev` @ `a384b17` (PR #45 merged) |
| Phase / Gate | **P0-P6 — cold-audited and closed out end-to-end** |
| From / To | T361 (DEV-A) → whoever picks this up next (DEV-A, DEV-B, or a future session) |
| Open PRs | **#46** `fix/close-disclosed-gaps`, **#47** `fix/root-readme` — both fully green, neither merged yet |
| Also open | **#42** `dev → main` — Bilal-approved once, approval auto-dismissed when `dev` moved, needs re-approval |

This isn't a replacement for `docs/AI-USAGE.md`'s own entries (which have the full technical
narrative, falsification steps, and rejected alternatives for everything below) — it's the
"here's exactly where things stand, here's what's on you" note. Read the matching `AI-USAGE.md`
entries (all dated 2026-09-26, in order) before touching any of this if you need the reasoning,
not just the outcome.

---

## 1. What's already done

Two independent, cold, adversarial audits ran this session — one subagent covering Phases 3-6
(backend core, AI triage, cache/ratelimit, k8s), one covering Phase 0, Phase 2, and the whole
frontend. Neither had access to this session's own reasoning; both were instructed to find
discrepancies, not confirm things were fine. Every real finding from both was fixed, verified,
and disclosed — nothing was patched over or silently claimed complete.

**Real, fixed gaps (PR #46, `fix/close-disclosed-gaps`):**
- `k8s/base/hpa.yaml` and `vpa.yaml` didn't exist — `00-SPEC.md §3.3`/`13-KUBERNETES.md`
  require them (Rubric H, 7 marks + 4 bonus). Both written per `14-LOAD-AUTOSCALING.md §3`/`§7`
  exactly, wired into `kustomization.yaml`, verified with the real `kustomize`/`kubeconform`
  binaries CI uses — both overlays, 21/21 resources valid, VPA CRD schema resolved correctly.
- `load/k6-script.js`, `load/corpus.json` (20 real complaints from `seed_data.py`),
  `load/k6-rollout.js`, `load/plot_hpa.py` — the rest of `14-LOAD-AUTOSCALING.md`'s
  non-cluster-dependent deliverables. Syntax-verified, never executed (see §2 below).
- `Makefile::k8s-up`'s metrics-server patch was only setting 1 of 3 required args — fixed. Added
  `vpa-up`, `load-rollout`, `hpa-chart` targets that didn't exist.
- The real Ollama benchmark: a local Ollama daemon turned out to already be running natively on
  this machine (systemd service, independent of Docker). Pulled `llama3.2:1b`, ran a real
  10-item benchmark through the actual `OllamaTriage` code path. Result, honestly reported:
  10/10 valid JSON, but 10/10 came back `priority: low` including a burst-water-main case that
  should be `high` — a real accuracy finding, not a clean pass. `docs/TRIAGE.md` updated with
  real p50/p95/p99 numbers.
- `/api/meta/providers`'s `cache.hits`/`misses`/`hit_rate` were hardcoded to `0` — fixed with a
  real `prometheus_client.Counter`, per `08-AI-TRIAGE.md §6`'s own specified read path.
- Three smaller findings: a stale `ci.yml` comment claiming Phase 6 hadn't landed (it has); a
  stale comment claiming `ComplaintService.create()` never invalidates the stats cache (fixed
  earlier this session, comment never updated — now has a real HTTP-level CI assertion instead
  of just a claim); dead `RateLimited` exception code that was never reachable (real 429s come
  from the middleware layer, not an exception handler).

**Real, fixed gaps (PR #47, `fix/root-readme`):**
- **No root `README.md` existed at all.** `03-REPO-BOOTSTRAP.md` requires it;
  CLAUDE.md's deduction ledger is −5 for exactly this. Written, with a `## Quickstart` section
  verified against the actual `scripts/check_submission.py::doc_quickstart()` detector logic.
- That detector itself was under-reporting the missing README as `SKIP` instead of `FAIL` —
  fixed.
- Ran the full `scripts/check_submission.py` suite for the first time this session (it's a
  local-only `make submission-check` target, never wired into CI) and found **3 FAIL + 2 stale
  SKIP that were all detector bugs**, not real problems — traced every one to the actual
  regex/path before touching anything:
  - `SEC-K8S-SECRET` false-flagged real, safe placeholder values (quoted-string handling bug,
    plus `DATABASE_URL`'s composite-template shape).
  - `NET-LOCALHOST` false-flagged two container healthchecks and a dev-only ingress hostname
    that `Makefile::lint-localhost` already correctly excludes — this Python script had never
    been brought into parity with that Makefile fix.
  - `NET-SEGMENT` false-flagged a real, correct `internal: true` network marker (regex assumed
    two adjacent lines; the real file has `driver: bridge` between them).
  - `K8S-DB-DEPLOYMENT` and `ENV-PARITY` were permanently `SKIP` against stale filenames
    (`postgres.yaml` → real file is `postgres-statefulset.yaml`; `config.py` → real file is
    `settings.py`) — silently never going to fire.
  - `RUBRIC-TESTS` reported **0 backend tests collected** against a real 299-test suite — two
    independent bugs (wrong Python interpreter; wrong output-format assumption for this
    project's own `pytest -q --collect-only`).
  - Net: `3 FAIL, 6 WARN, 3 SKIP` → `0 FAIL, 5 WARN, 1 SKIP`, all remaining items genuinely
    expected at this stage (no gitleaks binary in the sandbox, a real contributor-share number,
    real missing live-cluster evidence files).
- **`.github/workflows/cd.yml` didn't exist at all** — found while researching ADR-0003. Only
  `ci.yml` (test/lint/build/scan) existed; the actual GHCR-push-and-deploy workflow was never
  built. `00-SPEC.md §638` ties 4 real rubric marks to it. Built per `15-CICD.md §4`'s complete
  spec: `test` (reuses `ci.yml`) → `build-push` (`needs: test`, GHCR push tagged by SHA and
  `:latest`, SBOM, cosign signing as the labelled bonus) → `deploy-k8s` (`needs: build-push`,
  signature verification, real `kind` cluster, secrets from GitHub Secrets never echoed,
  `kustomize edit set image` pinned to the build's own captured **digest** — never a tag).
  **Not verified against a real deploy** — see §2.
- Three missing ADRs written (`0001-provider-interface.md`, `0003-deploy-by-sha.md`,
  `0004-pii-and-data-governance.md`) — `00-SPEC.md` requires four, only `0002` existed. Each
  grounded in code/spec text actually read, not invented content for a checkbox.

**Everything both audits checked and found genuinely correct, no fix needed:** contract surface
(`04-CONTRACTS.md` enums/error envelope/headers vs. `schemas/`/`domain/enums.py`), layering
(routes/services/repositories/providers, no SQL outside `repositories/`), the state machine (a
real dict lookup, no if/else chain), migrations vs. `05-DATA-LAYER.md` (native enums, both
indexes, the trigger, all six CHECK constraints), seed data (36 rows, honest `triaged_by=rules`,
never fabricated), the entire frontend (no business-rule leakage — HARD rule 9 — substantive
tests, contract sync enforced in CI), k8s StatefulSet/ClusterIP/NetworkPolicy setup, image
pinning, CI `needs:` gating, no secrets found anywhere.

---

## 2. What genuinely cannot be closed from a sandbox, and needs to happen on real infrastructure

This is the one category of "not done" that's real and disclosed, not an oversight:

1. **Gate 7's live evidence files** — `docs/evidence/hpa-watch.txt`, `hpa-samples.txt`,
   `hpa-replicas-vs-load.png`, `k6-summary.json`, `vpa-describe-run{1,2}.txt`,
   `zero-downtime-rollout.txt`. All require an actual k6 load run against an actual live k3d
   cluster with metrics-server and the VPA controller installed. The commands are all real and
   ready:
   ```bash
   make k8s-up          # cluster + ingress-nginx + metrics-server + dev overlay
   make vpa-up           # installs the VPA controller (recommender/updater/admission)
   # then the five-step VPA loop, 14-LOAD-AUTOSCALING.md §7.2:
   #   record the guess -> make load -> kubectl describe vpa -> update requests -> re-run
   make load             # k6 run load/k6-script.js
   make hpa-chart         # renders docs/evidence/hpa-replicas-vs-load.png
   make load-rollout      # the zero-downtime bonus proof
   ```
   Do this on a machine with real Docker access — this sandbox never had it all session
   (confirmed repeatedly: no `docker` group membership, no passwordless `sudo`).

2. **`cd.yml` has never actually run.** No GHCR credentials, no live cluster, no registry access
   from this sandbox to test it end-to-end. It's syntax-validated (`yaml.safe_load()`) and
   structurally checked (`needs:` edges present, by eye) but the real confirmation is the first
   actual push to `main` that triggers it. Before that happens, confirm:
   - `POSTGRES_PASSWORD` and `LLM_API_KEY` are set as real **GitHub repository secrets** (not
     committed anywhere — `Settings → Secrets and variables → Actions`).
   - `GITHUB_TOKEN` has `packages: write` available (default for same-repo workflows, but worth
     checking `Settings → Actions → General → Workflow permissions` if the push fails on the
     GHCR login step).

3. **`docs/ENGINEERING-NOTES.md`'s Q5 (HPA lag, per-term seconds) and Q6 (VPA/HPA oscillation)**
   need real numbers from the load test above, not the doc's own "typical" table copied in —
   `14-LOAD-AUTOSCALING.md §5`/`§7.4` are explicit that generic answers score zero.

---

## 3. The two open PRs, and what's blocking each

- **#46** (`fix/close-disclosed-gaps`) — all 7 CI checks pass. Not merged. Nothing blocking it
  except someone clicking merge.
- **#47** (`fix/root-readme`) — all 7 CI checks pass. Not merged. Same — nothing blocking it
  except the merge click. Depends on nothing in #46; either can merge first.
- **#42** (`dev → main`, "Phases 3-6 complete") — was Bilal-approved once. GitHub auto-dismisses
  an approval every time the base branch (`dev`) picks up new commits, which has happened
  several times this session as #44/#45 merged. **Needs Bilal to re-approve after #46 and #47
  also land in `dev`** (branch-update it first — `gh api -X PUT
  /repos/IfBilal/CivicPulse-SCD/pulls/42/update-branch`, or the "Update branch" button on
  GitHub) before it can merge. This repo's own branch protection requires that re-approval; it
  is not something either of you can skip or something I can do on Bilal's behalf.

**Merge order that keeps `dev` and #42 consistent:** #46 → #47 → update #42's branch → Bilal
re-approves #42 → merge #42 into `main`.

Per this session's standing instruction: **I have not merged, and will not merge, anything into
`main`.** Every merge from here is a click either of you makes on GitHub.

---

## 4. Things that will bite you if you don't know them going in

- **`gh auth` silently drifts to a second, no-write-access account (`taimoor-boop`) in this
  sandbox, periodically, for no traceable reason.** Every push/merge/PR-edit in this session
  needed `gh auth switch --hostname github.com --user T361` run immediately before it, checked
  every single time rather than assumed still correct from the last check. If a push 403s with
  "Permission ... denied to taimoor-boop," that's why — switch back and retry, don't assume
  something else broke.
- **`gh pr edit --body` silently no-ops** on this repo/token combination — it returns a
  confusing "Projects (classic) is being deprecated" GraphQL error and the edit does not apply,
  with no clear failure message. Use `gh api -X PATCH /repos/.../pulls/<n>` with a JSON payload
  instead if you need to update a PR description programmatically.
- **This sandbox has no Docker access** (`docker info` fails with a raw permission error; no
  `docker` group membership; `sudo` needs a password that was never available). Every
  Docker/k3d-dependent piece of work this session (verifying the actual image builds, running
  the load test, testing `cd.yml`) was written and syntax-checked but never executed end to end.
  Don't assume "it's in the repo" means "it's been run" for anything under `k8s/`, `load/`, or
  `.github/workflows/cd.yml`.
- **Ollama runs natively on this specific machine** (systemd service, `qwen2.5-coder:14b`
  pre-pulled), independent of the Docker gap above — that's how the real Ollama benchmark in
  §1 got run at all. Don't assume the same is true on a different machine.
