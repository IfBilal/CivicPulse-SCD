# HANDOVER — rubric-evidence closure pass on fix/close-disclosed-gaps

<!-- Written at session close, 2026-09-26. This is an evidence-audit session, not a
     feature branch — delete or fold into the branch's real handover once merged. -->

## 1. Position
| | |
|---|---|
| Branch | `fix/close-disclosed-gaps` |
| Base | `2d6368a` (merge of origin/dev) |
| Task | Move `docs/20-RUBRIC-TRACEABILITY.md` rows from ☐ to ☑ only where a real test/check AND a real evidence file both exist — no Docker/k8s/live DB available in this sandbox |
| Session ended | 2026-09-26 |
| Files touched | `docs/20-RUBRIC-TRACEABILITY.md` (Status column + inline notes only), `docs/AI-USAGE.md` (appended), 10 new files in `docs/evidence/`, this handover |
| Committed? | **NOT committed.** Working tree left with these changes unstaged, per instruction — review and commit yourself |

## 2. What moved from ☐ to ☑ (30 rows total)

**Rubric rows (21):** A1, A2, B5, C2, C7, E4, F5, F7, G2, G3, G4, G6, H1, H2, H4, I1, I2, I3, I6, I7, J2
**Deduction-armour rows (9):** all except "secret anywhere in git history" and "README quickstart fails from clean clone" (both need a live run/tool not available here)

Each ☑ row has an inline note in the table itself saying exactly what was verified and against which evidence file — read the row, not just the checkbox.

## 3. New evidence files in `docs/evidence/`
| File | Proves |
|---|---|
| `branch-ruleset.json` | Live GitHub ruleset on `main`: PR+CODEOWNERS review, 7 required CI jobs, no-bypass (A1) |
| `pr-review-audit.txt` | Audit of all 35 merged PRs' actual review bodies — **disproves** A3's "substantive partner review" claim (12 PRs have zero reviews; nearly all others are empty-body rubber stamps) |
| `shortlog.txt` | Identity-merged commit-authorship analysis — A4 is genuinely contested (35.9% vs 22.6% depending on counting method), left unresolved honestly |
| `ci-red-then-green.txt` | Real red→green CI history for PR #43/#45 via live `gh run list`/`gh pr checks` (I7) |
| `ci-workflow-structure.txt` | Structural read of ci.yml/cd.yml (I1-I6) — **also discloses cd.yml has never run** (only `ci` is registered on GitHub; I4/I5 stayed ☐ because of this) |
| `test-stability.txt` | 275/275 unit+contract tests pass, 3 independent runs, 90.11% coverage (C7) |
| `check-submission-run.txt` | Real `check_submission.py` run with `backend/.venv` actually installed — fixed a false "0 tests collected" into a real "300 collected" |
| `layer-lint-and-typecheck.txt` | `make lint-layers`/`lint-localhost`, `mypy --strict`, `ruff` all run live, all clean (C2) |
| `frontend-test-run.txt` | 14/14 frontend tests pass live (B5) |
| `static-code-audit-DEFGH.txt` | Line-by-line static verification of D1-D4, E1-E4, F1-F7, G1-G6, H1-H6 against actual source files |

## 4. Real findings worth your attention (not just "still pending")

1. **A3 is disproven, not just unproven.** 12 of 35 merged PRs have zero reviews; almost every
   review elsewhere is an empty-body "APPROVED" — the exact rubber-stamp pattern
   `CLAUDE.md §6` rule 5 explicitly warns against. If a marker checks this (they can, with
   `gh pr list --json reviews`), it will look bad unless some PRs get real review comments
   retroactively — which you can't do for merged PRs. Consider whether future PRs need
   real substantive reviews to average this out, or whether to disclose it plainly in
   README §Known limitations.
2. **`main` is stale and cd.yml has never run.** `origin/main` is 58 commits behind
   `origin/dev` and not even an ancestor of it (diverged, not just behind). `cd.yml` only
   exists on `dev`/feature branches — GitHub's Actions API confirms zero registered
   workflow runs for it. I4 and I5 cannot be proven until `dev` → `main` merges via a real
   PR and a real push to `main` triggers `cd.yml` at least once.
3. **A4's commit-share number is genuinely ambiguous.** `check_submission.py`'s own
   `RUBRIC-COMMITS` check reports 7.5% because it treats the two contributors' git-identity
   aliases (T361/Taimoor Shaukat, IfBilal/8BitNinja) as four separate people. Correctly
   merged, it's either 35.9% (passes) or 22.6% (fails) depending on whether you count
   `--all` refs or just `main`'s own history. Decide which counting method you'll defend at
   viva and verify the real number against exactly that method.
4. **J3 (RUNBOOK) and J5 (8-question ENGINEERING-NOTES structure) are not written at all**,
   not just missing evidence. `docs/ENGINEERING-NOTES.md` is a real, substantial 978-line
   decision log but doesn't answer the specific 8 questions `18-DOCS-EVIDENCE-VIVA.md §4`
   requires. J1 (README) is missing most of its required sections (Mermaid diagram, API
   table, screenshots, evidence index, ADR links, known-limitations, AI-usage link, team).

## 5. Rows BLOCKED on a live environment — exact commands to close them

```bash
# D4, E1, E3 — integration tests needing real Postgres/Redis via testcontainers
cd backend && pytest -m integration -q
# (needs a working Docker daemon; this sandbox's socket returned permission denied)

# G1, G5 — real image builds and compose healthchecks
docker compose build
docker compose up -d --build --wait
docker compose ps --format "{{.Service}}\t{{.Health}}"

# E1/E2 cache-behaviour capture (X-Cache MISS then HIT, then invalidation)
docker compose exec -T cache redis-cli FLUSHALL
curl -si localhost:8080/api/stats | grep -i '^x-cache:'   # expect MISS
curl -si localhost:8080/api/stats | grep -i '^x-cache:'   # expect HIT
curl -s -XPOST localhost:8080/api/complaints -H 'content-type: application/json' \
  -d '{"text":"...","location":"..."}' -o /dev/null
curl -si localhost:8080/api/stats | grep -i '^x-cache:'   # expect MISS again
# save all four outputs to docs/evidence/cache-behaviour.txt

# E3 distributed rate-limit proof under real concurrent load
for i in $(seq 1 12); do curl -s -o /dev/null -w '%{http_code}\n' -XPOST \
  localhost:8080/api/complaints -H 'content-type: application/json' -d @fixtures/one.json; done
# save to docs/evidence/ratelimit-distributed.txt

# H3, H5, H6 — live k3d/kind cluster, HPA/VPA
make k8s-up
kubectl -n civicpulse get pod -o jsonpath='{.items[*].spec.containers[*].livenessProbe}'
kubectl -n civicpulse get hpa -w    # capture a few minutes, save as hpa-watch.txt
# run load/*.js with k6 against the ingress, save k6-summary.json
# VPA needs the cluster running long enough to emit recommendations, then:
kubectl -n civicpulse describe vpa backend-vpa > docs/evidence/vpa-describe-run1.txt

# I4/I5 — a real cd.yml run
# 1. open a real PR merging dev into main (or wherever cd.yml currently lives) and merge it
# 2. gh run list --repo IfBilal/CivicPulse-SCD --workflow cd.yml
# 3. capture the GHCR package page (shows SHA-tagged images) for I4's evidence

# J1 README clean-clone quickstart test
git clone <repo-url> /tmp/clean-clone && cd /tmp/clean-clone && make up
# time it, screenshot the result, save to docs/evidence/

# Deduction-armour "secret in git history" — needs gitleaks binary
pip install gitleaks || brew install gitleaks   # or download the release binary
gitleaks detect --source . --log-opts="--all" > docs/evidence/history-scan.txt

# J4 video — needs both partners actually recording ≤5 min, six required beats
```

## 6. Next command
```bash
git diff --stat                       # review everything before committing
git add docs/20-RUBRIC-TRACEABILITY.md docs/AI-USAGE.md docs/evidence/ docs/handover/
git commit -m "docs: close statically-provable rubric-evidence gaps"
# do NOT push — leave for the user to review and push themselves
```

## 7. Do not touch
- `docs/20-RUBRIC-TRACEABILITY.md`'s column structure/headers — only Status values and
  inline notes were changed this session, per the task's explicit constraint.
- Do not mark A3, A4, I4, I5, J1, J3, J5, or any H5/H6/D-row without a live-DB artefact as
  ☑ — they are genuinely unproven or actively disproven, not just "probably fine."
