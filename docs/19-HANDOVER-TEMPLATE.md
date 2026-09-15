# 19 — HANDOVER PROTOCOL AND TEMPLATES

> **Owner:** both, every session · **Rubric:** indirect (A, and the viva factor)
> A Claude Code window is a *session*, not a *process*. It ends — by choice, by context limit, by a
> closed laptop. The handover file is the only thing standing between **"resume in four minutes"**
> and **"re-derive ninety minutes of context"**.
>
> It is also what lets your partner pick up your branch when you are unreachable, which §5.4 says
> you should plan for in week 1, not week 5.

---

## 1. The rules

| Rule | Reason |
|---|---|
| **One handover file per branch**, at `docs/handover/HANDOVER-<branch-slug>.md` | Branch = unit of work = unit of context |
| **Written at CLOSE, read at OPEN** — steps 2 and 12 of the session loop (`01-WORKFLOW.md §5`) | A handover written from memory the next morning is fiction |
| **Committed to the branch**, not kept locally | Your partner must be able to `git switch` and read it |
| **Deleted when the branch merges** (`git rm` in the final commit) | A stale handover is worse than none. The PR body carries the durable summary |
| **Written for a stranger**, not for yourself | You are a stranger to your own context after 48 hours. §1.4 calls this *"the same bar as a real handover"* |
| **Never contains a secret** | It is committed. `make secret-scan` covers `docs/` |
| **Under 120 lines** | Longer means you are writing a diary, not a handover |

### 1.1 The five questions a handover must answer

If a section does not serve one of these, delete it.

1. **Where am I?** — branch, base SHA, phase, issue.
2. **What is green?** — exactly which commands pass right now.
3. **What is half-done?** — the thing that will confuse whoever reads the diff.
4. **What is the literal next command?** — not "continue the work". A command.
5. **What will bite?** — the trap you already fell into and do not want repeated.

---

## 2. The template

```markdown
# HANDOVER — feat/ai-triage-fallback-ladder

<!-- Written at session close. Delete this file in the merge commit. -->

## 1. Position
| | |
|---|---|
| Branch | `feat/ai-triage-fallback-ladder` |
| Base | `dev` @ `4f1a2b9` (rebased 2026-09-22 16:10Z) |
| Phase / Gate | P4 → Gate 4 |
| Issue | #23 |
| Owner | DEV-A |
| Session ended | 2026-09-22 19:40Z |
| Files touched | `providers/triage/{base,llm,rules,simulated,factory}.py`, `services/triage_service.py`, `tests/integration/test_triage_fallback.py` |

## 2. Green right now
```bash
make check                                   # PASS (ruff, mypy, 78 tests, cov 71%)
pytest -m "unit or contract" -q              # PASS  4.1s
pytest backend/tests/integration/test_triage_fallback.py -q   # PASS  6 of 8
```
Last green commit: `9c2de11`.

## 3. Red right now
- `F5 test_rate_limit_retried_exactly_once` — FAILS. Counts **3** attempts, expects 2.
- `F9 test_total_budget_prevents_second_attempt` — SKIPPED (marked xfail, not yet implemented).

## 4. Half-done — read this before reading the diff
`TriageService.triage_with_fallback` is **complete for the raise/malformed paths** but the
retry accounting is wrong. `attempts` is incremented at the top of the loop *and* the
OpenAI SDK is still doing its own internal retries, so the observed count is
`our_attempts × sdk_retries`. `llm.py:L34` needs `max_retries=0` on the `AsyncOpenAI`
constructor — see `08-AI-TRIAGE.md §3.3`, which says exactly this and which I did not read
carefully enough.

`RuleBasedTriage.priority` currently returns `NORMAL` for everything; the urgency term list
exists (`rules.py:L22`) but is not wired into the scorer yet.

## 5. Next command
```bash
# 1. fix the SDK double-retry
sed -n '30,40p' backend/app/providers/triage/llm.py    # add max_retries=0
pytest backend/tests/integration/test_triage_fallback.py::test_rate_limit_retried_exactly_once -q
# 2. then wire urgency terms into RuleBasedTriage.priority and un-xfail F9
```

## 6. Open decisions (need a ponytail pass or a partner opinion)
- **Should a low-confidence LLM result fall back to rules, or be accepted as `other`?**
  Leaning: accept as `other` with `priority=NORMAL` and flag it in the ring, because a
  fallback would lose a real (if uncertain) judgement. Needs to land in ADR-0001 §Confidence.
- **Is `triage_confidence` persisted?** Contradiction A5 says yes, superset of spec. Column exists,
  service does not populate it yet.

## 7. Gotchas discovered this session
- `SimulatedTriage` seeding must be `seed ^ crc32(text)`, not `seed + hash(text)` — Python's
  `hash()` is salted per process (`PYTHONHASHSEED`), so tests passed locally and failed in CI.
  Cost 40 minutes. **Candidate for §5.2 question 8.**
- `respx` does not intercept the OpenAI SDK's client unless you pass the `httpx` client in
  explicitly. Use the `FailureMode` doubles instead — simpler and deterministic.

## 8. Do not touch
- `backend/app/schemas/stats.py` — DEV-B is editing it for the scheduled merge-conflict drill
  (`01-WORKFLOW.md §2.4`). Collision is intentional; do not pre-resolve it.
- `frontend/src/api/schema.d.ts` — generated. If it changes, that means the contract changed,
  which needs a `chore/contract-*` PR.

## 9. Spec clauses this branch must satisfy before the PR opens
- [x] §2.5 item 4 — fallback to rules, `triaged_by="rules:fallback"` (F1 green)
- [ ] §2.5 item 3 — exactly one jittered retry on timeout/429/5xx only (F5 red)
- [x] §2.5 item 1 — structured output validated against Pydantic (F2, F3, F4 green)
- [ ] §2.2 — exactly one WARNING per fallback (F20 not yet written)
- [x] Rubric F line 1 — ≥3 implementations behind the interface

## 10. AI usage this session (mirror into docs/AI-USAGE.md)
- `caveman` → 7-task decomposition of the ladder; merged tasks 4+5 (shared `except` ladder).
- `grilled meat` → found the missing `aclose()` on `LLMTriage`, and proposed retrying on
  `ValidationError`, which I **rejected** citing §2.5 item 3.
```

---

## 3. Variants

### 3.1 Emergency handover (partner takes over an unfinished branch)

Add at the top, before §1:

```markdown
## 0. EMERGENCY — taking over
**Confidence in this branch: medium.** The fallback ladder works; the retry accounting does not.
**Safe to merge?** No. **Safe to build on?** Yes, the interface in `base.py` is stable and frozen.
**If you need this working in 20 minutes:** set `TRIAGE_MAX_RETRIES=0` in `.env`; the fallback
path is correct and the retry path is the only broken part. F1 (the spec-mandated test) is green.
**Cheapest path to green CI:** mark F5 and F9 `xfail` with a linked issue, merge the rest, fix in a
follow-up. Do **not** delete them.
```

### 3.2 Phase-gate handover (end of a phase, before the `dev → main` PR)

Replace §4–§7 with the gate checklist from `02-CRITICAL-PATH.md §4`, ticked, plus:

```markdown
## Evidence produced this phase
| Artefact | Path | Proves |
|---|---|---|
| fallback WARNING sample | `docs/evidence/…` | C5, F3 |
| cache hit-rate snapshot | `docs/TRIAGE.md §6` | F4 |

## Rubric lines moved to PROVEN in 20-RUBRIC-TRACEABILITY.md
F1, F2, F3 (partial — retry line still PENDING)

## What the next phase depends on from this one
P5 (cache) needs `TriageService` to expose `content_key()` — it does, at `triage_service.py:L18`.
```

### 3.3 Cross-boundary handover (an ownership swap, `01-WORKFLOW.md §1`)

Add:

```markdown
## Orientation for someone new to this area
- **Start here:** `08-AI-TRIAGE.md §5` — the whole ladder is 40 lines and that section explains
  every line's spec justification.
- **Mental model:** cache → primary (≤2 attempts, budget-bounded) → rules. Rules cannot raise.
- **The one invariant:** `POST /api/complaints` returns 201 unless the *request* or the *database*
  is broken. No provider failure may ever produce a 5xx.
- **Where the tests are:** `tests/integration/test_triage_fallback.py`. F1 first, deliberately.
- **What will surprise you:** `extra="ignore"` on `TriageResult` vs `extra="forbid"` on
  `ComplaintCreate`. Deliberate asymmetry — see `04-CONTRACTS.md §7`.
```

---

## 4. `docs/handover/INDEX.md` — the live board

One table, updated at every close. This is the ten-second answer to *"what is in flight?"* at
standup, and the first thing you read after 48 hours away.

```markdown
| Branch | Owner | Phase | State | Blocked on | Last touched |
|---|---|---|---|---|---|
| `feat/ai-triage-fallback-ladder` | A | P4 | 🟡 6/8 tests | nothing | 2026-09-22 19:40Z |
| `feat/fe-dashboard-filters` | B | P4 | 🟢 green, PR open | A's review | 2026-09-22 18:05Z |
| `chore/ci-trivy-kubeconform` | B | P5 | 🔴 kubeconform fails on VPA CRD | schema-location flag | 2026-09-22 16:30Z |
| `spike/groq-json-mode` | A | — | ⚫ abandoned, findings in ADR-0001 | — | 2026-09-19 |
```

Legend: 🟢 green · 🟡 in progress · 🔴 red · ⚫ abandoned (never merged, findings extracted).

---

## 5. Why this is worth the five minutes

| Without a handover | With one |
|---|---|
| Re-read the diff to rebuild intent | §4 tells you the intent in three sentences |
| Re-run everything to find what is green | §2 and §3 tell you |
| Re-discover the `PYTHONHASHSEED` trap | §7 already paid that cost once |
| Guess whether the branch is safe to build on | §0/§1 says so explicitly |
| Two people edit `stats.py` by accident | §8 prevents it |
| Reconstruct AI attribution at the end (§5.5) | §10 captured it at the moment |
| Your partner cannot continue your work | They can, in four minutes |

That last row is the one the rubric cares about. §5.4 examines you on **your partner's code**, and
§1.4 sets the bar as *"the same bar as a real handover."* The handover files are the mechanism by
which two people end up genuinely understanding one system instead of two halves.

**Enforcement:** the PR template's phase-gate checkbox includes *"handover file updated or
deleted"*, and `make check` warns (does not fail) when the current branch has commits newer than
its handover file:

```bash
handover-check:
	@b=$$(git rev-parse --abbrev-ref HEAD); f="docs/handover/HANDOVER-$${b//\//-}.md"; \
	 if [ -f "$$f" ] && [ "$$(git log -1 --format=%ct -- $$f)" -lt "$$(git log -1 --format=%ct)" ]; then \
	   echo "WARN: $$f is older than your last commit"; fi
```
