# ADR-0003 — Deploy by digest, tag by SHA

- **Status:** Accepted · 2026-09-26 · Phase 6 (`fix/close-disclosed-gaps`)
- **Deciders:** DEV-B (author, `k8s/`/`cd.yml` owner), DEV-A (review)
- **Satisfies:** `00-SPEC.md §638` (`cd.yml` with `needs:`-gated publish, images tagged by
  commit SHA — 4 marks) · `15-CICD.md §4.2` · CLAUDE.md deduction ledger (`:latest`
  deployment, −8; publish/deploy job not `needs:`-gated, −8)

## Context

`00-SPEC.md §3.4` asks the question that motivates this whole decision: *"'What is production
running?' must have a one-word answer you can paste into `git show`."* Three candidate
references exist for identifying a running container image, and they are not interchangeable:

| Reference | Mutable? | What it actually identifies |
|---|---|---|
| `:latest` | Yes, constantly — every push overwrites it | Nothing stable. **§5.3 −8 if ever deployed.** |
| `:${{ github.sha }}` | Yes, in principle — a tag can be force-re-pushed to point at a different image | A commit, by convention, as long as nobody re-pushes the tag |
| `@sha256:…` (digest) | **No** — content-addressed, cryptographically tied to the exact bytes | The exact artefact: base image, every layer, the build environment that produced it |

## Decision

**Push both `:${{ github.sha }}` and `:latest` to GHCR (§3.4 explicitly permits pushing
`latest` — it exists for a human doing a local `docker pull`, nothing more), but deploy by
**digest**, never by tag.** `cd.yml`'s `build-push` job captures each image's digest as a job
output (`steps.be.outputs.digest`); `deploy-k8s` uses `kustomize edit set image
...=...@sha256:...` to pin the prod overlay to that exact digest before applying it.

**Why digest and not the SHA tag, even though the SHA tag is already far better than
`:latest`:** a SHA tag is still a mutable reference — nothing stops a re-push (accidental or
malicious) from repointing `ghcr.io/.../civicpulse-backend:abc1234` at a different image while
the tag string stays the same. A digest is a hash of the actual bytes; it cannot be silently
repointed. Deploying by digest means "what is production running" has an answer stronger than
convention — it is a cryptographic fact, and it covers the base image and build environment
too, not just the application source.

**Corollary — `kustomize edit set image`, never `sed` on YAML.** `15-CICD.md §2` calls this out
directly: `kustomize edit set image` is schema-aware (it only ever touches the `image:` field of
matching container specs), where a `sed` substitution risks a false match anywhere the image
string happens to appear as a substring elsewhere in the manifest tree. This is also what makes
the `:latest` deduction structurally impossible rather than merely policy-forbidden — the
overlay's base `kustomization.yaml` never contains a literal tag for `kustomize edit` to leave
alone by mistake.

## `needs:` gating — why it is the four characters worth the most marks in the repo

`15-CICD.md §4.1`, verbatim: *"Without it you publish artifacts from code you already know is
broken."* GitHub Actions runs jobs in parallel by default. Without an explicit `needs:` edge:

- `build-push` would start at the same instant as `test`, so a broken commit on `main` still
  gets an image pushed to the registry under its own SHA.
- `deploy-k8s` would start at the same instant as `build-push`, so a partially-built or
  unpublished image could be deployed.

`cd.yml` gates both: `build-push` has `needs: test`, `deploy-k8s` has `needs: build-push`. This
is what makes "deploy by SHA/digest" a safety property and not merely a traceability one — SHA
tracing tells you *which* broken commit you deployed; `needs:` gating is what stops you
deploying a broken commit in the first place.

## Secrets handling

- **GHCR auth** uses `secrets.GITHUB_TOKEN` with `packages: write` — scoped to this repository,
  expires when the run ends, auto-rotated, revocable by GitHub — never a long-lived PAT.
  `15-CICD.md §4.3` calls this "the cleanest path" for exactly that reason.
- **`LLM_API_KEY`/`POSTGRES_PASSWORD`** live in GitHub repository secrets, injected only inside
  `deploy-k8s`'s own `kubectl create secret ... --dry-run=client -o yaml | kubectl apply -f -`
  step — never written to a file, never echoed, never present in `k8s/base/secret.yaml`
  (which ships `PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUES` only — CLAUDE.md HARD rule 1).
- **Never `echo` a secret.** GitHub Actions masks a known secret *value* in logs, but
  `base64`-ing or `jq`-transforming one first defeats that mask (the masked bytes no longer
  match). `kubectl create secret --dry-run=client -o yaml | kubectl apply -f -` never prints the
  secret to stdout at all — the YAML round-trips through `kubectl`'s own client-side dry-run
  without ever being logged.

## What `cd.yml` does NOT do (scope boundary, stated deliberately)

- It does not run against `dev` — only `main`, since `main` is the only branch this repo treats
  as deployable (every other branch is a feature branch or `dev`, which is pre-release).
  Deploying from `dev` pushes would defeat the entire "reviewed PR is the only path to a
  release" discipline CLAUDE.md HARD rule 2 exists to protect.
- It does not manage database migrations as a separate CD step — `k8s/base/backend-deployment.yaml`'s
  `migrate` initContainer already runs `alembic upgrade head` before the app container starts on
  every new pod (`05-DATA-LAYER.md §3.3`), so `cd.yml` doesn't need its own migration step; the
  rollout itself carries it.
- Cosign signing/verification is the explicitly-labelled bonus (+3) — the pipeline is fully
  correct and gated without it; the signature step is additive assurance, not the load-bearing
  safety property (that's the digest pin + `needs:` gating above).

## Rejected alternatives

- **Tag-only deploy (`:${{ github.sha }}`, no digest pin).** Rejected: strictly weaker than the
  digest approach for the same cost — the digest is already captured as a build-push output, so
  not using it to pin the deploy step gives up a stronger guarantee for free.
- **A single combined job** (build, push, and deploy in one `steps:` list, no job boundaries).
  Rejected: collapses the `needs:` safety property entirely — there would be nothing to gate a
  deploy step behind, since "did the tests pass" and "did the build succeed" would just be
  earlier steps in the same job with no way to express "stop here if this job's own tests were
  meant to run first," since a single job's own steps in this pipeline would need `ci.yml`
  reused as a separate job specifically to get that ordering guarantee.
- **Deploying straight from `docker build` output without pushing to a registry first**
  (`kind load docker-image`). Rejected: works for a local demo cluster but breaks the "what is
  production running" traceability goal entirely — nothing is addressable by SHA or digest if it
  was never published anywhere.
