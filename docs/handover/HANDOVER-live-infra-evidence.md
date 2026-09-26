# HANDOVER — everything that needs a real Docker daemon / k3d cluster / human hands

<!-- Written 2026-09-26, end of a Claude Code session that closed every rubric gap it
     could close without live infrastructure, then hit a hard wall. This file is the
     complete, end-to-end list of what's left, with exact commands, expected output,
     and where to save each artefact. Nothing below can be produced by an AI agent in
     a sandboxed environment — they all require either a running Docker daemon, a
     live Kubernetes cluster, GHCR credentials with push rights, or a human doing a
     human thing (recording a video, clicking approve on a PR review). -->

## 0. Why this file exists

This session ran a full rubric-traceability audit (`docs/20-RUBRIC-TRACEABILITY.md`) and
closed every row provable from source code, git history, and the GitHub API alone — see
`docs/handover/HANDOVER-fix-close-disclosed-gaps-rubric-evidence.md` for that list (30 rows,
PR #49). What's left in this file is different in kind, not just in size: **none of it can be
faked, scripted around, or produced by another agent run in this same sandbox**, because the
sandbox has no Docker socket access (`permission denied` on every attempt, confirmed
repeatedly across three separate sessions) and no k3d/kind cluster. Producing fake output for
any of these would be exactly the CLAUDE.md rule-14/rule-15 violation this project's own
design exists to catch — so none of it was attempted, and none of it should be from any AI
session running in this same kind of sandbox. A session with real Docker access (e.g. running
directly on your machine, not in this cloud sandbox) could do all of §1–§4 in under an hour.

**Read `01-WORKFLOW.md` before running anything that opens a PR — branch from `dev`, never
commit to `main` directly (HARD rule 2).**

---

## 1. Compose integration evidence — needs a real Docker daemon, ~15 minutes

```bash
# from repo root, with Docker running
cp .env.example .env
docker compose up -d --build --wait --wait-timeout 180
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend python -m app.cli.seed
```

### 1.1 Cache behaviour (rows E1, E2 — 5 marks)
```bash
docker compose exec -T cache redis-cli FLUSHALL
{
  echo "=== first read, expect MISS ==="
  curl -si localhost:8080/api/stats | grep -i '^x-cache:'
  echo "=== second read, expect HIT ==="
  curl -si localhost:8080/api/stats | grep -i '^x-cache:'
  echo "=== POST a complaint ==="
  curl -s -X POST localhost:8080/api/complaints \
    -H 'Content-Type: application/json' \
    -d '{"text":"cache invalidation evidence probe","location":"evidence capture"}' \
    -o /dev/null -w 'status=%{http_code}\n'
  echo "=== third read, expect MISS again (invalidated) ==="
  curl -si localhost:8080/api/stats | grep -i '^x-cache:'
} | tee docs/evidence/cache-behaviour.txt
```
Expected: MISS, HIT, 201, MISS. If the third read is still HIT, `ComplaintService.create()`'s
invalidation call is broken — that's a real bug to fix, not a script problem, check
`backend/app/services/complaint_service.py` around the `StatsService.invalidate()` call.

### 1.2 Distributed rate limiter (row E3 — 4 marks)
```bash
{
  echo "=== 12 rapid POSTs, expect 429s once the window is exceeded ==="
  for i in $(seq 1 12); do
    curl -s -o /dev/null -w 'req %s -> %{http_code}\n' -X POST localhost:8080/api/complaints \
      -H 'Content-Type: application/json' -d @fixtures/one.json | sed "s/^req %s/req $i/"
  done
  echo "=== check Retry-After header on a 429 ==="
  curl -si -X POST localhost:8080/api/complaints -H 'Content-Type: application/json' \
    -d @fixtures/one.json | grep -i '^retry-after:'
} | tee docs/evidence/ratelimit-distributed.txt
```
If you have `docker compose up --scale backend=2` available, re-run this against both
replicas via the load balancer / directly against each port to prove the limiter state is
shared via Redis, not per-process — that's the "distributed" claim in E3, a single-replica
run only proves the limiter works, not that it's distributed.

### 1.3 Redis AOF persistence (row E4 — 1 mark)
```bash
{
  echo "=== AOF config ==="
  docker compose exec -T cache redis-cli CONFIG GET appendonly
  echo "=== restart and confirm data survived ==="
  docker compose restart cache
  sleep 3
  docker compose exec -T cache redis-cli DBSIZE
} | tee docs/evidence/redis-aof-persistence.txt
```

### 1.4 Network segmentation double-check (rows G3 — already partially evidenced)
`docs/evidence/network-isolation.txt` already exists from an earlier session. Re-verify it's
still current:
```bash
docker compose exec -T frontend sh -c 'nc -z -w2 database 5432' \
  && echo "FAIL: frontend reached the database" \
  || echo "OK: frontend cannot reach the database"
```

### 1.5 Compose healthchecks (row G5 — 2 marks)
```bash
docker compose ps --format 'table {{.Service}}\t{{.Health}}\t{{.Status}}' \
  | tee docs/evidence/compose-healthchecks.txt
```
All services should show `healthy`.

### 1.6 Image build evidence (row G1 — 4 marks)
```bash
{
  echo "=== backend image ==="
  docker images civicpulse-backend --format '{{.Repository}}:{{.Tag}} {{.Size}}'
  echo "=== frontend image ==="
  docker images civicpulse-frontend --format '{{.Repository}}:{{.Tag}} {{.Size}}'
  echo "=== confirm non-root ==="
  docker compose exec -T backend id
  docker compose exec -T frontend id
} | tee docs/evidence/image-build-evidence.txt
```

Clean up when done:
```bash
docker compose down -v
```

---

## 2. Kubernetes evidence — needs k3d or kind, ~30-45 minutes

### 2.1 Cluster setup (once)
```bash
k3d cluster create civicpulse --agents 2 -p "8080:80@loadbalancer"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch deployment metrics-server -n kube-system --type=json -p='[
  {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"},
  {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-preferred-address-types=InternalIP"}
]'
# wait ~30s, then confirm:
kubectl top nodes   # must return numbers, not an error
```

### 2.2 Deploy and persistence proof (row H1 — 5 marks; already have persistence-k8s.txt from
an earlier session, but re-verify it's current)
```bash
kubectl apply -k k8s/overlays/dev
kubectl -n civicpulse rollout status deployment/backend
kubectl -n civicpulse rollout status deployment/frontend
kubectl -n civicpulse get all
kubectl -n civicpulse get svc -o wide   # confirm ALL are ClusterIP, no NodePort/LB
```

### 2.3 Probes (row H3 — 4 marks)
```bash
kubectl -n civicpulse get pod -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{.spec.containers[*].livenessProbe}{"\n"}{.spec.containers[*].readinessProbe}{"\n\n"}{end}' \
  | tee docs/evidence/probe-config.txt
```

### 2.4 Resource requests/limits (row H4 — 2 marks)
```bash
kubectl -n civicpulse describe deploy backend | grep -A2 -i 'requests\|limits' \
  | tee docs/evidence/resource-requests-limits.txt
```

### 2.5 NetworkPolicy enforcement (part of H1/deduction armour — `netpol-enforcement.txt`
already exists from an earlier session; re-verify with k3d specifically, kindnet does NOT
enforce NetworkPolicy per `13-KUBERNETES.md §9`)
```bash
POD=$(kubectl -n civicpulse get pod -l app=frontend -o jsonpath='{.items[0].metadata.name}')
kubectl -n civicpulse exec "$POD" -- nc -z -w2 postgres 5432 \
  && echo "FAIL: NetworkPolicy not enforced" \
  || echo "OK: NetworkPolicy enforced"
```

### 2.6 HPA capture — wall-clock bound, needs k6 (row H5 — 4 marks)
This is the one item on this whole list that genuinely cannot be rushed — the doc's own
critical-path notes say so (`02-CRITICAL-PATH.md §3`). Budget 15-20 real minutes.
```bash
kubectl apply -f k8s/base/hpa.yaml -n civicpulse
# in one terminal:
kubectl -n civicpulse get hpa -w | tee docs/evidence/hpa-watch.txt
# in another terminal, once metrics-server is confirmed working:
k6 run load/k6-script.js --out json=docs/evidence/k6-summary.json
```
Let it run long enough to see replicas rise from 2 to ≥4 and then fall back down after load
stops — that fall-back is part of what H5 checks for, not just the rise.
Then plot it:
```bash
python3 load/plot_hpa.py docs/evidence/hpa-watch.txt docs/evidence/k6-summary.json \
  -o docs/evidence/hpa-replicas-vs-load.png
```

### 2.7 VPA two-run loop (row H6 — 3 marks)
```bash
# install VPA (see 14-LOAD-AUTOSCALING.md §7 for the exact manifests/version)
kubectl apply -f k8s/base/vpa.yaml -n civicpulse
# let it accumulate real CPU history — minutes, not seconds, this is also wall-clock bound
sleep 300
kubectl -n civicpulse describe vpa backend-vpa | tee docs/evidence/vpa-describe-run1.txt
```
Then, per the doc's own instruction, **update `k8s/base/backend.yaml`'s `requests` to match
the VPA's `Target` recommendation, in its own commit citing the number**, redeploy, wait
again, and capture run 2:
```bash
# after editing k8s/base/backend.yaml and committing/pushing that change:
kubectl apply -k k8s/overlays/dev
sleep 300
kubectl -n civicpulse describe vpa backend-vpa | tee docs/evidence/vpa-describe-run2.txt
```
Write up `docs/ENGINEERING-NOTES.md` Q5 (lag decomposed in real seconds you observed) and Q6
(what happened when VPA's Auto mode and HPA fought, or why you used Off mode) with the real
numbers from these two files — do not write these before you have the real files, the doc's
own rule is these need real numbers, not projected ones.

### 2.8 Zero-downtime rollout (bonus, +4 marks — cut-order says "keep, it's cheap")
```bash
# in one terminal, hammer the ingress during a rollout:
k6 run load/k6-rollout.js --out json=docs/evidence/zero-downtime-k6.json &
kubectl -n civicpulse set image deployment/backend backend=<new-sha-tag>
kubectl -n civicpulse rollout status deployment/backend
wait
# check the k6 summary's failure rate is exactly 0
jq '.metrics.http_req_failed' docs/evidence/zero-downtime-k6.json | tee docs/evidence/zero-downtime-rollout.txt
```

Tear down when done: `k3d cluster delete civicpulse`

---

## 3. CD pipeline evidence — needs PR #48 merged first, then a real push to `main`

**This one has a dependency on you specifically**: `cd.yml` triggers only on `push: {
branches: [main] }`. Until PR #48 (`chore/promote-dev-to-main`, currently open, conflicts
resolved, CI running) is reviewed and merged by a human with merge rights, `cd.yml` cannot
run at all — this isn't a script gap, it's the literal trigger condition.

Once #48 merges:
```bash
gh run list --workflow cd.yml --limit 5
# wait for it to complete, then:
gh run view <run-id> --log | tee docs/evidence/cd-run-log.txt
```
Capture the GHCR package page showing SHA-tagged images (row I4):
```bash
gh api /orgs/IfBilal/packages/container/civicpulse-backend/versions --jq '.[0:3]'
# or just open https://github.com/IfBilal?tab=packages in a browser and screenshot it
```

For the rollback demonstration (Gate 8, required for the video):
```bash
kubectl -n civicpulse rollout undo deployment/backend
kubectl -n civicpulse rollout status deployment/backend   # must complete in under 30s
```

---

## 4. Things that are not infrastructure problems — they need a human decision

### 4.1 A3 — PR review rigor (4 marks, currently disproven, not just unproven)
`docs/evidence/pr-review-audit.txt` (from PR #49) shows 12 of 35 merged PRs have **zero**
reviews, and nearly all the rest are empty-body approvals. This cannot be fixed
retroactively — you cannot un-rubber-stamp a merged PR. Two honest options:
1. Going forward, every remaining PR (including #48, #49, #50, and whatever comes out of
   this session) gets a real review comment from the other partner — not "LGTM" — citing
   something specific in the diff. If enough real reviews land from here to submission, the
   ratio improves; it still won't erase the 12 zero-review PRs.
2. Disclose it plainly in the README's Known Limitations section (already done in PR #50)
   and be ready to explain it honestly at viva — the project's own CLAUDE.md explicitly
   prefers "state it as a known gap" over hiding it, and a marker who runs
   `gh pr list --json reviews` will find the same thing this audit found either way.

**Actually usable action item right now**: review PR #48, #49, #50 (and #51 if the RUNBOOK
agent's PR lands) yourself, with real comments, not a rubber stamp. That's the one piece of
this whole list that takes five minutes and directly improves a real rubric row.

### 4.2 A4 — commit share ambiguity (3 marks)
`docs/evidence/shortlog.txt` (from PR #49) shows the real number is either 35.9% (passes the
35% floor) or 22.6% (fails it), depending on whether GitHub-identity aliases are merged and
which ref range is counted. Decide which counting method you'll defend at viva — ideally
the one that matches how the rubric author would actually run `git shortlog`, not the one
that's most flattering — and note the decision in `docs/ENGINEERING-NOTES.md`.

### 4.3 J4 — the video (3 marks, mandatory, no partial credit)
Needs both partners physically speaking, ≤5 minutes, covering the six required beats from
`18-DOCS-EVIDENCE-VIVA.md §7`. This cannot be scripted, recorded, or faked by an AI session.
Once §1-§3 above produce their evidence, the video should visually show: the `/ready` 503
naming a dependency, the fallback triage test, the `X-Cache` MISS→HIT, the network-isolation
`nc` failure, `kubectl rollout undo` completing in under 30s, and the HPA replica count
changing live.

### 4.4 J1 — README clean-clone test (row J1, part of the −5 deduction-ledger item)
Must be executed by **the partner who did not write it**, from a genuinely fresh
`git clone` into an empty directory, per Gate 8's own checklist. An AI session running
inside the existing checkout cannot honestly produce this — cloning into a scratch
directory and running `make up` from *this* session would not prove what the check is
meant to prove (that a stranger with nothing but the repo URL can start the system).

---

## 5. Order of operations (do these in sequence, not randomly)

1. **Merge PR #48** (dev→main promotion) — unblocks `cd.yml` entirely. Do this first, it's
   the one dependency everything in §3 needs.
2. **Review and merge PR #49, #50** (rubric evidence, README rebuild) — low risk, docs-only,
   should be CI-green already.
3. **Merge whatever PR comes out of the RUNBOOK/ENGINEERING-NOTES work** (in flight as of
   this handover — check for a PR titled around "runbook" or "viva notes" against `dev`).
4. **Get a real Docker daemon** (your own machine, not this sandbox) and run all of §1.
5. **Get k3d or kind running** and do §2 — budget a real afternoon for this because of the
   wall-clock-bound HPA/VPA steps (§2.6/§2.7 alone are 30-40 minutes of real waiting).
6. **After #48 is merged**, watch `cd.yml` run for the first time ever and capture §3.
7. **Decide and document** §4.1 and §4.2 — five minutes each, no infrastructure needed.
8. **Record the video** (§4.3) once you have real HPA/rollback/cache footage to show.
9. **Have your partner clean-clone test the README** (§4.4).
10. Once all evidence files from §1-§3 exist, update `docs/20-RUBRIC-TRACEABILITY.md`'s
    remaining ☐ rows (D4, E1-E4, G1, G5, H1-H6, I4, I5, and the bonus rows) to ☑ — the same
    way PR #49 did for the statically-provable rows. At that point every row should be
    provable one way or another.
