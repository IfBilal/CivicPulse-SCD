## What
<!-- one paragraph, not a changelog -->

## Why
Closes #

## Spec clauses satisfied
<!-- cite 00-SPEC.md, e.g. §2.5 item 3, Rubric F line 3 -->

## Phase gate
- [ ] Gate checklist from 02-CRITICAL-PATH.md pasted below, all ticked

## Evidence
<!-- paths under docs/evidence/ added or updated by this PR -->

## Deduction armour
- [ ] no secret / key / `.env` in the diff (`make secret-scan`)
- [ ] no `localhost` for service-to-service (`make lint-localhost`)
- [ ] no `:latest` in anything deployed
- [ ] every publishing/deploying job still `needs:`-gated

## AI usage
- [ ] `docs/AI-USAGE.md` updated (§5.5)

## Reviewer
- [ ] **≥ 2 substantive comments with file:line** (Rubric A — "LGTM" scores zero)
