# HANDOVER — fix/cd-smoke-test-diagnostics

## 1. Position

| | |
|---|---|
| Branch | `fix/cd-smoke-test-diagnostics` |
| Base | `dev` @ `c81ade3` |
| Scope | Expose the failing CD Ingress upstream response |
| Incident | CD run `36402494560`, main @ `08a8a9b` |

## 2. Diagnosis

The run passed signature verification, Kind creation, ingress-nginx, VPA installation, manifest
apply, and all rollouts. After cancellation, logs showed a `/api/stats` request every 31 seconds.
Frontend nginx has `proxy_read_timeout 30s`, but `wait_for.sh` counted each failed attempt as only
one second, so a nominal 90-second timeout could run about 45 minutes. The final nginx/backend
error and HTTP status were not captured before cancellation, so the failing upstream path remains
unconfirmed.

## 3. Change on this branch

- PR #78 added request deadlines and port-forward cleanup.
- This follow-up reports the last HTTP status and includes frontend logs in failure diagnostics.
- Record the confirmed timeout-loop cause and remaining upstream diagnosis in project notes.

## 4. Verification state

- Stuck CD run `36402494560` was cancelled after its smoke-test step had run for over 30 minutes.
- PR #78 merged to `dev`; its CI passed.
- The blocked call was `/api/stats`; the last HTTP status and nginx/backend error were not recorded.
- `bash -n scripts/wait_for.sh` and `git diff --check` passed on PR #78. No local tests were run.

## 5. Next commands

```bash
bash -n scripts/wait_for.sh
git diff --check
```

Push this branch and open a PR into `dev`. After the diagnostics merge, promote `dev` to `main`
through the usual reviewed PR. Use the HTTP status and frontend/backend logs from the next bounded
CD run to fix `/api/stats` if it still fails. Delete this handover in the final merge commit.
