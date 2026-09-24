# AGENTS.md — CivicPulse

Operational reference for any coding agent working in this repo (Claude Code, Codex,
Cursor, etc.). For the non-negotiable rules, read `CLAUDE.md` first — this file assumes
you already have and it doesn't restate the "never" list, it tells you how to move.

## Project

Two-developer, 14-day build: a municipal complaint intake/triage system. Backend is
FastAPI + Postgres 16 + Redis 7; frontend is React 18 + Vite + nginx; deploy target is
Kubernetes (k3d) with GitHub Actions CI/CD. Single source of truth: `00-SPEC.md`.
Frozen API contract: `04-CONTRACTS.md`.

## Repo layout

```
backend/app/
  main.py            app factory + lifespan + signal wiring — nothing else
  config.py          the ONLY os.environ reader
  domain/            enums.py, transitions.py — pure, no I/O
  schemas/           Pydantic DTOs (wire contract)
  routes/            HTTP only, thin
  services/          business rules, orchestration
  repositories/      all SQL
  providers/
    triage/          base.py (Protocol), llm.py, ollama.py, rules.py, simulated.py, factory.py
    cache/           redis_cache.py
    ratelimit/       redis_limiter.py, lua/fixed_window.lua
  middleware/        request_id, logging, metrics, ratelimit
  db/                session.py, models.py
  obs/               logging_config.py, metrics.py, ring.py
  cli/               seed.py, openapi_dump.py
frontend/src/{components,pages,api}/
k8s/base/, k8s/overlays/{dev,prod}/
docs/{adr,evidence,handover}/, docs/{ENGINEERING-NOTES,RUNBOOK,AI-USAGE,TRIAGE}.md
```

## Commands

```bash
make up                              # one-command local run, no API key required
make openapi && make gen-client      # regenerate typed client after any contract change
pytest -m "unit or contract" -q      # fast loop, run before every commit (~4s)
pytest -m integration -q             # real Postgres/Redis via testcontainers (~90s)
pytest                                # everything + coverage gate (--cov-fail-under=65)
ruff check . && mypy .                # lint + types, part of `make check`
python scripts/check_submission.py    # the deduction-armour lint, run before any PR
```

Backend tests are markered: `unit`, `contract`, `integration`, `slow`. `contract` tests
assert the frozen wire shape of `04-CONTRACTS.md` and must never be edited to make a
change pass — if a contract test fails, the code is wrong, not the test (unless the
contract itself is being changed via the formal process).

## Environment

`TRIAGE_PROVIDER` switches the classifier with zero call-site changes:
`simulated` (default, CI, no key/network needed) · `rules` (degraded mode) ·
`ollama` (local model, zero egress) · `llm` (Groq/Gemini, needs `LLM_API_KEY`).
Never require a real key for the default path — a stranger must be able to clone and
run this with one command and nothing else.

## Conventions

- Conventional commit prefixes; branch per unit of work; PR per branch; both people
  approve; issue-linked.
- Session boundaries get a handover file at `docs/handover/HANDOVER-<branch>.md`
  (template in `19-HANDOVER-TEMPLATE.md`): position, what's green, what's half-done,
  the literal next command, what will bite. Write it at close, read it at open. Delete
  it in the merge commit.
- Every design decision not fully dictated by the spec gets one paragraph in
  `docs/ENGINEERING-NOTES.md` — what was chosen, what the alternative was, why.
- Structured JSON logs to stdout, `request_id` on every line, `SecretStr` for anything
  that could be a credential.
- `StrEnum` for every closed vocabulary (`Category`, `Priority`, `Status`, `TriagedBy`)
  so wire format and Python equality line up with zero `.value` ceremony.

## Mandatory skill cadence

Two named Claude Code skills fire at fixed points every session and are not optional:
`caveman` (phase start → stripped task list), `ponytail` (every design fork → decision
stub with rejected alternatives). A pre-PR hardening review (before every PR → ≥3
findings with file:line) is also required, but is a review discipline, not a named
skill — the skill that shares its old nickname, `grill-me` (real behavior: an
interactive interview with the user about a plan/decision, not a diff scanner), is
optional on this project. Full trigger conditions and acceptance tests are in
`CLAUDE.md §6` — that's the authority, this is just the reminder that it applies to
every session, not just the first one. Every invocation gets logged in
`docs/AI-USAGE.md` at the time it happens, including what you overrode and why.

## Definition of done for a phase

Not "the code runs." A phase is done when:
1. Its tests are green under `pytest -m "unit or contract"` **and** `integration`.
2. `python scripts/check_submission.py` reports no new violations.
3. The relevant row(s) in `20-RUBRIC-TRACEABILITY.md` can be flipped to `PROVEN` because
   both the test and the evidence artefact exist — not one without the other.
4. A handover file exists if the branch isn't merging immediately.
5. `caveman`, `ponytail` (if a fork occurred), and the pre-PR hardening review fired
   at their required points and are logged in `docs/AI-USAGE.md` — see `CLAUDE.md §6`.

## Where to look when stuck

| Question | File |
|---|---|
| What does the API actually promise? | `04-CONTRACTS.md` |
| Why does this contradiction exist and what do we default to? | `00-SPEC.md` Appendix A |
| What's the fallback ladder's exact timing/retry logic? | `08-AI-TRIAGE.md §5` |
| What test proves this rubric line? | `20-RUBRIC-TRACEABILITY.md` |
| Is this a known trap someone already paid for? | `14-LOAD-AUTOSCALING.md §0`, any `docs/handover/*` §7 |
