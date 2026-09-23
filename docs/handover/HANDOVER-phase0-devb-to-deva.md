# HANDOVER — Phase 0 Bootstrap, DEV-B → DEV-A

**From:** IfBilal (DEV-B / Edge) · **To:** T361 (DEV-A / Core) · **Date:** 2026-09-20
**Phase:** P0 Bootstrap · **Gate:** Gate 0 (`02-CRITICAL-PATH.md §4`) — not yet closed, blocked on you

This is not a replacement for the planning docs — it doesn't re-explain anything already
written there. It's the "here's exactly where we are, here's exactly what's on you, here's
what will bite you" note so you don't have to re-derive it. Full role/ownership context is in
`01-WORKFLOW.md §1` and `§3.2` if you haven't read it yet — read it before you start.

---

## 1. What's already done (my half)

Everything in the **DEV-B column** of `02-CRITICAL-PATH.md §5` Day 1, plus the Gate 0
branch-protection line, is merged into `dev` and verified working:

- `.gitignore`, `.env.example`
- `.gitleaks.toml` + `.pre-commit-config.yaml` — secret scanning, **verified** to actually
  block a fake secret (`docs/evidence/precommit-secret-block.txt`)
- `.github/` — PR template, issue templates, `CODEOWNERS` (real usernames, not placeholders)
- `.github/workflows/ci.yml` — Phase 0 placeholder job only (see §4 of this file for why)
- Branch protection ruleset on `main` — PR required, 1 approval, required status check,
  linear history, no bypass for anyone including admins (`docs/evidence/branch-protection.png`)
- A **minimal** `Makefile` — one target only (`lint-localhost`), just enough for pre-commit
  to function. **This is not the real Makefile** — see §2.

Merged PRs so far: #2, #3, #4, #6, #7, #8 (all `dev`), #5 (`dev → main`, the first Gate 0
integration PR — you already reviewed and approved this one).

---

## 2. What's on you — DEV-A's Phase 0 slice

Per `02-CRITICAL-PATH.md §5` Day 1 (DEV-A column) and `03-REPO-BOOTSTRAP.md §4–§5`:

| Task | Where it's specified |
|---|---|
| `backend/pyproject.toml` (deps, ruff, mypy, pytest+cov config) | `03-REPO-BOOTSTRAP.md §4` — full file content is given verbatim, copy it |
| Backend Makefile targets (`lint`, `type`, `test-be`, `migrate`, `seed`, etc.) | `03-REPO-BOOTSTRAP.md §5` — merge these into the existing `Makefile` at repo root, don't create a second one |

Start from `dev`, not `main` — `main` is locked down now (see §3). Branch name per convention
(`01-WORKFLOW.md §2.1`): something like `chore/be-pyproject-bootstrap`.

**Before you start, point your Claude Code session at the actual docs.** Don't just say "do
DEV-A's bootstrap" — tell it to read `00-SPEC.md`, `01-WORKFLOW.md`, `02-CRITICAL-PATH.md`,
and `03-REPO-BOOTSTRAP.md` first, and to follow `§4`/`§5` exactly. The full file contents are
already written out in those docs — this isn't a from-scratch design task, it's transcription
plus judgement calls where the doc leaves something open.

---

## 3. Ground rules now in effect (they weren't, before today)

- **`main` is protected.** No more direct pushes — not even for admins. Everything goes
  branch → PR → `dev`, and periodically `dev` → PR → `main`.
- **PRs need a real review comment, not "LGTM."** `01-WORKFLOW.md §2.3` is explicit that a
  rubber-stamp scores zero on Rubric A. I'll review your PRs the same way — expect actual
  comments, not silence-then-approve.
- **Link every PR to an Issue** (`Closes #N`). Don't open orphan PRs.
- **`CODEOWNERS` is live** — `/backend/app/providers/` and `/backend/alembic/` route to you,
  `/frontend/`, `/k8s/`, `/.github/workflows/` route to me, `/backend/app/schemas/` and
  `/docs/adr/` need both of us.

---

## 4. Why `ci.yml` is only a placeholder right now

It's deliberately not the real 7-job pipeline (`lint-and-type`, `test-backend`,
`test-frontend`, `build`, `scan`, `manifests`, `integration` — see `15-CICD.md`). That pipeline
needs `backend/` and `frontend/` to exist first. Right now it just does repo-hygiene checks
and a gitleaks scan — enough to give branch protection something real to require. **Don't be
surprised it's thin; it's Phase 5 work, not Phase 0.**

---

## 5. Bugs I already hit, so you don't have to

All three cost real time before I found them. Worth knowing before you touch CI or
pre-commit yourself:

1. **`.gitleaks.toml`'s custom regex used a `(?!...)` negative lookahead** — gitleaks compiles
   rules with RE2, which has zero lookahead support, and it doesn't fail gracefully, it
   **crashes the whole process**. Already fixed, but if you add a custom gitleaks rule later,
   remember: no lookahead, ever. Use an `[rules.allowlist]` for exclusions instead.
2. **`gitleaks-action` needs `GITHUB_TOKEN` explicitly on `pull_request` events** — it works
   fine on `push` without it, which is exactly why this one is easy to miss until a real PR
   triggers it.
3. **`actions/checkout@v4` defaults to `fetch-depth: 1`** — gitleaks (and later, kubeconform
   drift checks, coverage diffing, etc.) often need full history. If a job behaves differently
   on a PR than on a push and you can't see why, check this first.
4. **A YAML plain scalar can't contain an unescaped `: `** — the `.pre-commit-config.yaml`
   conventional-commit hook's regex tripped this. If you write a pre-commit hook `entry` with
   a colon inside it, wrap the whole value in single quotes.

---

## 6. What happens after your Phase 0 slice lands

1. We extend the `Makefile` together to its full form (`03-REPO-BOOTSTRAP.md §5`) now that
   `backend/` exists.
2. We build `scripts/check_submission.py` (currently doesn't exist — it needs backend paths
   to check against).
3. One more `dev → main` PR — this one actually closes Gate 0. Walk the checklist in
   `02-CRITICAL-PATH.md §4` (PHASE 0 section) together before opening it.
4. **Phase 1 — Contract Freeze** starts. This one is joint, one PR, both of us, per
   `02-CRITICAL-PATH.md §4` (PHASE 1) and `04-CONTRACTS.md`. Read `04-CONTRACTS.md` before
   that session — it's the file everything else fans out from.

---

*Drafted with Claude Code from the DEV-B side. Corrections/disagreements welcome — this
reflects my understanding of the docs, not a ruling.*
