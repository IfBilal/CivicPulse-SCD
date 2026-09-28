# HANDOVER — fix/cd-backend-fqdn

<!-- Delete this file in the PR merge commit. -->

## 1. Position

| | |
|---|---|
| Branch | `fix/cd-backend-fqdn` |
| Base | `dev` @ `9ef80e5` |
| Scope | Fix the remaining CD Ingress smoke-test 502 |
| Evidence | CD run `36410195951`, main @ `1c12c34` |

## 2. Diagnosis

The deploy passed cluster creation, ingress-nginx, VPA setup, manifest apply, and Postgres
rollout. The `/api/stats` smoke check then reached its 90-second deadline with HTTP 502. Nginx
logged `backend could not be resolved (2: Server failure)`, and its startup log showed
`upstream=backend:8000`. Nginx's asynchronous resolver does not apply Kubernetes pod DNS search
domains. `docs/ENGINEERING-NOTES.md` already said Kubernetes must provide the backend FQDN, but the
frontend Deployment left `BACKEND_UPSTREAM` unset, so it used the short name.

Backend init containers also retried migrations while Postgres was starting. The current migration
eventually completed successfully; the steady `/api/stats` 502 was caused by the short DNS name.

## 3. Change on this branch

- The Kubernetes frontend Deployment sets
  `BACKEND_UPSTREAM=backend.civicpulse.svc.cluster.local:8000`.
- The deployment comment, Kubernetes guide, and engineering decision now agree with the runtime
  requirement.
- `dev` already contains the bounded smoke-test deadlines and diagnostic logging from PRs #78/#79.

## 4. Verification state

- CD run `36410195951`: all CI, image build/sign, cluster setup, ingress, VPA, manifest apply, and
  Postgres rollout passed; smoke test failed with HTTP 502 due to the unresolved short name.
- `git diff --check` passed after the FQDN change.
- PR CI and the next `main` CD run remain pending.

## 5. Next steps

```bash
git diff --check
```

After review and merge to `dev`, promote `dev` to `main`. Confirm the nginx startup log shows the
fully qualified upstream and that `/api/stats`, POST complaint, and GET complaint smoke checks all
pass. Delete this handover in the final merge commit.
