# Submission package — `00-SPEC.md §5.8`

The six items the brief asks for at submission time, assembled here so nothing has to be
hunted down again. Update item 4 once the video exists; everything else below is real,
live, and verified against the actual repository — not placeholders.

1. **GitHub repository URL**
   https://github.com/IfBilal/CivicPulse-SCD

2. **Link to a successful `cd.yml` run** that tested, published, and deployed
   https://github.com/IfBilal/CivicPulse-SCD/actions/runs/36543968481
   (commit `d39b298`, 2026-09-29 — latest green run on `main` as of this file)

3. **Link to both images in GHCR, showing SHA tags**
   - Backend: https://github.com/ifbilal/civicpulse-scd/pkgs/container/civicpulse-backend
   - Frontend: https://github.com/ifbilal/civicpulse-scd/pkgs/container/civicpulse-frontend

   Verified live via GHCR's own anonymous pull-token flow (no GitHub auth needed —
   these are public images), 2026-09-29. Both repositories carry real commit-SHA tags,
   each paired with a Cosign `.sig` tag proving the image was actually signed, not just
   pushed:

   ```
   civicpulse-backend tags (excerpt): f5f893d..., f89f396..., 9b9266c..., 08a8a9b...,
     1c12c34..., c424edb..., c1d5d7d..., 2b90a09..., d39b298..., 15461c6...
     + one sha256-<digest>.sig tag per image digest above
   civicpulse-frontend tags: same SHA set, same sig-tag pairing
   ```

   Reproduce this check yourself any time, no `gh` scopes or login required:
   ```bash
   for repo in civicpulse-backend civicpulse-frontend; do
     TOKEN=$(curl -s "https://ghcr.io/token?scope=repository:ifbilal/${repo}:pull" \
       | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
     curl -s -H "Authorization: Bearer $TOKEN" \
       "https://ghcr.io/v2/ifbilal/${repo}/tags/list"
   done
   ```

4. **Demo video link (unlisted)**
   _Not yet recorded — the one remaining item in this checklist. ≤5 min, both partners
   speaking, six required beats per `18-DOCS-EVIDENCE-VIVA.md §7`. Paste the unlisted
   link here once uploaded._

5. **`git shortlog -sn` output, pasted**
   See `docs/evidence/shortlog.txt` for the full raw output and identity-merged analysis.
   Headline number, `git shortlog -sn --no-merges HEAD` on `dev`, identities merged:
   Taimoor Shaukat/T361 = 67, IfBilal/8BitNinja = 38 — min share 38/105 = **36.2%,
   clears the 35% floor**. (`main` currently shows 29.7% pending the promotion PR that
   carries these same commits across — will match once merged.)

6. **`kubectl get hpa -w` capture and replicas-vs-load chart**
   - `docs/evidence/hpa-watch.txt` — real capture, replicas climbing 2→3→5→7→10 as CPU
     load rises during the `k6` ramp test
   - `docs/evidence/hpa-replicas-vs-load.png` — the corresponding chart
   - Full measured analysis (lag, per-term breakdown): `docs/ENGINEERING-NOTES.md` §Q5

---

Before submitting, from the repository root: `python scripts/check_submission.py` —
lint, not a grader; a clean run doesn't guarantee a good mark, a dirty run nearly
guarantees a bad one.
