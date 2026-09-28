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
`wait_for.sh` counted each failed attempt as only one second, stretching its nominal 90-second
timeout to about 45 minutes. Static inspection found the frontend's default-deny egress policy
omitted both CoreDNS and backend access, although nginx dynamically resolves `backend:8000`. This
breaks `/api` on policy-enforcing CNIs. The ephemeral CI Kind cluster uses kindnet, which does not
enforce NetworkPolicies, so that policy gap alone may not explain this run; the exact upstream
failure still needs its HTTP status and nginx/backend logs from the next bounded run.

## 3. Change on this branch

- PR #78 added request deadlines and port-forward cleanup.
- This follow-up adds narrow frontend egress to DNS/backend, matching backend ingress, and a
  five-second nginx DNS resolver timeout.
- It reports the last HTTP status and includes frontend logs in failure diagnostics.
- The remaining verification is the next real CD run on `main`.

## 4. Verification state

- Stuck CD run `36402494560` was cancelled after its smoke-test step had run for over 30 minutes.
- PR #78 merged to `dev`; its CI passed.
- The blocked call was `/api/stats`; the last HTTP status and nginx/backend error were not recorded.
- The frontend NetworkPolicy omission is fixed for enforcing CNIs, but the exact error in the
  kindnet CI cluster still needs confirmation.
- `bash -n scripts/wait_for.sh` and `git diff --check` passed on PR #78. No local tests were run.

## 5. Next commands

```bash
bash -n scripts/wait_for.sh
git diff --check
```

After this PR passes review and merges into `dev`, promote `dev` to `main` through the usual
reviewed PR. Use the HTTP status and frontend/backend logs from the next bounded CD run to confirm
the `/api/stats` path; fix any remaining kindnet-specific fault before marking Gate 8 green. Delete
this handover in the final merge commit.
