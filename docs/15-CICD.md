# 15 — CI/CD (GitHub Actions · GHCR · 20 marks + bonus)

> **Owner:** DEV-B · **Days:** 7–8 (CI), 11–12 (CD) · **Gates:** Gate 5, Gate 8 · **Rubric:** I (20)
> **Four §5.3 deductions live in this file** — `needs:` gating (−8), deploying `:latest` (−8),
> secrets in workflows (−20), and, indirectly, the quickstart (−5). That is **−36 of exposure**,
> more than the section is worth in marks. Treat the deduction armour as the primary deliverable.

---

## 1. Design rules that apply to every workflow

| Rule | Implementation | Spec |
|---|---|---|
| Least privilege | `permissions: {contents: read}` at workflow level; widen **per job**, never globally | §3.4 *"least-privilege `permissions:` block on every workflow"* |
| Pinned actions | `@v4` minimum; **commit SHA** for the bonus | §3.4 |
| No publishing from a PR | `build` job has no registry credentials at all | §3.4 *"A PR must not publish artifacts"* |
| `needs:` on every publish/deploy job | enforced by `scripts/check_submission.py::CI-NEEDS` | §5.3 −8 |
| Immutable deploy reference | `${{ github.sha }}` tag, or digest for the bonus | §5.3 −8 |
| Cancel superseded runs | `concurrency` group per ref | cost + feedback speed |
| Deterministic tests | `TRIAGE_PROVIDER=simulated` everywhere | §2.5 *Determinism* |
| Job names are load-bearing | branch protection references them by exact string | Rubric I line 1 |

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}   # never cancel a main deploy
```

> `cancel-in-progress: false` on `main` matters: cancelling a half-finished `deploy-k8s` leaves the
> cluster mid-rollout with no record of why. Cancel PRs freely; never cancel a deployment.

---

## 2. Required-checks wiring (Rubric I line 1 — *"configured as required checks"*)

The seven `ci.yml` job names go verbatim into branch protection
(`03-REPO-BOOTSTRAP.md §9`): `lint-and-type`, `test-backend`, `test-frontend`, `build`, `scan`,
`manifests`, `integration`.

**Two traps:**
1. A check can only be *selected* in the UI after it has run at least once. Push a throwaway PR
   first, then configure, then screenshot.
2. **Renaming a job silently disables its required check.** Protection keeps requiring the old name,
   which never reports, so PRs hang on "Expected — Waiting for status". If you rename, re-select.

---

## 3. `ci.yml` — on PR to `main`, on push to `dev`

```yaml
name: ci
on:
  pull_request: {branches: [main]}
  push:         {branches: [dev]}
permissions: {contents: read}
concurrency: {group: ci-${{ github.ref }}, cancel-in-progress: true}

env:
  PYTHON_VERSION: "3.12"
  NODE_VERSION: "22"
  TRIAGE_PROVIDER: simulated        # §2.5 — CI is pinned to the deterministic provider
```

### 3.1 `lint-and-type`

```yaml
  lint-and-type:
    runs-on: ubuntu-24.04            # pinned, not ubuntu-latest — §5.2 q1 is about frozen versions
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "${{ env.PYTHON_VERSION }}", cache: pip}
      - run: pip install -e "backend[dev]"
      - run: cd backend && ruff check --output-format=github .
      - run: cd backend && ruff format --check .
      - run: cd backend && mypy app
      - run: make lint-layers          # §05 5 — SQL out of routes, no upward imports
      - run: make lint-localhost       # §5.3 −8 armour
      - uses: actions/setup-node@v4
        with: {node-version: "${{ env.NODE_VERSION }}", cache: npm, cache-dependency-path: frontend/package-lock.json}
      - run: cd frontend && npm ci
      - run: cd frontend && npm run lint
      - run: cd frontend && npx tsc --noEmit
      - name: OpenAPI client drift gate            # §04 8 · §11 4
        run: |
          make gen-client
          git diff --exit-code frontend/src/api/schema.d.ts \
            || (echo "::error::schema.d.ts is stale — run 'make gen-client' and commit"; exit 1)
```

`--output-format=github` makes ruff findings appear as inline annotations on the PR diff, which is
what turns a lint failure into a reviewable comment instead of a log-scrolling exercise.

### 3.2 `test-backend` (coverage ≥ 65% on `app/`)

```yaml
  test-backend:
    runs-on: ubuntu-24.04
    services:
      postgres:
        image: postgres:16.4-alpine
        env: {POSTGRES_USER: ci, POSTGRES_PASSWORD: ci, POSTGRES_DB: civicpulse_test}
        options: >-
          --health-cmd "pg_isready -U ci" --health-interval 5s --health-timeout 3s --health-retries 10
        ports: ["5432:5432"]
      redis:
        image: redis:7.4.1-alpine
        options: >-
          --health-cmd "redis-cli ping" --health-interval 5s --health-timeout 3s --health-retries 10
        ports: ["6379:6379"]
    env:
      DATABASE_URL: postgresql+psycopg://ci:ci@localhost:5432/civicpulse_test
      REDIS_URL: redis://localhost:6379/0
      TRIAGE_PROVIDER: simulated
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12", cache: pip}
      - run: pip install -e "backend[dev]"
      - run: cd backend && alembic upgrade head
      - run: cd backend && pytest            # --cov-fail-under=65 lives in pyproject.toml
      - uses: actions/upload-artifact@v4
        if: always()
        with: {name: coverage-xml, path: backend/coverage.xml}
```

> **`localhost` here is legitimate and is NOT the §5.3 −8 violation.** Service containers are
> published onto the runner's loopback; this is the runner talking to itself, not service-to-service
> config. `make lint-localhost` excludes `.github/` and `tests/` for exactly this reason. Be ready to
> explain the distinction — it is a plausible viva trap.

### 3.3 `test-frontend`

```yaml
  test-frontend:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {node-version: "22", cache: npm, cache-dependency-path: frontend/package-lock.json}
      - run: cd frontend && npm ci
      - run: cd frontend && npm run test -- --run --coverage
      - name: assert ≥5 tests actually ran
        run: |
          n=$(jq '.numTotalTests' frontend/coverage/test-results.json)
          [ "$n" -ge 5 ] || { echo "::error::only $n frontend tests (rubric B requires ≥5)"; exit 1; }
```

Asserting the **count** in CI is what stops the rubric line rotting when somebody deletes a test.
Same pattern for the backend's ≥ 14.

### 3.4 `build` — build, **do not push**

```yaml
  build:
    runs-on: ubuntu-24.04
    permissions: {contents: read}          # ← notably NOT packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: backend/Dockerfile
          push: false                       # §3.4 — a PR must not publish artifacts
          load: true
          tags: civicpulse-backend:ci
          build-args: GIT_SHA=${{ github.sha }}
          cache-from: type=gha,scope=backend
          cache-to:   type=gha,mode=max,scope=backend
      - uses: docker/build-push-action@v6
        with: {context: ., file: frontend/Dockerfile, push: false, load: true,
               tags: civicpulse-frontend:ci, cache-from: "type=gha,scope=frontend",
               cache-to: "type=gha,mode=max,scope=frontend"}
      - name: size gate (§3.1 — frontend under ~60MB)
        run: |
          sz=$(docker image inspect civicpulse-frontend:ci --format '{{.Size}}')
          echo "frontend image: $((sz/1024/1024)) MB"
          [ "$sz" -lt 67108864 ] || { echo "::error::frontend image >64MB — multi-stage split is leaking"; exit 1; }
      - run: docker save civicpulse-backend:ci civicpulse-frontend:ci -o /tmp/images.tar
      - uses: actions/upload-artifact@v4
        with: {name: ci-images, path: /tmp/images.tar, retention-days: 1}
```

The **size gate is a rubric line turned into a build failure**. §3.1 says *"a frontend image over
~60 MB means the multi-stage split is not doing its job"* — so make it impossible to merge one.

### 3.5 `scan` — Trivy

```yaml
  scan:
    runs-on: ubuntu-24.04
    needs: build
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with: {name: ci-images, path: /tmp}
      - run: docker load -i /tmp/images.tar
      - uses: aquasecurity/trivy-action@0.28.0
        with:
          image-ref: civicpulse-backend:ci
          severity: HIGH,CRITICAL
          ignore-unfixed: true          # ← §3.4: "with a fixed version available"
          exit-code: "1"
          format: table
      - uses: aquasecurity/trivy-action@0.28.0
        with: {image-ref: civicpulse-frontend:ci, severity: HIGH,CRITICAL,
               ignore-unfixed: true, exit-code: "1"}
      - uses: aquasecurity/trivy-action@0.28.0    # SARIF for the Security tab
        if: always()
        with: {image-ref: civicpulse-backend:ci, format: sarif, output: trivy.sarif, exit-code: "0"}
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with: {sarif_file: trivy.sarif}
```

**`ignore-unfixed: true` is the spec, and it is the right call**, so say why: a HIGH with no
available fix is information, not an action. Failing the build on it means the only way to go green
is to ignore the scanner entirely, which trains the team to ignore red — the same argument §2.5
makes about flaky tests, applied to security tooling.

`.trivyignore` entries require a comment with a justification **and an expiry date**. An
unexplained ignore file is how a scanner becomes decoration.

### 3.6 `manifests` — kustomize + kubeconform

```yaml
  manifests:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - run: |
          curl -sL https://github.com/yannh/kubeconform/releases/download/v0.6.7/kubeconform-linux-amd64.tar.gz | tar xz -C /usr/local/bin kubeconform
          curl -sL "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv5.4.3/kustomize_v5.4.3_linux_amd64.tar.gz" | tar xz -C /usr/local/bin kustomize
      - name: validate both overlays
        run: |
          for ov in dev prod; do
            kustomize build "k8s/overlays/$ov" | kubeconform -strict -summary \
              -schema-location default \
              -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'
          done
      - name: §5.3 −8 — no :latest in any deployed manifest
        run: |
          ! kustomize build k8s/overlays/prod | grep -nE 'image:.*:latest' \
            || { echo "::error::deploying :latest (§5.3 −8)"; exit 1; }
      - name: §5.3 −15 — no real secrets in committed manifests
        run: |
          ! grep -rniE 'gsk_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}' k8s/ \
            || { echo "::error::key material in k8s manifests (§5.3 −15)"; exit 1; }
      - name: §5.3 −8 — DB is a StatefulSet and never NodePort/LoadBalancer
        run: |
          kustomize build k8s/overlays/prod | python3 scripts/assert_k8s_invariants.py
```

**The second `-schema-location` is the 20-minute trap.** `kubeconform -strict` fails on
`VerticalPodAutoscaler` and `ServiceMonitor` because their CRD schemas are not in the default
set. The CRDs-catalog URL supplies them. The alternative, `-ignore-missing-schemas`, makes the
job green by *skipping* validation of exactly the resources most likely to be wrong — which
defeats the purpose. Use the catalog.

> §3.4 on this job: *"catches a broken manifest in 20 seconds instead of on the cluster."* That is
> the shift-left argument in one sentence; put it in the notes.

### 3.7 `integration` — the compose smoke (Rubric I, 3 marks)

```yaml
  integration:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - run: cp .env.example .env
      - run: docker compose up -d --build --wait --wait-timeout 180
      - run: docker compose exec -T backend alembic upgrade head
      - run: docker compose exec -T backend python -m app.cli.seed
      - name: readiness
        run: ./scripts/wait_for.sh http://localhost:8080/api/stats 60
      - name: POST → GET → assert category
        run: |
          id=$(curl -sf -XPOST localhost:8080/api/complaints \
                 -H 'content-type: application/json' \
                 -d '{"text":"burst water main flooding street 12 since fajr, ground floor full",
                      "location":"Street 12, G-9/1"}' | jq -r .id)
          [ -n "$id" ] && [ "$id" != "null" ]
          cat=$(curl -sf "localhost:8080/api/complaints/$id" | jq -r .category)
          echo "category=$cat"
          [ "$cat" = "water" ] || { echo "::error::triage produced '$cat', expected 'water'"; exit 1; }
      - name: X-Cache MISS → HIT
        run: |
          a=$(curl -si localhost:8080/api/stats | grep -i '^x-cache:' | tr -d '\r' | awk '{print $2}')
          b=$(curl -si localhost:8080/api/stats | grep -i '^x-cache:' | tr -d '\r' | awk '{print $2}')
          echo "first=$a second=$b"
          [ "$a" = "MISS" ] && [ "$b" = "HIT" ]
      - name: invalidation on write
        run: |
          curl -sf -XPOST localhost:8080/api/complaints -H 'content-type: application/json' \
            -d '{"text":"streetlight pole 14 fused since three days, total dark at night","location":"G-9/1"}' >/dev/null
          c=$(curl -si localhost:8080/api/stats | grep -i '^x-cache:' | tr -d '\r' | awk '{print $2}')
          [ "$c" = "MISS" ]
      - name: network segmentation (§3.2) — this MUST fail
        run: |
          if docker compose exec -T frontend sh -c 'nc -z -w2 database 5432'; then
            echo "::error::frontend can reach the database (§5.3 −8)"; exit 1
          fi
          echo "segmentation OK: frontend cannot reach database"
      - name: rate limiter returns 429 + Retry-After
        run: |
          for i in $(seq 1 12); do
            code=$(curl -s -o /dev/null -w '%{http_code}' -XPOST localhost:8080/api/complaints \
                    -H 'content-type: application/json' -d @fixtures/one.json)
          done
          [ "$code" = "429" ]
          curl -si -XPOST localhost:8080/api/complaints -H 'content-type: application/json' \
            -d @fixtures/one.json | grep -i '^retry-after:'
      - if: always()
        run: docker compose logs --no-color > compose-logs.txt
      - if: always()
        uses: actions/upload-artifact@v4
        with: {name: compose-logs, path: compose-logs.txt}
      - if: always()
        run: docker compose down -v
```

This one job asserts **six rubric lines at once**: triage correctness, cache HIT/MISS, cache
invalidation, network segmentation, rate limiting, and the quickstart actually working from a clean
checkout. §3.4: *"it is the job that will catch your `localhost` bug before a human does."*

**`docker compose up --wait --wait-timeout 180`** blocks on healthchecks, so a service that starts
but never becomes healthy fails here with a clear message rather than producing a cryptic curl
error 40 lines later.

---

## 4. `cd.yml` — on push to `main`

```yaml
name: cd
on:
  push: {branches: [main]}
permissions: {contents: read}
concurrency: {group: cd-main, cancel-in-progress: false}   # never cancel a deploy

env:
  REGISTRY: ghcr.io
  IMAGE_BASE: ghcr.io/${{ github.repository_owner }}/civicpulse

jobs:
  test:
    uses: ./.github/workflows/ci.yml        # reuse; the suite runs on the MERGED result
    secrets: inherit

  build-push:
    needs: test                              # ←←← §5.3 −8 IF ABSENT
    runs-on: ubuntu-24.04
    permissions: {contents: read, packages: write, id-token: write}
    outputs:
      backend-digest:  ${{ steps.be.outputs.digest }}
      frontend-digest: ${{ steps.fe.outputs.digest }}
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}     # scoped, revocable, auto-rotated
      - id: be
        uses: docker/build-push-action@v6
        with:
          context: ., file: backend/Dockerfile, push: true
          tags: |
            ${{ env.IMAGE_BASE }}-backend:${{ github.sha }}
            ${{ env.IMAGE_BASE }}-backend:latest
          build-args: GIT_SHA=${{ github.sha }}
          provenance: true
          cache-from: type=gha,scope=backend
          cache-to:   type=gha,mode=max,scope=backend
      - id: fe
        uses: docker/build-push-action@v6
        with: {context: ., file: frontend/Dockerfile, push: true,
               tags: "${{ env.IMAGE_BASE }}-frontend:${{ github.sha }}\n${{ env.IMAGE_BASE }}-frontend:latest",
               provenance: true}
      - name: SBOM (Syft)
        uses: anchore/sbom-action@v0
        with: {image: "${{ env.IMAGE_BASE }}-backend:${{ github.sha }}",
               format: spdx-json, output-file: sbom-backend.spdx.json}
      - uses: actions/upload-artifact@v4
        with: {name: sbom, path: "sbom-*.spdx.json"}
      - name: Cosign keyless sign (bonus +3)
        uses: sigstore/cosign-installer@v3
      - run: |
          cosign sign --yes "${{ env.IMAGE_BASE }}-backend@${{ steps.be.outputs.digest }}"
          cosign sign --yes "${{ env.IMAGE_BASE }}-frontend@${{ steps.fe.outputs.digest }}"

  deploy-k8s:
    needs: build-push                        # ←←← §5.3 −8 IF ABSENT
    runs-on: ubuntu-24.04
    permissions: {contents: read, packages: read, id-token: write}
    steps:
      - uses: actions/checkout@v4
      - name: verify signatures before deploying (bonus)
        run: |
          cosign verify "${{ env.IMAGE_BASE }}-backend@${{ needs.build-push.outputs.backend-digest }}" \
            --certificate-identity-regexp "https://github.com/${{ github.repository }}/.*" \
            --certificate-oidc-issuer https://token.actions.githubusercontent.com
      - uses: helm/kind-action@v1
        with: {cluster_name: civicpulse-ci, wait: 180s}
      - name: ingress-nginx
        run: |
          kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3/deploy/static/provider/kind/deploy.yaml
          kubectl -n ingress-nginx wait --for=condition=ready pod \
            -l app.kubernetes.io/component=controller --timeout=300s
      - name: secrets from GitHub Secrets — never from the repo
        run: |
          kubectl create namespace civicpulse --dry-run=client -o yaml | kubectl apply -f -
          kubectl -n civicpulse create secret generic app-secrets \
            --from-literal=POSTGRES_USER=civicpulse \
            --from-literal=POSTGRES_PASSWORD='${{ secrets.POSTGRES_PASSWORD }}' \
            --from-literal=LLM_API_KEY='${{ secrets.LLM_API_KEY }}' \
            --dry-run=client -o yaml | kubectl apply -f -
      - name: pin the overlay to THIS commit  (§5.3 −8: never :latest)
        run: |
          cd k8s/overlays/prod
          kustomize edit set image \
            ${{ env.IMAGE_BASE }}-backend=${{ env.IMAGE_BASE }}-backend@${{ needs.build-push.outputs.backend-digest }} \
            ${{ env.IMAGE_BASE }}-frontend=${{ env.IMAGE_BASE }}-frontend@${{ needs.build-push.outputs.frontend-digest }}
          kustomize build . | tee /tmp/rendered.yaml | grep -E 'image:'
      - run: kubectl apply -f /tmp/rendered.yaml
      - run: |
          kubectl -n civicpulse rollout status statefulset/postgres --timeout=300s
          kubectl -n civicpulse rollout status deployment/backend  --timeout=300s
          kubectl -n civicpulse rollout status deployment/frontend --timeout=300s
      - name: smoke test through the Ingress
        run: |
          kubectl -n civicpulse port-forward svc/frontend 8080:8000 &
          ./scripts/wait_for.sh http://localhost:8080/api/stats 90
          curl -sf localhost:8080/api/stats | jq -e '.total >= 0'
          id=$(curl -sf -XPOST localhost:8080/api/complaints -H 'content-type: application/json' \
                 -d @fixtures/one.json | jq -r .id)
          curl -sf "localhost:8080/api/complaints/$id" | jq -e '.category != null'
      - run: kubectl -n civicpulse get hpa            # §3.4 — "print kubectl get hpa"
      - if: failure()
        run: |
          kubectl -n civicpulse get pods -o wide
          kubectl -n civicpulse describe pods -l app=backend
          kubectl -n civicpulse logs -l app=backend --tail=200 --all-containers
```

### 4.1 Why `needs:` is the highest-value four characters in the repo

> §3.4: *"Without it you publish artifacts from code you already know is broken."*

GitHub runs jobs **in parallel by default**. Without `needs: test`, `build-push` starts at the same
instant as the test suite, and on a broken commit the registry receives an image tagged with that
commit SHA anyway. Someone then deploys it by SHA — which is exactly the *correct* deployment
practice — and ships known-broken code with full traceability. The `needs:` edge is what makes
"deploy by SHA" safe rather than merely auditable.

`scripts/check_submission.py::CI-NEEDS` parses every workflow, finds jobs whose steps contain
`push: true`, `kubectl apply`, `helm upgrade` or `cosign sign`, and asserts a non-empty `needs`.

### 4.2 Why deploy by **digest**, not tag (bonus +3, and the §5.3 −8 armour)

| Reference | Mutable? | What it identifies |
|---|---|---|
| `:latest` | yes, constantly | nothing. **−8 if deployed** |
| `:${{ github.sha }}` | yes in principle — a tag can be re-pushed | a commit, by convention |
| `@sha256:…` | **no** | the exact bytes of the image |

We push both `:sha` and `:latest` (§3.4 permits pushing `latest`) and deploy the **digest**.
`:latest` exists for humans doing `docker pull` locally; it is never referenced by a manifest.

> §3.4's test: *"'What is production running?' must have a one-word answer you can paste into
> `git show`."* With a digest, the answer is even stronger — the digest is a hash of the artefact,
> not of the source, so it also covers the base image and the build environment.

### 4.3 Secrets handling

- `GITHUB_TOKEN` + `packages: write` for GHCR — scoped to the repository, expires with the run,
  revocable, no manual rotation. §3.4 calls it *"the cleanest path."*
- `LLM_API_KEY`, `POSTGRES_PASSWORD` in **repository secrets**, injected only in `deploy-k8s`.
- **Never `echo` a secret.** Actions masks known secret values in logs, but `base64`-ing or
  `jq`-transforming one defeats the mask. `kubectl create secret --dry-run=client -o yaml | kubectl
  apply -f -` never writes the value to a file or to stdout in plaintext.
- `permissions` is `contents: read` by default; `packages: write` appears only on `build-push`;
  `id-token: write` only where Cosign needs OIDC.

---

## 5. `release.yml` — on tag `v*`

```yaml
name: release
on: {push: {tags: ["v*"]}}
permissions: {contents: write, packages: write, id-token: write}
jobs:
  release:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
        with: {fetch-depth: 0}             # full history for release notes
      - uses: docker/login-action@v3
        with: {registry: ghcr.io, username: "${{ github.actor }}", password: "${{ secrets.GITHUB_TOKEN }}"}
      - uses: docker/metadata-action@v5
        id: meta
        with:
          images: ghcr.io/${{ github.repository_owner }}/civicpulse-backend
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            type=sha
      - uses: docker/build-push-action@v6
        with: {context: ., file: backend/Dockerfile, push: true,
               tags: "${{ steps.meta.outputs.tags }}", labels: "${{ steps.meta.outputs.labels }}"}
      - uses: softprops/action-gh-release@v2
        with: {generate_release_notes: true, files: "sbom-*.spdx.json"}
```

`docker/metadata-action` emits OCI labels (`org.opencontainers.image.revision`,
`.source`, `.created`) so `docker inspect` on a running image tells you the commit it came from
without consulting the registry. Cheap provenance; mention it.

---

## 6. Proving the gate works (Rubric I, 1 mark — *"red pipeline blocking merge, then green"*)

This is **scheduled work**, done once, on a real PR. Do it in Phase 5.

```bash
git switch -c chore/ci-prove-the-gate
cat >> backend/tests/unit/test_gate_proof.py <<'EOF'
def test_deliberately_failing_gate_proof():
    """TEMPORARY: proves required checks block a merge. Removed in the next commit."""
    assert 1 == 2, "deliberate failure to demonstrate the CI gate"
EOF
git commit -am "test: deliberate failure to demonstrate the CI gate"
git push -u origin chore/ci-prove-the-gate
gh pr create --base main --title "chore: prove the CI gate blocks merges" --body "Refs #N"
```

**Capture, in this order:**
1. `docs/evidence/ci-red.png` — the checks panel with `test-backend` red **and the merge button
   greyed out with "Required statuses must pass before merging"**. The greyed button is the actual
   evidence; a red X alone only proves a test failed.
2. Fix in the **same PR** (`git revert` the test, or delete it).
3. `docs/evidence/ci-green.png` — all seven checks green, merge button enabled.
4. `docs/evidence/ci-gate-pr-url.txt` — the PR permalink, so a marker can verify the timeline.

---

## 7. Rollback — both mechanisms, both on video (§3.4)

### 7.1 Imperative — *the 3 a.m. answer*

```bash
kubectl -n civicpulse rollout history deployment/backend
kubectl -n civicpulse rollout undo deployment/backend
kubectl -n civicpulse rollout status deployment/backend --timeout=120s
kubectl -n civicpulse get deploy backend -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
```
Under 30 seconds, no repository access, no CI run, no approval. It uses the ReplicaSet history the
Deployment already keeps (`revisionHistoryLimit`, default 10).

**Its weakness, and you must say it:** the cluster is now running something the repository does not
describe. The next `kubectl apply` or GitOps sync **re-applies the broken version**. It buys time; it
does not fix state.

### 7.2 Declarative — *the correct answer once the fire is out*

```bash
PREV=$(git rev-parse HEAD~1)
cd k8s/overlays/prod
kustomize edit set image ghcr.io/ORG/civicpulse-backend=ghcr.io/ORG/civicpulse-backend:$PREV
git commit -am "revert(deploy): pin backend to $PREV after incident 2026-09-25"
git push                       # → triggers cd.yml → full pipeline → deploy
```
Slower (a full CI/CD run), auditable, reviewable, and it leaves git and the cluster **in agreement**.

### 7.3 The decision rule, for the video and the runbook

| Situation | Use |
|---|---|
| Production is down, users affected, cause unknown | **`rollout undo`** — restore service, diagnose after |
| Bad deploy identified, no active incident | **re-apply previous SHA** — one mechanism, one source of truth |
| GitOps (Argo/Flux) is reconciling | **only** the declarative path; `rollout undo` will be reverted by the controller within its sync interval |
| Database migration already applied | **neither alone** — code rollback + a down-migration, or forward-fix. `05-DATA-LAYER.md §3.3` is why every `upgrade` needs a real `downgrade` |

> That last row is the one that impresses. Most teams demonstrate rollback and never mention that
> a schema change makes rollback a **two-artefact** problem.

---

## 8. Maturity-ladder self-assessment (§5.2 question 2)

Answer against Lecture 03 slide 32, then justify. The honest position for a complete CivicPulse:

| Rung | Have it? | Evidence |
|---|---|---|
| Version control, everyone commits | ✅ | `git shortlog -sn`, ≥35 commits, ≥35% each |
| Automated build on every push | ✅ | `ci.yml` `build` job |
| Automated test on every push, merge blocked on red | ✅ | required checks + `ci-red.png` |
| Artefacts built once, promoted | ✅ | `build-push` → digest → `deploy-k8s`; no rebuild between stages |
| Automated deploy to a production-like environment | ✅ | `deploy-k8s` on an ephemeral kind cluster |
| **Continuous deployment to real production** | ❌ | there is no real production; the cluster is created and destroyed per run |
| Progressive delivery (canary/blue-green), automated rollback on SLO breach | ❌ | rollback is manual; no SLO gate |

**The next rung and what it buys:** *automated rollback triggered by a post-deploy SLO check.*
Today `deploy-k8s` smoke-tests once and stops; a bad deploy that passes the smoke test but
degrades p95 latency stays up until a human notices. The next rung is a 5-minute post-deploy
watch on the `http_request_duration_seconds` p95 and `triage_fallback_total` rate
(`10-OBSERVABILITY.md §4`), with an automatic `rollout undo` on breach. It buys **mean-time-to-
recovery measured in minutes without a human in the loop**, which is the actual point of the
ladder. Cite the file and line where the smoke test lives so the answer is specific.
