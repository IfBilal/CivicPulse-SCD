# AI Usage Log

Every Claude Code skill invocation on this project, logged at the moment it happens
(`01-WORKFLOW.md §4`, `CLAUDE.md §6`).

---

## 2026-09-23 · chore/be-pyproject-bootstrap

- **Tool:** Claude Code + `caveman`
- **Shaped:** decomposition of DEV-A's remaining Phase 0 slice (per
  `docs/handover/HANDOVER-phase0-devb-to-deva.md`) into a stripped task list: create
  `backend/pyproject.toml` verbatim from `03-REPO-BOOTSTRAP.md §4`, minimal `backend/app/`
  and `backend/tests/` scaffold, replace root `Makefile` with the full `§5` version, verify.
- **Wrote:** none (planning only)
- **I changed:** nothing — accepted the task list as-is. Added one clarification not in the
  skill's output: `make check`'s `frontend`-dependent sub-targets (`lint`, `type`, `test-fe`)
  are known-red until DEV-B's Phase 2b FE scaffold lands, and that's out of scope for this
  slice — noted in the PR body rather than silently treated as a blocker.

## 2026-09-23 · chore/be-pyproject-bootstrap

- **Tool:** Claude Code + `ponytail`
- **Shaped:** the Makefile-merge decision (replace root `Makefile` wholesale with
  `03-REPO-BOOTSTRAP.md §5`'s verbatim text vs. manually splicing new targets into DEV-B's
  Phase-0-partial stub while preserving its header comment).
- **Wrote:** none (decision only)
- **I changed:** accepted the recommendation as-is (wholesale replace). Rejected alternatives
  it named: (1) manual splice — risks transcription drift from the frozen §5 source with no
  benefit, since §5 is already canonical; (2) keeping DEV-B's stale header comment — it
  describes a "backend doesn't exist yet" state that this PR itself ends, so retaining it
  would misinform the next reader of the file.

## 2026-09-23 · chore/be-pyproject-bootstrap

- **Tool:** Claude Code (manual hardening pass — the `grilled meat` skill is referenced by
  `CLAUDE.md §6` and `01-WORKFLOW.md §4` but is not present in this session's installed
  skill set; ran the same end-of-phase diff review manually instead of skipping it)
- **Shaped:** review of the full diff (`Makefile`, `backend/pyproject.toml`,
  `backend/app/__init__.py`, `backend/tests/__init__.py`) before opening the PR.
- **Findings:**
  1. `Makefile` `test-be` target will fail today (0% coverage vs. the 65% floor in
     `backend/pyproject.toml`'s `--cov-fail-under=65`) — no tests exist yet. **WONTFIX for
     this PR**: expected until Phase 2/3 add real backend tests; documented in the PR body,
     not silently left unexplained.
  2. `Makefile` `openapi`/`migrate`/`seed` targets reference `app.cli.openapi_dump` /
     `app.cli.seed`, neither of which exist yet. **WONTFIX for this PR**: those modules are
     Phase 2/3 scope per the directory layout in `03-REPO-BOOTSTRAP.md §1`; adding them now
     is scope creep outside the declared Phase 0 slice.
  3. Verified `openai==1.54.*` sits correctly under `[project.dependencies]` (runtime), not
     `[project.optional-dependencies].dev` — needed at runtime by the later LLM triage
     provider, not just in tests. No change needed; flagged so a future edit doesn't
     "helpfully" move it into dev extras and break the production container's `make up`.
  4. `backend/tests/` has no `conftest.py` and no `unit/integration/contract` subdirs yet —
     markers are pre-registered in `pyproject.toml` (`markers = [...]`) so `--strict-markers`
     won't reject Phase 2+ test files, but the fixtures they'll need don't exist yet.
     **WONTFIX for this PR**: Phase 2+ scope, noted so the next window doesn't assume
     `conftest.py` fixtures are already wired.
- **I changed:** N/A — this is the finding-generation step itself, not a review of another
  tool's output.

## 2026-09-23 · chore/scripts-check-submission

- **Tool:** Claude Code + `ponytail`
- **Shaped:** the SKIP/PASS/FAIL/WARN state-machine and exit-code contract for
  `scripts/check_submission.py` when a check's prerequisite files don't exist yet (Phase 0,
  before frontend/k8s/compose/tests/ADRs land).
- **Wrote:** none (decision only)
- **I changed:** accepted the recommendation as-is (SKIP doesn't block exit 0, only FAIL does;
  no `--strict` flag added speculatively). Rejected alternatives it named: (1) SKIP counts as
  FAIL until the prerequisite lands — rejected, makes the script useless as a signal until
  Phase 8; (2) three-tier exit codes (0/1/2 for clean/warn/fail) — rejected, nothing downstream
  branches on exit-code granularity beyond zero-vs-nonzero.
- **Note:** `caveman` was not invoked for this task's initial decomposition — this entry
  reflects that honestly rather than reconstruct one after the fact, per `CLAUDE.md §6` rule 3
  ("logged at the moment it happens, not reconstructed later").

## 2026-09-23 · chore/scripts-check-submission

- **Tool:** Claude Code (manual hardening pass — the `grilled meat` skill is referenced by
  `CLAUDE.md §6` and `01-WORKFLOW.md §4` but is not present in this session's installed skill
  set, same gap noted in the prior PR's log entry; ran the equivalent review manually)
- **Shaped:** review of `scripts/check_submission.py` before opening the PR.
- **Findings:**
  1. `net_localhost()` relied on `grep`'s exit code 2 to mean "some target path missing," but
     with a mixed existing/missing path list `grep` also returns 2 even when a real match
     exists among the paths that *do* exist — silently masking a genuine `NET-LOCALHOST`
     violation in `backend/app` once it has real content but `compose.yaml`/`k8s/` still don't
     exist. **Fixed**: now checks only existing target paths explicitly and reports which ones
     were skipped, rather than trusting grep's combined exit code.
  2. `run()` only caught `FileNotFoundError`; a hung external tool (`gitleaks`, `kubectl`) with
     no timeout would crash the whole 18-check run over one flaky call. **Fixed**: added a 30s
     timeout and a `TimeoutExpired` handler that degrades that one check to a non-fatal state
     instead of killing the script.
  3. `rubric_seed()` always returns SKIP unconditionally, regardless of `seed.py`'s existence —
     structurally incapable of ever reporting PASS or FAIL. **WONTFIX**: the real check (`run
     seed twice against a throwaway DB, assert equal counts ≥ 30`) needs a live DB connection
     this static script deliberately doesn't stand up; correctly deferred to `make seed` +
     manual verification at Gate 2, not silently dropped — noted here so it isn't mistaken for
     an oversight.
  4. Found and documented separately (`docs/ENGINEERING-NOTES.md`): `03-REPO-BOOTSTRAP.md §5`'s
     Makefile line `submission-check: ; python scripts/check_submission.py` fails on this
     machine (`python: command not found`, only `python3` is on `PATH`). Not fixed in this PR's
     diff since it means touching the frozen bootstrap Makefile content again — flagged per
     `CLAUDE.md §0`'s rule that an implementation-doc bug should be said out loud, not quietly
     reconciled, and left for a joint decision.
- **I changed:** N/A — finding-generation step, not a review of another tool's output.

## 2026-09-23 · fix/gate0-make-check

- **Tool:** Claude Code (manual verification pass, no skill invoked for the investigation
  itself — this was re-checking a Gate 0 checklist item against the live repo, not a new
  phase or a design fork)
- **Shaped:** ran the actual Gate 0 checklist (`02-CRITICAL-PATH.md` Phase 0 gate) against
  the repo instead of trusting the prior session's log entries. Created a real venv and ran
  `pip install -e ".[dev]"` to verify "`make check` exits 0 on a clean clone" for real.
- **Findings:**
  1. `backend/pyproject.toml` had no `[build-system]` table and no `version` key under
     `[project]`. `pip install -e ".[dev]"` failed immediately with a PEP 621 validation
     error (`project must contain ['version']`) — nobody could actually run `make check`
     from a clean clone, contradicting the Gate 0 checkbox. **Fixed**: added
     `[build-system]` (setuptools>=68) and `version = "0.1.0"`. Verified: install now
     succeeds; `ruff check .`, `ruff format --check .`, and `mypy app` all pass clean.
  2. `Makefile`'s `lint`/`type`/`test-fe` targets unconditionally `cd frontend`, but
     `frontend/` doesn't exist yet (correctly — it's Phase 2b scope, not Phase 0). This
     made `make check` fail even after fix #1, on a directory that legitimately isn't
     built yet. Asked the user via AskUserQuestion whether to guard the Makefile now or
     leave Gate 0 formally blocked-pending-Phase-2b; user chose to guard now. **Fixed**:
     `lint`, `type`, `test-fe` now `test -d frontend` first and print a skip message
     instead of failing when it's absent.
  3. `pytest` still fails `make check`'s `test-be` step via `--cov-fail-under=65` in
     `backend/pyproject.toml`, because `backend/app/` is intentionally empty at Phase 0
     (app code is Phase 2/3 scope) and zero tests exist yet. **WONTFIX for this branch**:
     this is the coverage floor correctly doing its job on an empty app, not a bootstrap
     defect — touching the floor now would mask a real signal later. Will clear itself
     once Phase 2/3 land real code and tests.
  4. `gitleaks` (the `secret-scan` target) isn't installed in this sandbox, so it can't be
     verified here. Not a repo defect — `docs/evidence/precommit-secret-block.txt` already
     documents a real blocked run in a proper dev environment. Noted so this isn't
     mistaken for a fourth code bug.
  5. Found and cleaned up: `pip install -e` generated `backend/civicpulse_backend.egg-info/`,
     which wasn't gitignored. Added `*.egg-info/` to root `.gitignore` and deleted the
     stray directory before staging anything, so it never entered history.
- **I changed:** the Makefile-guard approach per the user's explicit choice (see finding 2)
  — this is disclosed as a user decision, not an autonomous one, per `CLAUDE.md §6` rule 4
  (ponytail-equivalent fork surfaced immediately, not rationalized after the fact).

## 2026-09-23 · feat/contract-freeze

- **Tool:** Claude Code + `caveman` (start of Phase 1, before any code)
- **Shaped / Wrote:** stripped task list for Phase 1 from `02-CRITICAL-PATH.md §4` PHASE 1 +
  `04-CONTRACTS.md` + `00-SPEC.md §2.2/§2.3/§2.5/App. A`:
  1. Write `backend/app/domain/enums.py` — four `StrEnum`s, A4 superset on `TriagedBy`.
  2. Write `backend/app/domain/limits.py` — every field bound as a named constant.
  3. Write `backend/app/domain/transitions.py` — `TRANSITIONS` dict, `TERMINAL`, `is_allowed`.
  4. Write `backend/app/schemas/` — complaint, page, stats, meta, health, error envelope, triage.
  5. Write the app factory + route signatures for all endpoints, stable `operation_id`s, every status code declared.
  6. Register the validation handler — 422 → 400 field-level envelope; bad path UUID → 404.
  7. Strip 422 from the generated OpenAPI; set `servers: [{"url": "/"}]`.
  8. Write `app/cli/openapi_dump.py` — dump sorted JSON, no server.
  9. Fix Makefile `python` → `python3` (`submission-check`, `openapi`).
  10. Pin `openapi-typescript` in a minimal `frontend/package.json` + lockfile; generate `schema.d.ts`.
  11. Write unit tests — 16-cell transition matrix, enum values vs spec.
  12. Write contract tests — operation ids golden list, relative servers, no 422, declared codes, 400/404 envelopes.
  13. Add CI job — contract tests + `make gen-client` + `git diff --exit-code`.
  14. Run `grilled meat` on the diff; fix or WONTFIX each finding.
  15. Write handover for DEV-A; open the PR into `dev`, both approve.
- **I changed:** accepted as-is. Session driven by DEV-B (IfBilal) with Claude Code building
  the joint branch end-to-end; DEV-A (T361) reviews and co-signs per `04-CONTRACTS.md` header.
