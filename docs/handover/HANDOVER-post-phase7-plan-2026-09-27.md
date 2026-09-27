# HANDOVER — post-Phase-7 plan, as directed by Taimoor, 2026-09-27

<!-- Written at the user's explicit request to document a verbal plan before executing it.
     This is a working plan snapshot, not a rubric-traceability update — that lives in
     20-RUBRIC-TRACEABILITY.md and gets updated as each item actually closes. -->

## 0. Context: what triggered this note

PR #58 (Phase 7: HPA load capture, VPA loop, zero-downtime rollout proof) merged into `dev` at
`6a97c7c` on 2026-09-27. Immediately after confirming the merge, the user gave the following
instructions verbally, in one message, which this document breaks down and makes actionable:

> "It's merged check it now and let's proceed to the phase 7 loose ends and in leaving no minute
> detail let's do those complete those then do A5 uh, forget the A3 and A4 for now and like I
> believe A5 has also been done and documented move to phase 8 and to end and yeah and is the
> demo video a bonus as well as tell me besides the demo video what are the bonuses that I can be
> able to do and document all of this shit that I've just said right now"

## 1. Merge verified

`git fetch origin` + `gh pr view 58 --json state,mergedAt` confirmed: **MERGED**, `2026-09-27T14:50:28Z`,
now `dev`'s tip at commit `6a97c7c`.

## 2. Correction: A5 is NOT done

The user's belief ("I believe A5 has also been done and documented") was checked against the
actual repo state and is **incorrect** — flagging this explicitly rather than silently proceeding
on a wrong premise:

- No `feat/deliberate-conflict-a` / `-b` branches exist (`git branch -a` checked).
- No `docs/evidence/merge-conflict-markers.txt`, `-raw.py`, `-graph.txt`, or `merge-conflict.md`
  exist.
- `docs/20-RUBRIC-TRACEABILITY.md`'s A5 row is still `☐`, with its own text explaining exactly
  why: this needs **two humans, independently branching from the same `dev` SHA, at the same
  time** — a single Claude Code session producing this alone would fabricate the exact
  collaborative exercise the rubric is testing, which a prior session (correctly) declined to do.

**Per the user's own "forget A3 and A4 for now" instruction, A5 is being treated the same way
here: deferred, not attempted solo.** It needs both partners in one sitting — see
`docs/handover/HANDOVER-to-ifbilal-phases-0-6-close-and-next-steps.md §2` for the exact commands,
already written and ready to run whenever both of you are free (budget 30-45 minutes).

## 3. Corrected fact: the demo video (J4) is not a bonus

Checked `docs/20-RUBRIC-TRACEABILITY.md` §J directly. **J4 is a required row in section J
(Documentation, portfolio, reflection — 15 marks total), worth 3 marks on its own**, not part of
the capped Bonus pool. Requirement: video ≤5 min, **both partners speaking**, six required beats
(`18-DOCS-EVIDENCE-VIVA.md §7`). Status: `☐ — not attempted, requires the two human contributors`.
This cannot be done solo, same as A5/A3/A4.

## 4. The actual Bonus section (capped +15) — what's left after this session

| Item | Marks | Status | Solo-doable? |
|---|---|---|---|
| Zero-downtime rollout, zero failed requests | +4 | ☑ closed (PR #58, this session) | — |
| GitOps (Argo CD / Flux) reconciling from the repo | +4 | ☐ | Yes |
| Digest deploy + Cosign sign **and** verify in CI | +3 | ☐ | Yes |
| Prometheus scraping `/metrics` + Grafana dashboard | +2 | ☐ | Yes |
| OpenTelemetry tracing frontend → backend → LLM | +2 | ☐ | Yes |

The doc's own cut-order (if time runs out, cut in this order): OTel first, then Grafana, then
Cosign, then GitOps — meaning GitOps and Cosign are the ones worth doing first if only some of
the four get done, since they're the last to be cut, not the first.

## 5. The plan, as agreed

1. **Phase 7 loose ends** — close out completely, no detail skipped:
   - `docs/ENGINEERING-NOTES.md` Q5's disclosed `readyReplicas`-vs-HPA-desired-replicas
     discrepancy: resolve or tighten the note so it isn't left as an open caveat.
   - Any other Gate 7 checklist item not already ticked off by PR #58 — re-audit
     `14-LOAD-AUTOSCALING.md §8`'s Gate 7 checklist line by line against what actually exists now
     that `dev` has the merged evidence.
2. **A5 — deferred**, per the correction in §2 above. Not attempted solo. Flagged to the user as
   still needing a joint session.
3. **A3/A4 — deferred**, per explicit user instruction ("forget the A3 and A4 for now").
4. **Move to Phase 8** (CD/rollback) once Phase 7 loose ends are closed.
5. **Demo video (J4)** — flagged as not a bonus, needs both partners; not attempted solo.
6. **Bonus items** — GitOps, Cosign, Prometheus/Grafana, OpenTelemetry are all candidates for
   solo work once Phase 8 is underway or done, time permitting.

## 6. Mandatory skill-invocation note

Per `CLAUDE.md §6`, starting Phase 8 requires a fresh `caveman` pass against
`02-CRITICAL-PATH.md`'s Phase 8 section before writing any code, logged in `docs/AI-USAGE.md` the
moment it happens — not assumed from this document's plan.
