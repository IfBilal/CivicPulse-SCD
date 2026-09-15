# CivicPulse — Implementation Package

**24 documents.** Everything needed to build CS4032 Assignment 01 end to end, as two developers
working in parallel Claude Code windows.

`00-SPEC.md` is the single source of truth. Every other file cites it. Where an implementation doc
disagrees with `00-SPEC.md`, the spec wins and the implementation doc is a bug.

---

## Read in this order

### Before you write any code (Day 0 – Day 2, both developers)

| File | What it gives you | Read when |
|---|---|---|
| **`00-SPEC.md`** | The full assignment converted to markdown, plus **Appendix A: 14 contradictions** in the brief with our default resolution for each | Day 0, aloud, together |
| **`22-PRD.md`** | Personas, 5 user stories with testable acceptance criteria, 16 functional + 16 non-functional requirements, success metrics, 10 risks, release plan | Day 0 |
| **`21-ARCHITECTURE-DIAGRAMS.md`** | 10 Mermaid diagrams — context, networks, components, request sequence, **the fallback ladder**, state machine, k8s, pipeline, observability, Gantt | Day 0 |
| **`02-CRITICAL-PATH.md`** | The 12-node critical path, float analysis, **8 phase gates with binary checklists**, the 14-day two-window schedule, collision matrix, marks-per-hour triage | Day 0 |
| **`01-WORKFLOW.md`** | Ownership split, branch model, commit convention, PR protocol, the **scheduled merge-conflict drill**, worktrees, **caveman / ponytail / grilled-meat / PR-review invocation slots**, emergency procedures | Day 0 |
| **`03-REPO-BOOTSTRAP.md`** | Directory layout, `.gitignore`, `.env.example`, `pyproject.toml`, the full `Makefile`, pre-commit, gitleaks, `check_submission.py` as an 18-check table, **the exact branch-protection clicks** | Day 1 |
| **`04-CONTRACTS.md`** | **FROZEN at Gate 1.** Ten endpoints, enums, validation rules, 16-cell transition table, header contract, error envelopes, Pydantic models, the typed-client drift gate | Day 2 AM, together, one PR |

### Implementation (Day 2 – Day 12, parallel)

| File | Owner | Rubric | Phase |
|---|---|---|---|
| `05-DATA-LAYER.md` | DEV-A | D (12) | P2 |
| `23-ERD-DATA-DICTIONARY.md` | DEV-A | D | P2 |
| `06-BACKEND-CORE.md` | DEV-A | C (11 of 25) | P3 |
| `07-BACKEND-API.md` | DEV-A | C (10 of 25) | P3 |
| `08-AI-TRIAGE.md` | DEV-A | **F (25)** | P4 |
| `09-CACHE-RATELIMIT.md` | DEV-A | E (10) | P5 |
| `10-OBSERVABILITY.md` | DEV-A | C, F6, bonus | P6d |
| `11-FRONTEND.md` | DEV-B | B (18) | P2b, P4b |
| `12-DOCKER-COMPOSE.md` | DEV-B | G (15) | P3b |
| `13-KUBERNETES.md` | DEV-B | H (13 of 20) | P6b |
| `14-LOAD-AUTOSCALING.md` | both ⏱ | H (7 of 20) + bonus | P7 |
| `15-CICD.md` | DEV-B | I (20) | P6a, P8a |

### Cross-cutting (continuous)

| File | Purpose |
|---|---|
| `16-TESTING.md` | The consolidated matrix — **121 backend tests, 11 frontend**, fixtures, testcontainers, failure-injection catalogue, anti-flake rules |
| `17-SECURITY-SECRETS.md` | All 11 §5.3 deductions with guard + detector, the secret-exposure incident runbook, **ADR-0004 in full**, supply chain, runtime hardening |
| `19-HANDOVER-TEMPLATE.md` | The `HANDOVER-<branch>.md` template, three variants, the live board |
| `18-DOCS-EVIDENCE-VIVA.md` | README structure, the four ADRs, RUNBOOK, the eight §5.2 answers, **the 32-file evidence manifest**, the ≤5-min video script, the viva question bank |
| `20-RUBRIC-TRACEABILITY.md` | **Every rubric line → file → test → artefact → status.** The sheet you keep open in the viva |

---

## The five things that matter most

1. **The fallback test.** §2.5: *"Write this test if you write no other: given a provider that always
   raises, `POST /api/complaints` still returns 201 and `triaged_by == 'rules:fallback'`."*
   → `08-AI-TRIAGE.md §5.2`, test **F1**.
2. **Deduction armour beats features.** The eleven §5.3 violations total **−101**. Every one has a
   guard *and* an automated detector → `17-SECURITY-SECRETS.md §1`, `20-RUBRIC-TRACEABILITY.md`.
3. **Freeze the contract on Day 2.** It is the fan-out point; nothing parallelises before it
   → `04-CONTRACTS.md`.
4. **Start the wall-clock items on Day 0.** Keys, k3d, metrics-server, VPA, the HPA capture, the
   video. These cannot be compressed by working harder → `02-CRITICAL-PATH.md §3`.
5. **The viva multiplies the team mark** (1.0 / 0.75 / 0.5 / 0.0) and examines you on **your
   partner's** code. Cross-review and the two scheduled ownership swaps are not courtesy
   → `01-WORKFLOW.md §1`, `18-DOCS-EVIDENCE-VIVA.md §8`.

## If you fall behind

§5.1's order: **F (AI) > C (backend) > I (CI/CD) > H (Kubernetes)**.
Cut order for bonuses: OTel → Grafana → GitOps → Cosign → VPA second run → frontend polish.
**Never cut the fallback test.**

---

## Conventions used throughout

- `§x.y` refers to a section of `00-SPEC.md`.
- `A1`–`A14` are the contradictions in `00-SPEC.md` Appendix A.
- Test IDs: `C-*` backend core/state machine, `D*` data, `E*` cache, `F*` AI, `FE-*` frontend.
- Gate checklists are **binary**. A phase is not done until its gate passes.
- ⏱ marks work that is wall-clock-bound rather than effort-bound.
