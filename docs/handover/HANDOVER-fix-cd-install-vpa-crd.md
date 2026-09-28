# HANDOVER — fix/cd-install-vpa-crd

## 1. Position

| | |
|---|---|
| Branch | `fix/cd-install-vpa-crd` |
| Base | `dev` @ `9d4c515` |
| Scope | Phase 8 CD deploy fix |
| Last failing run | `36399497619` (`main` @ `9b9266c`) |

## 2. Diagnosis

The latest CD logs confirm the ingress/kind change worked. The `ingress-nginx` step passed,
secrets were created, and the production overlay rendered. `kubectl apply` then failed because
the ephemeral kind cluster had no `VerticalPodAutoscaler` CRD:

```text
resource mapping not found for kind "VerticalPodAutoscaler"
in version "autoscaling.k8s.io/v1"; ensure CRDs are installed first
```

The prod overlay includes `k8s/base/vpa.yaml`, but CD did not install VPA before applying it.

## 3. Change on this branch

- Before applying app manifests, fetch the pinned official VPA 1.8.0 release and apply its VPA
  CRD, RBAC, and recommender deployment. Wait for the CRD and recommender to become ready.
- The app uses `updateMode: "Off"`; updater and admission webhook are unnecessary here.
- Replace the failure handler's civicpulse-only diagnostics with best-effort pod, event, ingress,
  VPA, and backend diagnostics across relevant namespaces.
- Record the diagnosis in `docs/AI-USAGE.md`.

## 4. Verification state

- `git diff --check`: passed.
- CI and CD have **not** run on this branch yet.
- Latest successful upstream steps: CD run `36399497619` passed ingress setup; app apply failed
  because the VPA CRD was missing.

## 5. Next commands

```bash
git diff --check
git add .github/workflows/cd.yml docs/AI-USAGE.md docs/handover/HANDOVER-fix-cd-install-vpa-crd.md
git commit -m "fix: install VPA before CD manifest apply"
git push -u origin fix/cd-install-vpa-crd
gh pr create --base dev --head fix/cd-install-vpa-crd \
  --title "fix: install VPA CRD before CD deployment" \
  --body "CD run 36399497619 passed ingress setup but failed applying backend-vpa because the ephemeral kind cluster lacked the VPA CRD. This installs the pinned official CRD/RBAC/recommender before applying prod manifests and makes failure diagnostics cover the relevant namespaces."
```

After partner review and merge to `dev`, promote `dev` to `main` through the required reviewed
PR. `cd` runs only on pushes to `main`; I5 is complete only after deploy, rollouts and the Ingress
smoke test pass. Delete this handover in the final merge commit.
