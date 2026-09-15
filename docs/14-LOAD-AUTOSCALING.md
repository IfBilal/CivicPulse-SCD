# 14 — LOAD TESTING AND AUTOSCALING (HPA · VPA · zero-downtime)

> **Owner:** both, joint session · **Days:** 10–11 · **Gate:** Gate 7 · **Rubric:** H lines 5–6 (7 marks) + bonus +4
> **This phase is wall-clock-bound.** You cannot compress a load test by working harder. Start on
> Day 10 or the chart does not exist and 7 marks vanish with no recovery path.

---

## 0. Why this phase is the one people fail

Three failure modes, all of which have already happened to somebody:

1. **`<unknown>/60%` forever.** No `resources.requests.cpu` on the pod ⇒ the HPA has no
   denominator ⇒ it never scales and never errors. §3.3 calls this out by name: *"Every semester,
   several teams debug a 'broken HPA' that is in fact a missing three-line block."*
2. **metrics-server `CrashLoopBackOff` on kind/k3d.** The kubelet serves metrics over TLS with a
   self-signed cert that metrics-server refuses. One flag fixes it. Without it `kubectl top` returns
   `error: Metrics API not available` and the HPA reads `<unknown>` for a *different* reason, which
   is why you must diagnose with `kubectl top` **before** blaming the HPA.
3. **A VPA `Target` that is empty.** The recommender needs real CPU history. Install it, run load,
   *then* describe. Describing a VPA five minutes after install on an idle cluster yields
   `Recommendation: <none>`, and teams conclude VPA is broken.

Diagnose in this order, always: `kubectl top pods` → `kubectl describe hpa` → `kubectl get hpa -w`.
If `top` is empty the problem is the metrics pipeline, not the autoscaler.

---

## 1. metrics-server — install and *verify*

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# kind/k3d only: the kubelet's serving cert is not signed by the cluster CA
kubectl -n kube-system patch deployment metrics-server --type=json -p='[
  {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"},
  {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-preferred-address-types=InternalIP,Hostname,ExternalIP"},
  {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--metric-resolution=15s"}
]'
kubectl -n kube-system rollout status deploy/metrics-server --timeout=180s
```

**Verification gate — do not proceed until both return numbers:**

```bash
kubectl top nodes
kubectl top pods -n civicpulse
kubectl get apiservice v1beta1.metrics.k8s.io -o jsonpath='{.status.conditions[0].status}'   # True
```

`--metric-resolution=15s` is set explicitly rather than left at the default because it is one of the
four terms in the lag budget (§5) and you want to be able to say *"I set it, here is what it cost."*

Commit the patched args to `k8s/base/` or to a `scripts/cluster-up.sh` so the cluster is
reproducible. An undocumented `kubectl patch` typed once at 2 a.m. is not infrastructure.

---

## 2. Resource requests — the denominator (Rubric H, 2 marks)

```yaml
resources:
  requests:                 # ← what the SCHEDULER reserves and what the HPA divides by
    cpu: 200m
    memory: 256Mi
  limits:                   # ← what the KERNEL enforces (cgroup)
    cpu: "1"
    memory: 512Mi
```

| Concept | Meaning | Consequence of omitting |
|---|---|---|
| `requests.cpu` | scheduling reservation **and the HPA denominator** | HPA shows `<unknown>/60%` and never scales |
| `limits.cpu` | CFS quota; exceeding it causes **throttling**, not eviction | one noisy pod starves its node-mates |
| `requests.memory` | scheduling reservation | overcommit ⇒ node pressure ⇒ random evictions |
| `limits.memory` | hard cap; exceeding it is **OOMKill** | a memory leak takes the node, not the pod |

**QoS class:** requests ≠ limits ⇒ **Burstable**. State this and why we did not choose Guaranteed
(requests == limits): Guaranteed gives the best eviction protection but removes all headroom, so
every transient spike throttles and the HPA's utilisation signal becomes a square wave. Burstable
is correct for a bursty HTTP workload and is what makes the 60% target meaningful.

**CPU utilisation arithmetic, spelled out** — this is the sentence to have ready at viva:

```
target 60% of requests.cpu (200m) = 120m per pod
current usage across 2 pods = 340m  ⇒ average 170m ⇒ 170/200 = 85%
desiredReplicas = ceil(currentReplicas × currentMetric / targetMetric)
                = ceil(2 × 85 / 60) = ceil(2.83) = 3
```

That formula is the entire HPA algorithm. Write it in `docs/ENGINEERING-NOTES.md` and be able to
apply it to a number the examiner invents on the spot.

**Tolerance:** the HPA ignores deviations under 10% by default
(`--horizontal-pod-autoscaler-tolerance=0.1`). At a 60% target, nothing happens between 54% and
66%. Teams see "utilisation is 63%, why no scale-up?" and assume a bug. Know the number.

---

## 3. The HPA manifest

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: {name: backend-hpa, namespace: civicpulse}
spec:
  scaleTargetRef: {apiVersion: apps/v1, kind: Deployment, name: backend}
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource: {name: cpu, target: {type: Utilization, averageUtilization: 60}}
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300      # §3.3 — flapping is expensive
      policies:
        - {type: Percent, value: 50, periodSeconds: 60}    # at most halve per minute
        - {type: Pods,    value: 2,  periodSeconds: 60}
      selectPolicy: Min                    # the most conservative policy wins on the way down
    scaleUp:
      stabilizationWindowSeconds: 0        # §3.3 — users are waiting
      policies:
        - {type: Percent, value: 100, periodSeconds: 30}   # double every 30s
        - {type: Pods,    value: 4,   periodSeconds: 30}
      selectPolicy: Max                    # the most aggressive policy wins on the way up
```

**`selectPolicy` asymmetry is the whole design.** `Max` on the way up (grab capacity fast, users are
waiting), `Min` on the way down (release it slowly, a scale-down that was wrong costs a cold start
and a latency spike). The 300 s stabilisation window means scale-down uses the **highest**
recommendation from the last five minutes — so a brief traffic trough cannot collapse the fleet.
Scale-up's 0 s window means it acts on the newest reading immediately.

**`maxReplicas: 10` interacts with the DB connection pool** — see `05-DATA-LAYER.md §1`.
10 replicas × (`pool_size` 5 + `max_overflow` 2) = 70 connections against a default
`max_connections=100`. That arithmetic must appear in the notes; it is the most likely
cross-cutting question in the viva because it joins two rubric sections.

---

## 4. Load generation

### 4.1 `load/k6-script.js` — the scale-out driver

```javascript
import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const created = new Counter('complaints_created');
const BASE = __ENV.BASE_URL || 'http://civicpulse.localhost';

export const options = {
  scenarios: {
    rampup: {
      executor: 'ramping-arrival-rate',   // ← ARRIVAL rate, not VUs. See note below.
      startRate: 5, timeUnit: '1s',
      preAllocatedVUs: 50, maxVUs: 400,
      stages: [
        { target: 5,   duration: '1m'  },   // baseline — proves 2 replicas is enough at rest
        { target: 120, duration: '2m'  },   // ramp — this is the interval the chart is about
        { target: 120, duration: '4m'  },   // plateau — let the HPA converge and settle
        { target: 5,   duration: '1m'  },   // drop — proves the 300s scaleDown window
        { target: 5,   duration: '6m'  },   // hold — watch it NOT flap, then scale in
      ],
    },
  },
  thresholds: {
    http_req_failed:   ['rate<0.01'],
    http_req_duration: ['p(95)<3000'],
  },
};

const CORPUS = JSON.parse(open('./corpus.json'));   // 20 complaints, Zipf-weighted repeats

export default function () {
  const body = CORPUS[Math.floor(Math.random() ** 2 * CORPUS.length)];  // skew → cache hits
  const r = http.post(`${BASE}/api/complaints`, JSON.stringify(body),
                      { headers: { 'Content-Type': 'application/json' } });
  check(r, { 'created': (x) => x.status === 201 });
  if (r.status === 201) created.add(1);
  http.get(`${BASE}/api/stats`);
}
```

**Use `ramping-arrival-rate`, not `ramping-vus`.** With VUs, a slowing system *reduces* offered
load (each VU waits for its response), so the load generator quietly backs off exactly when you
want pressure — and your replicas-vs-load chart becomes a chart of your own closed-loop
feedback rather than of the HPA. Arrival-rate holds requests-per-second constant regardless of
response time, which is what "offered load" means in the chart §4.3 requires. **This distinction is
worth a sentence in the notes** — it is the difference between a load test and a load-shaped
coincidence.

**The `Math.random() ** 2` skew** produces a Zipf-ish repeat distribution, which is what a real
complaint stream looks like (*"a burst main gets reported by nine neighbours"*, §2.5) and what
makes the triage-cache hit rate in `08-AI-TRIAGE.md §6` a realistic number rather than a
uniform-random artefact.

**Pin `TRIAGE_PROVIDER`** during the load test. With `llm` you are load-testing Groq's free tier and
will be rate-limited within seconds, so the run measures the fallback path. Run the scale-out test
with `TRIAGE_PROVIDER=simulated` (CPU-bound, deterministic, no external quota) and say so in the
chart caption. Then run a **separate, short** `llm` run purely to capture real triage latency
percentiles for `docs/TRIAGE.md §5`. Two runs, two purposes, both honest.

### 4.2 Running it and capturing the HPA

Three terminals, all recorded:

```bash
# T1 — the watcher (this file IS the deliverable)
kubectl -n civicpulse get hpa backend-hpa -w | ts '%H:%M:%S' | tee docs/evidence/hpa-watch.txt

# T2 — replica-count sampler, 5s cadence, for the chart
while true; do
  printf '%s %s %s\n' "$(date +%s)" \
    "$(kubectl -n civicpulse get deploy backend -o jsonpath='{.status.readyReplicas}')" \
    "$(kubectl -n civicpulse get hpa backend-hpa -o jsonpath='{.status.currentMetrics[0].resource.current.averageUtilization}')"
  sleep 5
done | tee docs/evidence/hpa-samples.txt

# T3 — the load
k6 run --summary-export=docs/evidence/k6-summary.json load/k6-script.js
```

Expected shape of `hpa-watch.txt`:

```
NAME          REFERENCE          TARGETS    MINPODS  MAXPODS  REPLICAS  AGE
backend-hpa   Deployment/backend 3%/60%     2        10       2         12m
backend-hpa   Deployment/backend 41%/60%    2        10       2         13m
backend-hpa   Deployment/backend 88%/60%    2        10       2         13m   ← breach observed
backend-hpa   Deployment/backend 88%/60%    2        10       3         13m   ← decision
backend-hpa   Deployment/backend 71%/60%    2        10       4         14m
backend-hpa   Deployment/backend 58%/60%    2        10       5         15m   ← converged
backend-hpa   Deployment/backend 9%/60%     2        10       5         20m   ← load dropped
backend-hpa   Deployment/backend 9%/60%     2        10       2         25m   ← 300s window elapsed
```

**If you capture nothing else, capture the two lines where TARGETS breaches 60% and where
REPLICAS first changes.** The timestamp delta between them is the first term of your lag answer
(§5) and the number §5.2 question 5 asks for.

### 4.3 The chart (Rubric H — *"a chart of replicas against offered load over time"*)

```python
# load/plot_hpa.py
import json, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

t0 = None; ts, reps, util = [], [], []
for line in open("docs/evidence/hpa-samples.txt"):
    s, r, u = line.split()
    t0 = t0 or int(s)
    ts.append(int(s) - t0); reps.append(int(r)); util.append(int(u or 0))

offered = [...]   # from k6: stage-derived RPS, or parse the summary's iteration timeline

fig, ax1 = plt.subplots(figsize=(11, 5))
ax1.plot(ts, offered, label="offered load (req/s)", linewidth=2)
ax1.set_xlabel("seconds since start"); ax1.set_ylabel("offered load (req/s)")
ax2 = ax1.twinx()
ax2.step(ts, reps, where="post", label="ready replicas", linewidth=2, linestyle="--")
ax2.plot(ts, util, label="CPU utilisation %", alpha=0.5)
ax2.axhline(60, linestyle=":", label="HPA target 60%")
ax2.set_ylabel("replicas / utilisation %")
fig.legend(loc="upper left", bbox_to_anchor=(0.1, 0.95))
plt.title("CivicPulse backend: offered load vs HPA replica count")
plt.tight_layout(); plt.savefig("docs/evidence/hpa-replicas-vs-load.png", dpi=150)
```

Chart requirements for full marks:
- **One shared time axis.** Two side-by-side charts do not show *lag*, and lag is the point.
- **Annotate the lag** with an arrow between "load crosses threshold" and "replicas increase".
- **Show the scale-down too.** The flat 5 minutes before replicas fall is the visible proof that
  `stabilizationWindowSeconds: 300` is doing exactly what you configured.
- **Caption with the run conditions:** date, `TRIAGE_PROVIDER`, cluster (k3d, N agents), image SHA.

---

## 5. HPA lag, decomposed in seconds (§5.2 question 5 · Rubric H)

> *"How many seconds between offered load rising and replicas rising? Where did the time go, and
> what would reduce it?"* — Generic answers score zero. Measure yours; the table below is the
> structure, and the numbers are typical, not yours.

| # | Term | Typical | Why it exists | What reduces it |
|---|---|---|---|---|
| 1 | cAdvisor housekeeping | 0–10 s | kubelet samples container CPU on an interval before metrics-server can read it | `--housekeeping-interval` (node-level, rarely worth touching) |
| 2 | metrics-server scrape | 0–15 s | `--metric-resolution=15s`; your load may arrive just after a scrape | lower resolution (costs API-server load) |
| 3 | HPA control-loop sync | 0–15 s | `--horizontal-pod-autoscaler-sync-period=15s` on the controller-manager | lower period (managed clusters usually forbid) |
| 4 | Tolerance band | 0 s–∞ | no action between 54% and 66% at a 60% target | lower `--horizontal-pod-autoscaler-tolerance` |
| 5 | Scheduling | 1–3 s | scheduler binds the new pod | pre-provisioned "pause pod" over-provisioning with a low PriorityClass |
| 6 | Image pull | 0 s–2 min | cached on the node ⇒ ~0; cold node ⇒ full pull | pre-pull via DaemonSet; smaller images (§3.1's 60 MB rule pays off here) |
| 7 | initContainer (`alembic upgrade head`) | 2–5 s | runs before the app container on every new pod | it is a no-op once at head — but it still costs a container start. Could be moved to a one-shot Job at the cost of the coupling argument in `13-KUBERNETES.md §4.1` |
| 8 | App start + `startupProbe` first success | 4–10 s | Python import, pool construction; probe polls every 2 s | faster boot; `periodSeconds: 1` on the startupProbe |
| 9 | `readinessProbe` first success | 0–5 s | `periodSeconds: 5` | lower period (more probe load) |
| 10 | Endpoint → kube-proxy propagation | 1–5 s | EndpointSlice write, watch, iptables/IPVS update on every node | EndpointSlices already help; nothing much at this scale |
| | **Total observed** | **45–90 s** | | |

**The 3–5 sentences §3.3 asks for, structured:** *"Offered load crossed the 60% threshold at
T+0; replicas moved at T+62s. Roughly 25 s of that was the metrics pipeline (cAdvisor
housekeeping plus a 15 s metrics-server resolution plus a 15 s HPA sync period, each of which can
land anywhere in its interval), ~5 s was scheduling and the migration initContainer, and ~20 s was
application startup until the first successful readiness probe; the remainder was endpoint
propagation. The pipeline terms can be halved by lowering `--metric-resolution` and the sync
period at the cost of API-server load; the startup term is bounded below by Python import time and
pool construction. **The conclusion that matters is that autoscaling is a minute-scale control
loop, so it absorbs sustained load growth but cannot absorb a one-second spike — that is what
`minReplicas`, request queuing and capacity planning are for.**"*

That last sentence is the learning outcome §3.3 says *"noticing it yourself"* is about. Say it.

---

## 6. Zero-downtime rolling update (bonus +4)

```javascript
// load/k6-rollout.js
export const options = {
  scenarios: { steady: { executor: 'constant-arrival-rate', rate: 40, timeUnit: '1s',
                         duration: '3m', preAllocatedVUs: 60, maxVUs: 200 } },
  thresholds: {
    http_req_failed: ['rate==0'],                 // ← ZERO. Not <0.01. The bonus says zero.
    'http_req_duration{expected_response:true}': ['p(99)<5000'],
  },
};
export default function () { check(http.get(`${__ENV.BASE_URL}/api/stats`), {'200': r => r.status === 200}); }
```

```bash
k6 run load/k6-rollout.js &                 # runs for 3 minutes
sleep 20
kubectl -n civicpulse set image deploy/backend backend=ghcr.io/ORG/civicpulse-backend:$NEW_SHA
kubectl -n civicpulse rollout status deploy/backend --timeout=300s
wait                                        # k6 exits non-zero if ANY request failed
echo "k6 exit=$?"                           # 0 = zero-downtime proven, mechanically
```

Tee to `docs/evidence/zero-downtime-rollout.txt` and record the terminal for the video. The
threshold makes this **pass/fail rather than eyeballed**, which is the difference between the bonus
and a claim.

**If it fails, the cause is almost always one of four**, in order of likelihood: (1) `preStop` missing
or too short, (2) `terminationGracePeriodSeconds` shorter than preStop + drain, (3) shell-form
`CMD` so SIGTERM never reaches uvicorn, (4) `maxUnavailable` not 0. Check them in that order —
and if you spend more than an hour here, this is a strong candidate for §5.2 question 8.

---

## 7. VPA — recommender mode (Rubric H, 3 marks)

### 7.1 Install

```bash
git clone --depth 1 https://github.com/kubernetes/autoscaler.git /tmp/autoscaler
cd /tmp/autoscaler/vertical-pod-autoscaler && ./hack/vpa-up.sh
kubectl -n kube-system get pods | grep vpa     # recommender, updater, admission-controller
```

VPA needs metrics-server (already installed) and generates its own webhook certs. On k3d the
admission controller occasionally fails to register; since we run `updateMode: "Off"` we only
strictly need the **recommender**, so a failing admission controller does not block the deliverable
— note that in the runbook rather than fighting it.

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata: {name: backend-vpa, namespace: civicpulse}
spec:
  targetRef: {apiVersion: apps/v1, kind: Deployment, name: backend}
  updatePolicy: {updateMode: "Off"}          # ← recommend only. Do not evict.
  resourcePolicy:
    containerPolicies:
      - containerName: backend
        controlledResources: ["cpu","memory"]
        minAllowed: {cpu: 50m,  memory: 128Mi}
        maxAllowed: {cpu: "2",  memory: 1Gi}
      - containerName: migrate
        mode: "Off"                          # do not recommend for a short-lived initContainer
```

`kubeconform` does not know the VPA CRD by default — see `15-CICD.md §3.6` for the schema
location flag. That is a 20-minute trap.

### 7.2 The five-step loop (§3.3, verbatim requirement)

| Step | Command | Artefact |
|---|---|---|
| **1. Record the guess** | `git log -1 --format=%H -- k8s/base/backend.yaml`; note `cpu: 200m, memory: 256Mi` | `docs/evidence/vpa-step1-guess.txt` |
| **2. Run load** | `k6 run load/k6-script.js` (full 14-minute profile — the recommender needs history) | `k6-summary.json` |
| **3. Describe** | `kubectl -n civicpulse describe vpa backend-vpa \| tee docs/evidence/vpa-describe-run1.txt` | Target / Lower Bound / Upper Bound / Uncapped Target |
| **4. Update requests** | edit `k8s/base/backend.yaml` to the **Target**, commit alone with the recommendation quoted in the body | a commit whose message cites the numbers |
| **5. Re-run and report** | `k6 run …` again, `describe` again, capture `hpa -w` again | `vpa-describe-run2.txt`, `hpa-watch-run2.txt` |

Expected `describe` output:

```
Recommendation:
  Container Recommendations:
    Container Name:  backend
    Lower Bound:   cpu: 137m   memory: 262144k
    Target:        cpu: 310m   memory: 314572k
    Uncapped Target: cpu: 310m memory: 314572k
    Upper Bound:   cpu: 812m   memory: 524288k
```

**Read the four numbers correctly** — this is a likely viva question:

| Field | Meaning |
|---|---|
| **Target** | What the recommender would set if it could. The number you copy into the manifest. |
| **Lower Bound** | Below this, the VPA is confident the pod is under-provisioned; in `Auto` it would evict upward. |
| **Upper Bound** | Above this, resources are confidently wasted. |
| **Uncapped Target** | Target ignoring `maxAllowed`. If Target < Uncapped Target, **your `maxAllowed` is clipping the recommendation** — an important tell. |

### 7.3 What to report about the HPA after the update (step 5)

The commit message and notes must answer: *what changed?* The mechanism, so you can predict it
before you measure it:

Raising `requests.cpu` from 200m to 310m **raises the denominator**. The same absolute CPU draw
now computes to a *lower* utilisation percentage:

```
before: 170m used / 200m requested = 85%   ⇒ desired = ceil(2 × 85/60) = 3
after:  170m used / 310m requested = 55%   ⇒ desired = ceil(2 × 55/60) = 2   (and 55% is inside the tolerance band)
```

So the observable outcomes are: **the HPA scales later and to fewer replicas**, each pod is bigger,
total reserved CPU at a given load is roughly similar, the scheduler may fit fewer pods per node,
and p95 latency under the plateau typically **improves** because each pod has more headroom
before CFS throttling. Report your actual numbers against that prediction; where they disagree,
that disagreement is the interesting part of the write-up.

### 7.4 Why `Off`, and the `Auto` failure mode (§5.2 question 6)

> §3.3 spells out the loop; your job is to say it precisely and to name the resulting oscillation.

```
       load rises
           │
           ▼
   HPA sees utilisation = usage / request  ── high ──▶ adds pods
           │                                              │
           │                                       per-pod usage falls
           ▼                                              │
   VPA (Auto) sees per-pod usage and raises `request` ◀────┘
           │
           ▼
   utilisation = usage / LARGER request  ── lower ──▶ HPA removes pods
           │                                              │
           │                                       per-pod usage rises
           ▼                                              │
   VPA raises `request` again  ◀──────────────────────────┘
```

**Both controllers act on the same signal — CPU — and one of them can move the denominator of
the other's ratio.** That is the definition of a control-loop conflict. Consequences in `Auto`:
sustained replica oscillation, and — worse — VPA in `Auto` **evicts pods to apply new requests**,
so the fleet churns during exactly the traffic event you were trying to survive. A PDB
(`minAvailable: 1`) bounds but does not prevent the churn.

**The industrial answers, all worth naming:**
- **VPA `Off` + human review** — what we ship, and what §3.3 calls *"the current industrial
  practice."*
- **HPA on a non-resource metric** (RPS, queue depth, p95 latency via `type: Pods` or `External`
  with Prometheus Adapter/KEDA) while VPA owns CPU/memory. The loops then act on **different**
  signals and no longer fight. This is the genuinely correct answer at scale — say it, because it
  shows you understand *why* the conflict exists rather than just *that* it does.
- **VPA `Initial`** — sets requests only at pod creation, never evicts. A middle ground; note it.

> One-sentence viva answer: *"They fight because the HPA's metric is a ratio whose denominator the
> VPA controls; running VPA in recommender mode removes it from the loop and puts a human at the
> point where the two concerns meet."*

---

## 8. Gate-7 checklist

- [ ] `kubectl top pods -n civicpulse` returns numbers
- [ ] `kubectl get hpa -n civicpulse` shows `N%/60%`, never `<unknown>/60%`
- [ ] `docs/evidence/hpa-watch.txt` shows REPLICAS 2 → ≥4 → back to 2
- [ ] `docs/evidence/hpa-replicas-vs-load.png` — one time axis, lag annotated, target line drawn
- [ ] `docs/evidence/k6-summary.json` committed with thresholds passing
- [ ] `docs/evidence/vpa-describe-run1.txt` and `run2.txt` with all four bound values
- [ ] `k8s/base/backend.yaml` requests updated in **its own commit**, message quoting the Target
- [ ] `docs/evidence/zero-downtime-rollout.txt` with `http_req_failed rate==0` passing (bonus)
- [ ] ENGINEERING-NOTES Q5 has a **per-term seconds table**, not a paragraph of prose
- [ ] ENGINEERING-NOTES Q6 names the oscillation **and** the eviction behaviour of `Auto`
