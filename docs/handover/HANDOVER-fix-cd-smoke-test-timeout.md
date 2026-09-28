# HANDOVER — fix/cd-smoke-test-timeout

## 1. Position

| | |
|---|---|
| Branch | `fix/cd-smoke-test-timeout` |
| Base | `dev` @ `4266571` |
| Scope | Bound and clean up the CD Ingress smoke test |
| Incident | CD run `36402494560`, main @ `08a8a9b` |

## 2. Diagnosis

The run passed signature verification, Kind creation, ingress-nginx, VPA installation, manifest
apply, and the Postgres rollout. Its `smoke test through the Ingress` step remained active for more
than 30 minutes. GitHub did not expose partial logs while the step was running. The current code
has unbounded `curl` calls in both the readiness helper and the following API checks, so one stalled
HTTP response can explain the hang. The background port-forward also lacked explicit output
redirection and cleanup.

## 3. Change on this branch

- Add connect and total-request deadlines to `scripts/wait_for.sh` and each smoke-test request.
- Redirect and clean up the background port-forward; print its log if the smoke test fails.
- Document the timeout decision in `docs/ENGINEERING-NOTES.md` and this session in
  `docs/AI-USAGE.md`.
- Remove the stale VPA handover; its PR already merged.

## 4. Verification state

- Stuck CD run `36402494560` was cancelled after its smoke-test step had run for over 30 minutes.
- All earlier CD steps passed, including Postgres rollout. The exact blocked curl was not visible
  in the live runner logs.
- Local tests have not been run. CI and the next CD run must verify the fix after review/merge.

## 5. Next commands

```bash
bash -n scripts/wait_for.sh
git diff --check
```

Then push this branch, open a PR into `dev`, and get the required partner review. After the fix is
merged into `dev`, promote `dev` to `main` through the usual reviewed PR. Confirm the new CD run
passes the Ingress smoke test before marking deployment complete. Delete this handover in the final
merge commit.
