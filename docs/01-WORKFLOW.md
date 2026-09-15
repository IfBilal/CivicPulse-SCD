# 01 — DEVELOPER WORKFLOW

> **Scope.** How two developers, each driving a Claude Code session, build CivicPulse without
> stepping on each other, without breaking `main`, and with enough paper trail to satisfy Rubric A
> (15 marks), §5.5 (AI attribution) and §5.4 (individual viva, which **multiplies** the team mark).
>
> **Read with:** `02-CRITICAL-PATH.md` (what to build when), `19-HANDOVER-TEMPLATE.md`
> (the session-boundary artefact), `20-RUBRIC-TRACEABILITY.md` (proof obligations).

---

## 1. Roles, and why they are not "frontend guy / backend guy"

The viva cross-examines you **on code your partner wrote** (§5.4). A clean split maximises
throughput and **minimises viva factor**. So: split by *primary ownership*, but enforce
**mandatory cross-review** and **two scheduled ownership swaps**.

| | **DEV-A — "Core"** | **DEV-B — "Edge"** |
|---|---|---|
| Primary | Backend core, Data, AI triage, Cache/rate-limit, Observability | Frontend, Docker/Compose, Kubernetes, CI/CD, Load/Autoscaling |
| Rubric ownership | C (25), D (12), E (10), F (25), part of J | B (18), G (15), H (20), I (20), part of J |
| Raw marks owned | 72 + | 73 + |
| Swap 1 (Phase 5) | DEV-A writes the k6 script + HPA capture | DEV-B writes the stats-cache invalidation + its tests |
| Swap 2 (Phase 7) | DEV-A writes the frontend Stats view + `X-Cache` badge | DEV-B writes the prompt-injection guardrail test |

The swaps are not decoration. They exist so that at viva **each of you has written code in the
other's territory**, which is the difference between viva factor `1.0` and `0.75` — a 25% multiplier
on the entire team mark.

**Shared, co-authored, never solo:** `04-CONTRACTS.md`, `README.md`, the four ADRs,
`docs/ENGINEERING-NOTES.md`, the demo video script.

---

## 2. Branch model

```
main ──────●───────────────●───────────────●──────────  protected, deployable, tagged
            ╲             ╱ ╲             ╱
dev ─────────●───●───●───●───●───●───●───●────────────  integration, CI on every push
              ╲ ╱     ╲ ╱     ╲ ╱     ╲ ╱
feat/*, fix/*, chore/*, docs/*  ...                      short-lived, ≤ 2 days, one concern
```

**Rules, enforced by settings not by goodwill:**

| Rule | Mechanism |
|---|---|
| No direct push to `main` | GitHub branch protection: *Require a pull request before merging* |
| No direct push to `dev` for feature work | Convention + PR template; CI runs on `push: dev` as a safety net |
| ≥ 1 approval on every PR to `main` | Branch protection: *Require approvals = 1* |
| CI must pass | Branch protection: *Require status checks to pass* → tick the exact job names from `ci.yml` |
| Branch must be current | Branch protection: *Require branches to be up to date before merging* |
| Linear history | *Require linear history* → forces squash or rebase merge |
| No force-push, no deletion | *Do not allow bypassing* + *Restrict force pushes* |
| Admins included | **Tick "Do not allow bypassing the above settings"** — otherwise you can push to main by accident and eat −5 |

> **Deduction watch (§5.3):** *Commits pushed directly to `main` → −5.* Turn protection on
> **before the first commit of real code**, and screenshot it to
> `docs/evidence/branch-protection.png` **on day 1** (Rubric A, 3 marks).

### 2.1 Branch naming

```
feat/<area>-<slug>      feat/ai-triage-provider-interface
fix/<area>-<slug>       fix/cache-stats-invalidation-race
chore/<area>-<slug>     chore/ci-pin-actions-to-sha
docs/<slug>             docs/adr-0004-pii-governance
spike/<slug>            spike/groq-json-mode          # throwaway, never merged
```

`<area>` ∈ `{be, fe, ai, db, cache, obs, docker, k8s, ci, docs}` — it becomes the commit scope too.

### 2.2 Commit convention (Rubric A: ≥ 35 commits, conventional prefixes, ≥ 35% each)

```
<type>(<scope>): <imperative summary ≤ 72 chars>

<body: why, not what. Wrap at 80.>

Refs: #<issue>
AI-Assisted: claude-code  (scope: scaffolding|tests|refactor|docs|none)
Co-authored-by: <partner> <email>   # only when genuinely pair-driven
```

`type` ∈ `feat | fix | docs | test | refactor | perf | build | ci | chore | revert`.

**Commit-count arithmetic.** The floor is **35 commits total** with **neither partner below 35%**.
35% of 35 = 12.25 ⇒ **13 commits minimum each**, and realistically you will land 60–90. Do not
farm commits; the review comment requirement (below) makes padding obvious. Check weekly:

```bash
git shortlog -sn --no-merges
# then compute share:
git shortlog -sn --no-merges | awk '{t+=$1; a[NR]=$1; n[NR]=$2" "$3} END {for(i=1;i<=NR;i++) printf "%-20s %4d  %5.1f%%\n", n[i], a[i], 100*a[i]/t}'
```

Commit `git shortlog -sn` output to `docs/evidence/shortlog.txt` at submission (§5.8 item 5).

### 2.3 Pull request protocol (Rubric A: ≥ 5 merged PRs, each Issue-linked, each with a substantive partner review)

Every PR to `main`:

1. **Opened from `dev`** (integration PRs) or from a feature branch into `dev` (work PRs).
   The **≥ 5 merged PRs** requirement is satisfied by `dev → main` integration PRs, one per phase
   gate in `02-CRITICAL-PATH.md`. There are 8 gates, so you clear 5 with slack.
2. **Body uses `.github/pull_request_template.md`** (see `03-REPO-BOOTSTRAP.md §6`).
3. **Linked to an Issue** via `Closes #N`. No orphan PRs.
4. **Reviewed by the partner with a substantive comment.** *"LGTM" scores zero.* A substantive
   comment names a file and a line and either (a) asks why a decision was made, (b) identifies a
   failure mode, or (c) proposes a concrete alternative. Two per PR minimum.
5. **Squash-merged** with the PR title as the squash commit subject, conventional-prefixed.

**Anti-pattern:** both devs approving each other's PRs in bulk on the last night. GitHub timestamps
reviews. The rubric says *substantive*, the viva says *explain your partner's code*. Review as you go.

### 2.4 The deliberate merge conflict (Rubric A, 3 marks)

This is **scheduled work**, not an accident. Do it in **Phase 4**, on real code, on a file both of you
legitimately touch.

**The designated collision site:** `backend/app/schemas/stats.py` — the `StatsResponse` model.
Both devs add a field to the same region of the same model at the same time:

- DEV-A adds `by_status: dict[Status, int]`
- DEV-B adds `cache_age_seconds: int | None`

**Procedure:**

```bash
# Both branch from the same dev SHA
git switch dev && git pull --ff-only
git switch -c feat/be-stats-by-status        # DEV-A
git switch -c feat/fe-stats-cache-age        # DEV-B

# Both edit the SAME lines of StatsResponse, commit, push.
# DEV-A merges first.
# DEV-B then:
git switch dev && git pull --ff-only
git switch feat/fe-stats-cache-age
git merge dev            # ← CONFLICT

# CAPTURE THE MARKERS BEFORE RESOLVING:
git diff --diff-filter=U > docs/evidence/merge-conflict-markers.txt
cp backend/app/schemas/stats.py docs/evidence/merge-conflict-raw.py

# Resolve (keep BOTH fields — that is the correct engineering answer)
git add backend/app/schemas/stats.py
git commit           # do NOT use --no-edit; write the why into the merge commit body
git log --graph --oneline -20 > docs/evidence/merge-conflict-graph.txt
```

**Evidence bundle required by the rubric:** markers, resolution, merge evidence,
**plus 2–4 sentences on why that version won** → `docs/evidence/merge-conflict.md`.

Model answer skeleton (write your own, but hit these beats): *both changes were additive and
non-exclusive; the conflict was textual, not semantic; the resolution keeps both fields because
`StatsResponse` is a DTO with no invariant coupling the two; the alternative — taking one side —
would have silently dropped a field already consumed by `frontend/src/pages/Stats.tsx:L42`, and the
frontend's generated types would have failed `tsc` in CI, which is the check that would have caught
a wrong resolution.*

---

## 3. The two-window model (Claude Code)

Each developer runs **one primary Claude Code window per active branch**, backed by a
**git worktree** so the two windows never share a working directory.

```bash
# one-time, from the repo root
git worktree add ../civicpulse-A dev
git worktree add ../civicpulse-B dev
# DEV-A works in ../civicpulse-A, DEV-B in ../civicpulse-B
# Branches are switched inside the worktree; the .git dir is shared, the checkout is not.
```

**Why worktrees and not two clones:** shared object store (no double fetch), shared refs (you see
each other's branches instantly), and `git worktree list` is a cheap answer to "what is the other
window doing".

### 3.1 Window discipline

| Rule | Reason |
|---|---|
| **One window = one branch = one Issue** | A window whose diff spans three concerns produces a PR nobody can review substantively. |
| **Window opens by reading the handover** | `docs/handover/HANDOVER-<branch>.md`. See `19-HANDOVER-TEMPLATE.md`. |
| **Window closes by writing the handover** | Even mid-task. Especially mid-task. |
| **Never let a window edit files outside its ownership boundary** | Ownership boundaries in §4 below. Crossing them is how you manufacture conflicts you did not schedule. |
| **Contracts are read-only in feature windows** | `04-CONTRACTS.md` and the generated OpenAPI schema change only via a dedicated `chore/contract-*` PR with both devs on the review. |
| **Run the gate command before every commit** | `make check` — see `03-REPO-BOOTSTRAP.md §7`. A red pre-commit is cheaper than a red CI. |

### 3.2 Parallel-safe file ownership map

The single biggest source of avoidable conflict is two windows editing the same file. This map is
the contract. It is enforced socially, and mechanically by `CODEOWNERS`.

| Path glob | Owner | Notes |
|---|---|---|
| `backend/app/{routes,services,repositories}/**` | DEV-A | |
| `backend/app/providers/**` | DEV-A | |
| `backend/alembic/**` | DEV-A | **Migration revision IDs collide. See §3.3.** |
| `backend/tests/**` | both | Split by test module; never the same file |
| `frontend/**` | DEV-B | except `frontend/src/pages/Stats.tsx` in Swap 2 |
| `frontend/src/api/schema.d.ts` | **generated — nobody edits** | `make gen-client` |
| `*/Dockerfile`, `*/.dockerignore` | DEV-B | |
| `compose*.yaml` | DEV-B | |
| `k8s/**` | DEV-B | |
| `.github/workflows/**` | DEV-B | |
| `load/**` | DEV-A after Swap 1 | |
| `docs/adr/**` | one ADR per author, named in `02-CRITICAL-PATH.md` | |
| `docs/ENGINEERING-NOTES.md` | **both, but one section each** | Sections are H2-delimited; edit only your own |
| `backend/app/schemas/**` | **shared — the scheduled conflict zone** | See §2.4 |

`.github/CODEOWNERS`:

```
/backend/app/providers/   @dev-a
/backend/alembic/         @dev-a
/frontend/                @dev-b
/k8s/                     @dev-b
/.github/workflows/       @dev-b
/backend/app/schemas/     @dev-a @dev-b
/docs/adr/                @dev-a @dev-b
```

### 3.3 Alembic revision collisions — the specific hazard

Two branches each generating a migration produces **two heads with the same `down_revision`**.
`alembic upgrade head` then fails with `Multiple head revisions are present`.

**Prevention (preferred):** only DEV-A generates migrations, and only on `dev` rebased to tip.

**Cure (when it happens anyway):**

```bash
alembic heads                       # shows 2+ heads
alembic merge -m "merge heads" <rev1> <rev2>
alembic upgrade head
alembic history --verbose | head -40 > docs/evidence/alembic-history.txt
```

Never renumber or delete a migration that has been applied on a branch the partner has run.
Never hand-edit `down_revision` on a pushed migration. This is exactly the class of failure §5.2
question 8 is fishing for — if it happens, **write it up**, it is worth 2 marks.

---

## 4. Claude Code skill invocation slots

You are running four named skills. Below is **where each one fires in this project**, what artefact it
must produce, and the acceptance test for that artefact. Confirm the exact invocation string for
each skill in your own Claude Code setup; the *slots* are what matter here.

| Skill | Fires at | Input | Required output artefact | Acceptance test |
|---|---|---|---|---|
| **caveman** | Start of every phase, before any code | The phase section of `02-CRITICAL-PATH.md` + the relevant `0X-*.md` | A stripped-to-bone task list: nouns and verbs only, no hedging, every item independently completable in ≤ 90 min | Every line starts with a verb; no line contains "consider", "maybe", "as needed"; item count ≥ 5 |
| **ponytail** | Mid-phase, when a design decision has ≥ 2 defensible answers | The decision + constraints from `00-SPEC.md` | A decision record stub → becomes an ADR or an `ENGINEERING-NOTES.md` paragraph | Names ≥ 2 rejected alternatives **and** the rejection reason for each |
| **grilled meat** | End of phase, before opening the PR | The full diff | A hardening pass: error paths, timeouts, resource cleanup, log lines, edge cases the happy path skipped | Produces ≥ 3 concrete findings with file:line; each becomes a commit or a documented `WONTFIX` |
| **PR review** | On every PR, run by the **partner**, never the author | PR diff + `04-CONTRACTS.md` | ≥ 2 substantive review comments with file:line (Rubric A requirement) | Comments reference a spec clause or a failure mode, not style |

**The rule that makes this legitimate under §5.5:** everything these skills produce goes into
`docs/AI-USAGE.md` **at the moment it is produced**, not reconstructed at the end. Format:

```markdown
## 2026-09-22 · feat/ai-triage-provider-interface
- **Tool:** Claude Code + `caveman`
- **Shaped:** decomposition of the provider-interface phase into 7 tasks
- **Wrote:** none (planning only)
- **I changed:** merged tasks 4 and 5 because the retry policy and the fallback path share
  the same `except` ladder and splitting them produced an artificial seam.

## 2026-09-22 · same branch
- **Tool:** Claude Code + `grilled meat`
- **Wrote:** `backend/app/providers/triage/llm.py:88-131` (the retry/jitter ladder)
- **I changed:** it proposed retrying on `ValidationError`. Rejected — §2.5 item 3 restricts
  retries to timeout/429/5xx, and a schema failure is deterministic under retry. See
  `docs/adr/0001-provider-interface.md §Retry policy`.
```

> That last bullet is worth more at viva than the code. It proves you read the spec and overruled
> the tool. **Specific disclosure carries no penalty whatsoever** (§5.5).

---

## 5. The session loop (what a window actually does)

```
┌─ OPEN ────────────────────────────────────────────────────────────────┐
│ 1. git switch <branch>; git pull --ff-only origin dev; git rebase dev │
│ 2. cat docs/handover/HANDOVER-<branch>.md        ← state reconstruction│
│ 3. make up && make check                          ← prove green start │
│ 4. caveman(phase doc)                             ← task list          │
└───────────────────────────────────────────────────────────────────────┘
┌─ LOOP (per task, ≤ 90 min) ───────────────────────────────────────────┐
│ 5. write the FAILING test first (see 16-TESTING.md §2 for the matrix)  │
│ 6. implement until green                                               │
│ 7. ponytail(...) if a fork in the road appeared → ADR stub             │
│ 8. make check                                                          │
│ 9. git commit -m "<type>(<scope>): ..."   (one task = one commit)     │
└───────────────────────────────────────────────────────────────────────┘
┌─ CLOSE ───────────────────────────────────────────────────────────────┐
│ 10. grilled-meat(full diff) → findings → commits or WONTFIX notes     │
│ 11. update docs/AI-USAGE.md                                            │
│ 12. write docs/handover/HANDOVER-<branch>.md   ← 19-HANDOVER-TEMPLATE  │
│ 13. git push -u origin <branch>; open PR with template; assign partner │
│ 14. post the phase-gate checklist result in the PR body               │
└───────────────────────────────────────────────────────────────────────┘
```

**Never close a window without step 12.** The handover is the only thing standing between
"resume in 4 minutes" and "re-derive 90 minutes of context".

---

## 6. Synchronisation points

Asynchronous work needs scheduled convergence or it diverges silently.

| Sync | Cadence | Duration | Output |
|---|---|---|---|
| **Standup** | Daily, start of session | 10 min | Each dev: done / doing / blocked. Blocked items get an owner and a deadline **in the same 10 min**. |
| **Contract review** | Only when `04-CONTRACTS.md` changes | 20 min | Both approve; `chore/contract-*` PR merged; `make gen-client` re-run; frontend `tsc` green |
| **Integration merge** | End of every phase (8 total) | 30 min | `dev → main` PR, both review, CI green, tag if it is a demo-able state |
| **Phase gate** | End of every phase | 15 min | Walk the gate checklist in `02-CRITICAL-PATH.md`. **A phase is not done until its gate passes.** No exceptions — the gates are what keep the critical path honest. |
| **Viva drill** | End of Phase 6 and Phase 8 | 20 min each | Each dev is questioned **on the partner's code**, repository open. Record which questions could not be answered; those are study items. This directly rehearses §5.4. |

---

## 7. Definition of Done (per task)

A task is done when **all** of these are true. This list is short on purpose — every item is
independently checkable, and every item maps to a rubric line or a §5.3 deduction.

- [ ] Code implements exactly the contract in `04-CONTRACTS.md` — no more, no less
- [ ] A test exists that **fails without the change** (verify by `git stash`-ing the change)
- [ ] `make check` green: `ruff`, `mypy --strict`, `pytest`, `eslint`, `tsc --noEmit`
- [ ] Layer boundary respected (`routes` has no SQL, `services` has no HTTP status codes)
- [ ] Every new outbound call has a **timeout**
- [ ] Every new failure path emits a **structured log line with `request_id`**
- [ ] No secret, key, URL-with-credentials, or `.env` in the diff (`make secret-scan`)
- [ ] No `localhost` in any non-test, non-docs file (`make lint-localhost`)
- [ ] Conventional commit message with `Refs: #N` and `AI-Assisted:` trailer
- [ ] `docs/AI-USAGE.md` updated if a skill or model shaped the change
- [ ] Handover file updated

## 8. Definition of Done (per phase gate)

- [ ] All phase tasks done per §7
- [ ] The phase's **evidence artefacts** exist in `docs/evidence/` with the exact filenames from
      `18-DOCS-EVIDENCE-VIVA.md §3`
- [ ] The phase's rubric lines in `20-RUBRIC-TRACEABILITY.md` are marked `PROVEN` with a
      file:line or artefact reference
- [ ] `dev → main` PR merged, CI green, **both devs reviewed**
- [ ] `python scripts/check_submission.py` exits 0
- [ ] Both devs can explain every file changed in the phase (viva drill spot-check: 3 random files)

---

## 9. Emergency procedures

| Situation | Procedure |
|---|---|
| **Secret committed** | **Stop.** Do not just `git rm`. (1) Rotate the credential immediately at the provider. (2) `git filter-repo --invert-paths --path .env` or BFG, force-push **with partner coordination**, both re-clone. (3) Write `docs/evidence/incident-secret-exposure.md`: what leaked, when, rotation timestamp, blast radius. §5.3 demands the rotation **and** the incident note; the −20 is for the exposure, the note is how you show you understand it. (4) Add the pattern to `.gitleaks.toml` and to the pre-commit hook. |
| **`main` broken** | Revert first, diagnose second. `git revert -m 1 <merge-sha>`, push via PR (protection still applies), then fix forward on a branch. |
| **Cluster wedged** | `k3d cluster delete civicpulse && make k8s-up`. The cluster is cattle; the PVC contents are the only thing worth grieving, and `make db-dump` runs nightly. |
| **Partner unreachable > 48 h** | §5.4: *"If your partner is not contributing, say so in week 1, not week 5."* Escalate to the instructor in writing, keep working, and keep `git shortlog` honest. |
| **Free-tier key dies** | Flip `TRIAGE_PROVIDER=ollama`. §2.5: *"you lose no marks for it."* This is why the provider interface exists; exercising it is the assignment's own thesis. |
| **Behind schedule** | §5.1 priority order: **F (AI) > C (backend) > I (CI/CD) > H (Kubernetes)**. Cut bonus items first, then H's VPA loop, then frontend polish. **Never cut the fallback test.** |
