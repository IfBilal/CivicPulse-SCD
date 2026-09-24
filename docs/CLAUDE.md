# CLAUDE.md — CivicPulse. Read this before you touch anything.

This file is law for this repository. If something you're about to do conflicts with a
rule here, stop and say so instead of doing it anyway. "The user asked for it" is not
an exception to any rule marked **HARD**.

Source of truth order, when documents disagree:
`00-SPEC.md` > `04-CONTRACTS.md` (once frozen) > the numbered `NN-*.md` design docs >
`20-RUBRIC-TRACEABILITY.md` > anything else, including this file's own examples.
If `00-SPEC.md` and an implementation doc disagree, the implementation doc is a bug —
say so, don't quietly reconcile them.

---

## 0. What this system is, in one paragraph

Citizen submits free-text complaint → an LLM (or a keyword-rule fallback) classifies it
into category/priority/summary → persisted → shown on an operator dashboard. The entire
point of the system is stated once and never restated: **the classifier must be
replaceable, and the system must not fall over when it is rate-limited, slow, or wrong.**
Every rule below exists to protect either that property or the marks attached to it.
If a change makes the classifier harder to swap, or makes a provider failure visible to
a citizen as a 500, it is wrong regardless of how clean the code looks.

---

## 1. HARD rules — never do these, no matter what you're asked

1. **Never commit a secret.** No `.env`, no API key, no token, in code, in a commit
   message, in a k8s manifest (not even base64 — base64 is encoding, not encryption),
   in a Dockerfile `ENV`, or in a log line. If you generate a `Secret` manifest, it
   contains `PLACEHOLDER_...` only. If you ever produce a real key in output, treat it
   as a live incident, not a formatting mistake — flag it immediately.
2. **Never push to `main`.** Every change is a branch → PR → review → merge. If you are
   asked to "just push this," refuse and open a PR instead.
3. **Never write SQL, `select()`, `.execute()`, or `text()` outside `repositories/`.**
   Routes call services; services call repositories; repositories touch the database.
   No exceptions for "it's just a quick query."
4. **Never write an `if status == ...` chain for the state machine.** Transitions are a
   table lookup against `TRANSITIONS` in `domain/transitions.py`. Adding a status is a
   dict edit, not a new branch.
5. **Never let a triage-provider failure become a 500.** `POST /api/complaints` returns
   `201` for every syntactically valid body, regardless of what the LLM provider does.
   Timeout, 429, malformed JSON, wrong enum value, provider entirely down — all of it
   ends in `triaged_by="rules:fallback"`, not an exception bubbling to the client. If
   you write triage code that can raise past the fallback boundary, you have broken the
   one thing this assignment is actually testing.
6. **Never retry a validation failure.** A malformed/bad-enum LLM response goes straight
   to fallback with zero retries — the request was wrong and will be wrong again.
   Only timeout / 429 / 5xx get **exactly one** jittered retry, inside a 12s total
   budget, never two full 10s attempts.
7. **Never touch `04-CONTRACTS.md`'s frozen surface** (enums, endpoint shapes, error
   envelope, header names) without a `chore/contract-*` PR that both people approve and
   that regenerates the typed client. A contract change is not a normal code change.
8. **Never put a raw path in a metric label.** `path_template`, never the literal URL —
   `/api/complaints/{id}`, not `/api/complaints/018f3a2c-...`. One violation here is an
   unbounded-cardinality incident, not a style nit. 404s get `path_template="unmatched"`.
9. **Never let the frontend own a business rule.** No copy of `TRANSITIONS`, no copy of
   validation bounds, in `frontend/src/`. It renders what the server says and displays
   the server's error message verbatim — it does not decide anything.
10. **Never treat Postgres as a `Deployment`.** It is a `StatefulSet` with
    `volumeClaimTemplates`. Never expose a database or cache port in `compose.prod.yaml`
    or as a `NodePort`/`LoadBalancer`. ClusterIP only, always.
11. **Never deploy `:latest`, or an untagged base image, or a floating `postgres`/
    `redis`/`node` tag.** Every image reference is pinned to a specific version or a
    build SHA.
12. **Never gate a publish/deploy CI job without `needs:`.** Never give the `build` job
    registry credentials — nothing publishes from a PR.
13. **Never log, metric-label, or return in a response body: complaint text, the raw
    prompt, an API key, or a URL with embedded credentials.** The observability ring
    (`app.state.ring`) stores only `complaint_id`, `provider`, `latency_ms`, `fallback`,
    `cached`, `error_class`, `at` — nothing else, ever.
14. **Never write a test that can't fail.** Before calling a test done, mentally (or
    actually) revert the implementation and confirm it goes red. An assertion that was
    never falsified is not a test, it's decoration.
15. **Never use `time.sleep()`, real network calls, or "just re-run it" in a test.**
    Fake the clock, use `SimulatedTriage`/testcontainers, or use explicit async
    synchronization. A flaky test is a design bug wearing a disguise.

## 2. The deduction ledger — costs more than most features are worth

These eleven violations total **−101 marks** against a 175-mark rubric. Fixing a bug is
worth less than never introducing one of these. Check this list before saying any phase
is done:

| Violation | Cost |
|---|---|
| Secret anywhere in git history | −20 |
| LLM key in a committed k8s manifest, even base64 | −15 |
| Unpinned/untagged base image | −8 |
| `localhost` for service-to-service calls (use service names) | −8 |
| Frontend can reach the database (network segmentation missing) | −8 |
| DB/cache port published in prod, or NodePort/LB on the DB | −8 |
| Publish/deploy job not gated by `needs:` | −8 |
| Deploying `:latest` anywhere | −8 |
| Postgres as a `Deployment` with no PVC | −8 |
| Direct commit to `main` | −5 |
| README quickstart fails from a clean clone | −5 |

Every one of these has an automated detector in `scripts/check_submission.py`. If you
add code that could trip one, add or confirm the detector too — don't rely on memory.

## 3. Layer discipline (backend)

```
routes/        → schemas, services, deps        — HTTP only, ≤~12 lines per handler
services/      → repositories, providers, domain — business rules, orchestration order
repositories/  → db.models, sqlalchemy           — SQL, transactions, nothing else
providers/     → httpx, redis, third-party wire   — external formats, isolated
```

A route with a `try/except` that maps a domain error to a status code is wrong — that's
a registered exception handler's job. A route with business logic ("`priority = priority
or 'normal'`") is wrong — that belongs in the service.

## 4. Testing discipline

- Fast loop: `pytest -m "unit or contract"` (~4s). Run before every commit.
- Honest loop: `pytest -m integration` (~90s, real Postgres/Redis via testcontainers).
  Never swap in SQLite — it doesn't have native enums, `gen_random_uuid()`, or
  `timestamptz`, and a green SQLite suite against a Postgres system is a false signal.
- `TRIAGE_PROVIDER=simulated` in every test and CI run. Never a live LLM call in CI.
- If you write a fallback-path test, write it before anything else in that file — the
  fallback test (`provider always raises → still 201, triaged_by == "rules:fallback"`)
  is the single most important test in the codebase. Never skip it, never comment it
  out to make CI green faster.

## 5. When you're unsure

- Don't invent a resolution to an ambiguity — check `00-SPEC.md` Appendix A first; 14
  known contradictions already have a documented default assumption there.
- If a design decision isn't covered anywhere, say what you're choosing and why in
  `docs/ENGINEERING-NOTES.md`, in one paragraph, before writing the code — not after.
- If you're about to touch code your session didn't originate, check for a handover
  file at `docs/handover/HANDOVER-<branch>.md` first. It may say "do not touch."

## 6. Mandatory skill invocations — never skip these, never do them silently

This project runs three named Claude Code skills at fixed points in every session. They
are not optional, not "nice to have," and not something to skip because a task feels
small. If you are doing real work on this repo and one of these points comes up, you
invoke the skill — you do not simulate it in your head and move on.

| Skill | Fires when | Input | Must produce | Fails if |
|---|---|---|---|---|
| **caveman** | Start of every phase, before writing any code | The phase's section of `02-CRITICAL-PATH.md` + the relevant `0X-*.md` | A stripped task list — nouns and verbs only, every item independently completable in ≤90 min | Any line contains "consider", "maybe", "as needed"; fewer than 5 items; a line doesn't start with a verb |
| **ponytail** | The moment a design decision has ≥2 defensible answers — mid-phase, whenever it happens | The decision + the constraints in `00-SPEC.md` | A decision-record stub (feeds an ADR or an `ENGINEERING-NOTES.md` paragraph) | Fewer than 2 rejected alternatives named, or a rejection with no reason given |
| **grill-me** *(optional on this project — see note below)* | End of phase, before opening the PR, if invoked | A plan/decision/diff you want stress-tested | An interactive round-by-round interview (real upstream behavior: `mattpocock/skills` → `productivity/grill-me`, which forwards to `grilling` — it interviews **the user**, question by question with a recommended answer, until the design tree is settled; it does **not** output automated `file:line` findings on its own) | N/A — not required for this project |

> **Correction, 2026-09-24:** this row previously read "grilled meat" and described an
> automated diff review producing ≥3 `file:line` findings. That was never what the real
> `grill-me`/`grilling` skill does — verified against its actual source
> (`github.com/mattpocock/skills`, `skills/productivity/grill-me` and `grilling`). The real
> skill is an interactive Socratic interview *with the user* about a plan or decision, not a
> diff scanner. Per project decision, `grill-me` is **not mandatory** for this assignment —
> use it only if you explicitly want to stress-test a design decision with the user present.
> The mandatory ≥3-findings-with-`file:line` pre-PR review described below stays required,
> but is a plain self/partner review step, not a named skill invocation.

**Rules that make this non-negotiable:**

1. **Do not skip `caveman` because you already know what the tasks are.** The artefact —
   the stripped task list — is what gets checked, not your mental model of it.
2. **Do not skip the pre-PR review because the diff is small or "obviously fine."** A diff
   that's actually fine still produces findings (timeouts to add, cleanup to verify) or,
   at minimum, an explicit statement that none were found and why that's credible for
   *this specific diff* — not a rubber stamp. This step is a review discipline, not a named
   skill invocation — see the correction above.
3. **Every skill invocation gets logged in `docs/AI-USAGE.md` at the moment it happens**,
   not reconstructed later from memory. Format:
   ```markdown
   ## <date> · <branch>
   - **Tool:** Claude Code + `<skill>`
   - **Shaped / Wrote:** <what it touched>
   - **I changed:** <what you overrode or rejected and why, citing a spec clause if one applies>
   ```
   The "I changed" line is mandatory even when you accepted the skill's output as-is —
   write "accepted as-is" rather than omitting the line. Specific disclosure carries no
   penalty; an undisclosed skill invocation is the thing that costs marks at viva.
4. **`ponytail` fires the moment the fork appears, not at end-of-phase cleanup.** If you
   notice mid-implementation that you're choosing between two designs, stop and invoke
   it there — do not keep coding and rationalize the choice afterward in the pre-PR review.
5. **PR review is run by the partner, never by you on your own PR.** Don't invoke it on
   your own diff and count that as satisfying Rubric A's review requirement — it doesn't.

## 7. Before you say a task is done

Run through this, out loud, not just in your head:

- [ ] Does this cross a layer boundary it shouldn't? (§3)
- [ ] Did I add anything to a metric label, log line, or response body that could be
      PII, a secret, or unbounded cardinality?
- [ ] Does every new triage failure path still return 201?
- [ ] Did I write a test that I confirmed would fail without the implementation?
- [ ] Did I touch `04-CONTRACTS.md`'s frozen surface without a `chore/contract-*` PR?
- [ ] Would this trip any row in the deduction ledger (§2)?
- [ ] Am I about to commit directly to `main`?
- [ ] Did `caveman` run at the start of this phase, `ponytail` at every design fork, and
      a pre-PR review (≥3 `file:line` findings or a credible "none found") before this PR —
      and is each one logged in `docs/AI-USAGE.md`?

If any answer is "yes" where it shouldn't be, fix it before reporting completion —
don't report it as done and mention the caveat afterward.
