# HANDOVER — Phase 7 HPA Load Capture, DEV-B → DEV-A

**From:** IfBilal (DEV-B / Edge) · **To:** T361 (DEV-A / Core) · **Date:** 2026-09-27
**Phase:** P7 Load + Autoscaling · **Gate:** Gate 7 (`14-LOAD-AUTOSCALING.md §8`) — not yet
closed, blocked on you for the reason below.

This is not a replacement for `14-LOAD-AUTOSCALING.md` — read that first if you haven't. This
is "here's exactly what I tried, here's exactly why it's landing on you, here's what will bite
you so you don't lose time rediscovering it."

---

## 1. Why this is moving to your machine

Per `02-CRITICAL-PATH.md` Day 10, the HPA capture is joint work — normally we'd do this in one
session, me driving the cluster, you driving the load. I ran the full setup solo first to have
it ready, and hit a hardware wall that isn't fixable by cleanup:

**Six real attempts on my laptop, all against a live k3d cluster with the real HPA config,
never faked.** Every attempt proved the actual mechanism works — replicas genuinely scaled
2→10 under real CPU load and back to 2 after, every single time. But `load/k6-script.js`'s own
pass/fail thresholds (`http_req_failed rate<1%`, `p95<3000ms`) never passed cleanly. Results
bounced between 1.4% and 13% failed across attempts, with no convergence even after freeing
RAM, disk, and closing every other app on the machine.

**Root cause, confirmed, not guessed:** at the plateau (120 req/s), the HPA correctly scales
backend to its max of 10 replicas — but all 10 replicas, Postgres, Redis, k3s itself, and
ingress-nginx are all containers on **one physical laptop**, sharing one CPU and one disk. In a
real cluster those 10 replicas would each get independent hardware; here, scaling out just adds
contention, not real capacity. The thresholds in the k6 script assume real multi-node capacity.
This is a hardware ceiling, not a bug in `app/` or in the HPA manifest — both are already
correct (see §3).

If your machine has meaningfully more headroom (more free RAM, more free disk, ideally not
running much else during the capture), a clean pass on your side directly fixes the root cause
instead of us just disclosing a caveat.

---

## 2. Two real bugs I hit that will cost you time if you don't know about them first

1. **The rate limiter will silently wreck your run.** `RATELIMIT_REQUESTS=10` per 60s is keyed
   by client IP (`09-CACHE-RATELIMIT.md §4.3`) — correct behavior in production, but a single
   load-generator machine looks like one citizen making 120 req/s and gets capped at 10, so
   `POST /api/complaints` returns 429 almost immediately and the HPA never sees real CPU load.
   Disable it for the duration of the capture only, on the cluster, not in any committed file:
   ```bash
   kubectl -n civicpulse set env deploy/backend RATELIMIT_ENABLED=false
   kubectl -n civicpulse rollout status deploy/backend
   # ... run the capture ...
   kubectl -n civicpulse set env deploy/backend RATELIMIT_ENABLED-   # revert after
   ```

2. **The `complaints` table compounds across repeated runs and quietly degrades every
   subsequent attempt.** Each 14-minute run inserts ~30-40k rows. Run it twice without clearing
   the table and the second run is measurably worse than the first — more rows, bigger index,
   slower writes — which looks like "the test is flaky" but is actually just DB growth. Truncate
   before every attempt:
   ```bash
   kubectl -n civicpulse exec postgres-0 -- psql -U PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUES \
     -d civicpulse -c "TRUNCATE complaints;"
   ```
   (Real username in your cluster is whatever your `Secret` actually has — check
   `kubectl -n civicpulse exec postgres-0 -- env | grep POSTGRES_USER` if it's not the
   placeholder.)

3. **k3d's disk-pressure eviction can taint every node on a machine that's otherwise fine for
   everything else.** If `kubectl get nodes -o custom-columns=TAINTS:.spec.taints` shows
   `disk-pressure` and pods go stuck `Pending`, either free real disk space or recreate the
   cluster with relaxed thresholds (this is a throwaway dev cluster, not production, so it's
   safe to loosen):
   ```bash
   k3d cluster create civicpulse --agents 2 -p "8081:80@loadbalancer" \
     --k3s-arg '--disable=traefik@server:*' \
     --k3s-arg '--kubelet-arg=eviction-hard=imagefs.available<1%,nodefs.available<1%@server:*' \
     --k3s-arg '--kubelet-arg=eviction-hard=imagefs.available<1%,nodefs.available<1%@agent:*' \
     --wait
   ```

---

## 3. What's already verified correct — don't re-check these, just use them

- `k8s/base/hpa.yaml` — matches `14-LOAD-AUTOSCALING.md §3` verbatim (asymmetric scale-up/down
  behavior, `minReplicas: 2`, `maxReplicas: 10`).
- `k8s/base/vpa.yaml` — matches `§7.1` verbatim (`updateMode: "Off"`, `migrate` container's mode
  set to `"Off"`).
- `k8s/base/backend-deployment.yaml` — already has `resources.requests: {cpu: 200m, memory:
  256Mi}`, the HPA's denominator. No manifest changes needed for any of this.
- `load/k6-script.js`, `load/corpus.json`, `load/plot_hpa.py`, `load/k6-rollout.js` — all exist,
  all run correctly against a live cluster. `plot_hpa.py` needs `matplotlib`
  (`python3 -m venv /tmp/plotvenv && /tmp/plotvenv/bin/pip install matplotlib` if your system
  Python is externally-managed and blocks a plain `pip install`).

---

## 4. The exact sequence to run on your machine

```bash
git fetch origin && git switch feat/phase7-load-autoscaling-devb && git pull

make k8s-up   # k3d + ingress-nginx + metrics-server, fully scripted already

docker build -t ghcr.io/ifbilal/civicpulse-backend:dev -f backend/Dockerfile \
  --build-arg GIT_SHA=dev .
docker build -t ghcr.io/ifbilal/civicpulse-frontend:dev -f frontend/Dockerfile .
k3d image import ghcr.io/ifbilal/civicpulse-backend:dev \
  ghcr.io/ifbilal/civicpulse-frontend:dev -c civicpulse
kubectl -n civicpulse rollout restart deploy/backend deploy/frontend
kubectl -n civicpulse rollout status deploy/backend
kubectl -n civicpulse rollout status deploy/frontend

# Gate before touching the HPA at all — both must return real numbers:
kubectl top nodes
kubectl top pods -n civicpulse

kubectl -n civicpulse set env deploy/backend RATELIMIT_ENABLED=false
kubectl -n civicpulse exec postgres-0 -- psql -U PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUES \
  -d civicpulse -c "TRUNCATE complaints;"

# Three terminals, all recorded, exactly as 14-LOAD-AUTOSCALING.md §4.2 specifies:
kubectl -n civicpulse get hpa backend-hpa -w > docs/evidence/hpa-watch.txt 2>&1 &

( while true; do
  printf '%s %s %s\n' "$(date +%s)" \
    "$(kubectl -n civicpulse get deploy backend -o jsonpath='{.status.readyReplicas}')" \
    "$(kubectl -n civicpulse get hpa backend-hpa -o jsonpath='{.status.currentMetrics[0].resource.current.averageUtilization}')"
  sleep 5
done > docs/evidence/hpa-samples.txt 2>&1 ) &

BASE_URL=http://localhost:8081 k6 run --summary-export=docs/evidence/k6-summary.json \
  load/k6-script.js > docs/evidence/k6-run.log 2>&1

# after it finishes (14 min):
python3 load/plot_hpa.py   # or the venv workaround above if matplotlib isn't installed

kubectl -n civicpulse set env deploy/backend RATELIMIT_ENABLED-   # revert
```

Check `docs/evidence/k6-run.log`'s tail for the threshold summary before deciding the run is
good — if `http_req_failed` and `http_req_duration` both stayed under their limits, you have a
clean pass. If not, truncate `complaints` again and re-run rather than assuming it's broken —
see §2 item 2.

---

## 5. What happens after your capture lands

**You drive this to the PR yourself — this is now your branch to finish and merge, not mine to
wait on.**

1. Stay on `feat/phase7-load-autoscaling-devb` (already has the caveman task-list log for this
   phase and this handover doc committed). Commit `docs/evidence/hpa-watch.txt`,
   `hpa-samples.txt`, `k6-summary.json`, `hpa-replicas-vs-load.png`, and `k6-run.log` once your
   run passes cleanly.
2. Do your own Day-11 slice on the same branch: the VPA five-step loop,
   `vpa-describe-run1.txt`/`run2.txt`, `k8s/base/backend.yaml`'s requests update citing the real
   Target **in its own commit**, and `docs/ENGINEERING-NOTES.md` Q6.
3. Ping me for `docs/ENGINEERING-NOTES.md` Q5 (HPA lag decomposed in seconds) — I'll write that
   from your real `hpa-watch.txt` timestamps once they exist; it's a few minutes, doesn't block
   you otherwise.
4. Run the pre-PR hardening review yourself (≥3 `file:line` findings or a credible
   "none found" — `CLAUDE.md §6` rule 2), log it in `docs/AI-USAGE.md`.
5. Open the PR from `feat/phase7-load-autoscaling-devb` into `dev` yourself, get a real review
   (not self-reviewed — rule 5), merge it.
6. Tell me once it's merged — I'll pull `dev` and pick up wherever Phase 7/8 goes next.

---

*Drafted with Claude Code from the DEV-B side. Corrections/disagreements welcome — this
reflects my understanding of the docs and of what actually happened on my machine, not a
ruling.*
