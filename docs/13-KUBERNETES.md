# 13 — KUBERNETES (20 marks)

> **Owner:** DEV-B, DEV-A pairs on probes · **Days:** 9–10 · **Gate:** Gate 6 · **Rubric:** H (20)
> Cluster: **k3d** preferred over kind — see §9 for the NetworkPolicy reason.
> A managed cloud cluster *"is not required and earns no extra marks"* (§3.3).

---

## 1. Object inventory (§3.3, complete)

| Object | Name | Notes |
|---|---|---|
| Namespace | `civicpulse` | **never `default`** |
| Deployment | `backend` | ≥2 replicas, initContainer runs migrations |
| Deployment | `frontend` | ≥2 replicas |
| **StatefulSet** | `postgres` | `volumeClaimTemplates` → PVC. **A Deployment here is a marked error** |
| Deployment + PVC | `redis` | `strategy: Recreate` (see §4.2) |
| Service ×4 | `backend`, `frontend`, `postgres` (headless), `redis` | **ClusterIP only** |
| Ingress | `civicpulse` | `/` → frontend, `/api` → backend, one host |
| ConfigMap | `app-config` | non-secret configuration |
| Secret | `app-secrets` | **placeholders only in git** |
| HPA v2 | `backend-hpa` | `14-LOAD-AUTOSCALING.md` |
| VPA | `backend-vpa` | `updateMode: "Off"` |
| PDB | `backend-pdb` | `minAvailable: 1` |
| NetworkPolicy ×4 | default-deny + allows | §9 — not in the spec, shipped anyway (contradiction A13) |

## 2. Kustomize structure

```
k8s/
├── base/kustomization.yaml            # namespace: civicpulse, commonLabels, all resources
└── overlays/
    ├── dev/kustomization.yaml         # replicas 2, requests small, image :dev, ingress host localhost
    └── prod/kustomization.yaml        # replicas 3, VPA-derived requests, image :${SHA}
```

```yaml
# k8s/overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: civicpulse
resources: [../../base]
images:
  - name: ghcr.io/ORG/civicpulse-backend
    newTag: PLACEHOLDER_SHA          # CD replaces via `kustomize edit set image`
  - name: ghcr.io/ORG/civicpulse-frontend
    newTag: PLACEHOLDER_SHA
replicas:
  - {name: backend, count: 3}
  - {name: frontend, count: 2}
patches:
  - path: backend-resources.yaml      # the VPA-informed requests
  - path: ingress-host.yaml
configMapGenerator:
  - name: app-config
    behavior: merge
    literals: [APP_ENV=prod, TRUSTED_PROXY_HOPS=2, LOG_LEVEL=INFO]
```

`TRUSTED_PROXY_HOPS=2` in prod, `1` in dev — ingress-nginx **plus** the frontend nginx both
append to `X-Forwarded-For` (`09-CACHE-RATELIMIT.md §4.3`). Getting this wrong in the overlay
means every citizen shares one rate-limit bucket on the cluster but not in Compose, which is a
bug that only appears in the environment you demo.

**`kustomize edit set image` is how CD injects the SHA** — never `sed` on YAML. It is schema-aware
and it is what keeps §5.3's `:latest` deduction impossible by construction.

---

## 3. Postgres StatefulSet (Rubric H, part of 5 marks)

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata: {name: postgres, namespace: civicpulse}
spec:
  serviceName: postgres                  # headless Service — stable DNS postgres-0.postgres
  replicas: 1
  selector: {matchLabels: {app: postgres}}
  template:
    spec:
      terminationGracePeriodSeconds: 60          # let a checkpoint finish
      securityContext: {fsGroup: 999, runAsUser: 999, runAsNonRoot: true}
      containers:
        - name: postgres
          image: postgres:16.4-alpine
          env:
            - {name: POSTGRES_USER, valueFrom: {secretKeyRef: {name: app-secrets, key: POSTGRES_USER}}}
            - {name: POSTGRES_PASSWORD, valueFrom: {secretKeyRef: {name: app-secrets, key: POSTGRES_PASSWORD}}}
            - {name: POSTGRES_DB, valueFrom: {configMapKeyRef: {name: app-config, key: POSTGRES_DB}}}
            - {name: PGDATA, value: /var/lib/postgresql/data/pgdata}   # ← subdir, see below
          ports: [{name: pg, containerPort: 5432}]
          volumeMounts: [{name: pgdata, mountPath: /var/lib/postgresql/data}]
          readinessProbe:
            exec: {command: ["sh","-c","pg_isready -U $POSTGRES_USER -d $POSTGRES_DB"]}
            initialDelaySeconds: 5, periodSeconds: 5
          livenessProbe:
            exec: {command: ["pg_isready","-U","postgres"]}
            initialDelaySeconds: 30, periodSeconds: 10
          resources: {requests: {cpu: 250m, memory: 256Mi}, limits: {cpu: "1", memory: 1Gi}}
  volumeClaimTemplates:
    - metadata: {name: pgdata}
      spec: {accessModes: [ReadWriteOnce], resources: {requests: {storage: 2Gi}}}
```

**Why StatefulSet, in one viva-ready paragraph.** A Deployment's pods have random names and its
`volumes` block binds *one* PVC that all replicas would share — with `ReadWriteOnce` that means
only one pod can ever schedule, and on any node change the pod may come back bound to nothing.
A StatefulSet gives each replica a **stable ordinal identity** (`postgres-0`), a **stable DNS name**
(`postgres-0.postgres.civicpulse.svc.cluster.local`), and a PVC **named after that ordinal**
(`pgdata-postgres-0`) which is re-attached to the replacement pod. Deleting `postgres-0` therefore
returns the *same* disk to the *same* identity — which is precisely the demonstration Gate 6
requires and why §3.3 calls the Deployment version *"a marked error."*

**`PGDATA` points at a subdirectory** of the mount. On many storage classes the mount root
contains a `lost+found`, and Postgres refuses to initialise into a non-empty directory. This costs
people an hour; the fix is one env var.

---

## 4. Backend Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: {name: backend, namespace: civicpulse}
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate: {maxSurge: 1, maxUnavailable: 0}     # §3.3 — never dip below desired
  selector: {matchLabels: {app: backend}}
  template:
    metadata: {labels: {app: backend}}
    spec:
      terminationGracePeriodSeconds: 30
      securityContext: {runAsNonRoot: true, runAsUser: 10001, fsGroup: 10001,
                        seccompProfile: {type: RuntimeDefault}}
      initContainers:
        - name: migrate                                  # §05 3.3 — migrations here, not in main.py
          image: ghcr.io/ORG/civicpulse-backend:PLACEHOLDER_SHA
          command: ["alembic","upgrade","head"]
          envFrom: [{configMapRef: {name: app-config}}, {secretRef: {name: app-secrets}}]
          resources: {requests: {cpu: 50m, memory: 128Mi}, limits: {cpu: 500m, memory: 256Mi}}
      containers:
        - name: backend
          image: ghcr.io/ORG/civicpulse-backend:PLACEHOLDER_SHA
          ports: [{name: http, containerPort: 8000}]
          envFrom: [{configMapRef: {name: app-config}}, {secretRef: {name: app-secrets}}]
          resources:
            requests: {cpu: 200m, memory: 256Mi}      # ← MANDATORY or the HPA reads <unknown>
            limits:   {cpu: "1",  memory: 512Mi}
          startupProbe:
            httpGet: {path: /health, port: http}
            failureThreshold: 30
            periodSeconds: 2                           # 60-second boot budget
          livenessProbe:
            httpGet: {path: /health, port: http}       # ← MUST NOT depend on the database
            periodSeconds: 10, timeoutSeconds: 2, failureThreshold: 3
          readinessProbe:
            httpGet: {path: /ready, port: http}        # ← SHOULD depend on it
            periodSeconds: 5, timeoutSeconds: 3, failureThreshold: 2, successThreshold: 1
          lifecycle:
            preStop: {exec: {command: ["sh","-c","sleep 5"]}}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {drop: ["ALL"]}
          volumeMounts: [{name: tmp, mountPath: /tmp}]
      volumes: [{name: tmp, emptyDir: {}}]
```

### 4.1 The initContainer migration decision

Migrations run **before** the app container starts, in the same pod, from the **same image**, so the
schema version and the code version are the same artefact by construction. Two replicas both run
it; Alembic takes a Postgres advisory lock on the version table, so the second waits and then
finds `head` already applied. A Kubernetes `Job` was rejected: a Job and a rolling update race,
and the Job's completion is not a precondition of the new pods starting unless you add an
orchestration layer the assignment does not need.

### 4.2 Redis uses `strategy: Recreate`, not RollingUpdate

A `ReadWriteOnce` PVC cannot be attached to two pods at once, so a rolling update deadlocks: the
new pod cannot mount until the old one releases, and the old one is not terminated until the new
one is ready. `Recreate` accepts a few seconds of cache unavailability — which the degradation
path in `09-CACHE-RATELIMIT.md §3` already handles. Worth one line in the notes; it is a real
deadlock people hit and misdiagnose as a storage bug.

---

## 5. The three probes — the 4-mark block

| Probe | Path | Effect of failure | Depends on DB? | Tuning |
|---|---|---|---|---|
| `startupProbe` | `/health` | blocks liveness/readiness until first success; on exhaustion, **kills the pod** | no | `failureThreshold: 30 × periodSeconds: 2` = **60 s budget** |
| `livenessProbe` | `/health` | **restarts the container** | **no** | 10 s period, 3 failures = ~30 s to restart |
| `readinessProbe` | `/ready` | **removes the pod from Service endpoints** | **yes** | 5 s period, 2 failures = ~10 s to drain |

**Why the startup budget is 60 s and not 10:** cold start is image pull (cached after the first
node), Python import (~1–2 s), pool construction, and the initContainer's migration before any of
it. Under a CI runner's contended CPU that can exceed a naive `initialDelaySeconds`. §3.3 says it
outright: *"slow start is not failure — this is what stops restart loops on boot."* Without a
`startupProbe`, you must set `initialDelaySeconds` high enough for the worst cold start, which
then delays detection of a genuine hang by the same amount. The `startupProbe` decouples those
two numbers, and saying *that* sentence is the difference between reciting and understanding.

**The wiring-backwards blast radius** is in `06-BACKEND-CORE.md §5`. Have it ready; §3.3 flags it
as a viva topic.

**Frontend probes** use `/healthz` (the nginx `return 200`), not `/`, so a broken SPA bundle does
not mark the pod unready — nginx being up is exactly what the frontend's liveness means.

---

## 6. Zero-downtime rolling update (bonus +4, and Rubric H's `maxUnavailable: 0`)

The termination timeline is in `06-BACKEND-CORE.md §6`. The manifest side:

| Setting | Value | Why |
|---|---|---|
| `maxSurge` | 1 | one extra pod during the roll; capacity never dips |
| `maxUnavailable` | **0** | the roll cannot remove a pod before its replacement is Ready |
| `terminationGracePeriodSeconds` | 30 | must exceed `preStop` (5 s) + drain (5 s) + margin |
| `preStop` | `sleep 5` | lets endpoint removal propagate through kube-proxy on every node |
| `readinessProbe.successThreshold` | 1 | a pod counts as Ready on its first good `/ready` |
| `minReadySeconds` | 5 (optional) | guards against a pod that is Ready then immediately crashes |

**Demonstration** (`14-LOAD-AUTOSCALING.md §6`): run `k6 run load/k6-rollout.js` with a
`http_req_failed: ['rate==0']` threshold while `kubectl set image` rolls. k6 exits non-zero if a
single request fails, so the demo is **pass/fail, not eyeballed**. That is the difference between
claiming zero downtime and proving it.

---

## 7. Services and Ingress

```yaml
apiVersion: v1
kind: Service
metadata: {name: backend, namespace: civicpulse}
spec:
  type: ClusterIP                 # ← every service. NodePort/LoadBalancer on a DB is §5.3 −8
  selector: {app: backend}
  ports:
    - {name: http, port: 8000, targetPort: http}
---
apiVersion: v1
kind: Service
metadata: {name: postgres, namespace: civicpulse}
spec:
  clusterIP: None                 # headless — required by the StatefulSet for stable pod DNS
  selector: {app: postgres}
  ports: [{name: pg, port: 5432}]
```

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: civicpulse
  namespace: civicpulse
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "30"     # > the 12s triage budget
    nginx.ingress.kubernetes.io/enable-real-ip: "true"
spec:
  ingressClassName: nginx
  rules:
    - host: civicpulse.localhost
      http:
        paths:
          - {path: /api, pathType: Prefix, backend: {service: {name: backend,  port: {name: http}}}}
          - {path: /,    pathType: Prefix, backend: {service: {name: frontend, port: {name: http}}}}
```

Path ordering matters: `/api` is listed first and is more specific, so ingress-nginx matches it
before the catch-all. **`/metrics` is deliberately absent** — it is reachable only on the ClusterIP
Service, scraped in-cluster by Prometheus. Exposing `/metrics` publicly leaks your internal
topology, your traffic volume and your provider mix to anyone who curls it.

**Service-to-service DNS is `http://backend:8000`, never `localhost`.** §5.3 −8. The
`make lint-localhost` grep covers `k8s/` for exactly this.

---

## 8. ConfigMap / Secret split (Rubric H, 2 marks)

```yaml
apiVersion: v1
kind: ConfigMap
metadata: {name: app-config, namespace: civicpulse}
data:
  APP_ENV: "prod"
  LOG_LEVEL: "INFO"
  POSTGRES_HOST: "postgres"
  REDIS_URL: "redis://redis:6379/0"
  TRIAGE_PROVIDER: "llm"
  LLM_BASE_URL: "https://api.groq.com/openai/v1"
  LLM_MODEL: "llama-3.1-8b-instant"
  TRUSTED_PROXY_HOPS: "2"
---
apiVersion: v1
kind: Secret
metadata: {name: app-secrets, namespace: civicpulse}
type: Opaque
stringData:
  POSTGRES_USER: "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUES"
  POSTGRES_PASSWORD: "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUES"
  LLM_API_KEY: "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUES"
```

> §5.3: *an LLM API key in a committed Kubernetes manifest, **even base64-encoded**, is **−15**,
> because **base64 is encoding, not encryption**.*

`stringData` with visible placeholders is used on purpose: `data:` with base64 makes a committed
real secret *look* redacted to a careless reviewer. Plain placeholders make a mistake obvious to a
human, and `.gitleaks.toml`'s `k8s-secret-nonplaceholder` rule (`03-REPO-BOOTSTRAP.md §7`)
catches it mechanically.

Real values are injected at deploy time:
```bash
kubectl -n civicpulse create secret generic app-secrets \
  --from-literal=LLM_API_KEY="$LLM_API_KEY" \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -
```
from GitHub Secrets in CD. The honest next step, worth naming in ADR-0003 or the notes: External
Secrets Operator or Sealed Secrets, so the *reference* is in git and the *value* never is.

**`envFrom` vs individual `valueFrom`:** `envFrom` is used for bulk config, but note the failure
mode — a key in the Secret that collides with a ConfigMap key is silently overridden by whichever
source is listed later. Keep the namespaces of keys disjoint (config keys never appear in secrets)
and say so.

---

## 9. NetworkPolicy — not in the spec, ship it anyway (contradiction A13)

§3.3 never mentions `NetworkPolicy`, yet §3.2 marks network segmentation in Compose. Shipping
the Kubernetes equivalent shows you understood the *intent* rather than the *checklist*, and it is
the direct answer to *"how does your `internal: true` design translate to the cluster?"*

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: default-deny, namespace: civicpulse}
spec: {podSelector: {}, policyTypes: [Ingress, Egress]}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: postgres-allow-backend, namespace: civicpulse}
spec:
  podSelector: {matchLabels: {app: postgres}}
  policyTypes: [Ingress]
  ingress:
    - from: [{podSelector: {matchLabels: {app: backend}}}]
      ports: [{protocol: TCP, port: 5432}]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: backend-egress, namespace: civicpulse}
spec:
  podSelector: {matchLabels: {app: backend}}
  policyTypes: [Egress]
  egress:
    - to: [{podSelector: {matchLabels: {app: postgres}}}]
      ports: [{protocol: TCP, port: 5432}]
    - to: [{podSelector: {matchLabels: {app: redis}}}]
      ports: [{protocol: TCP, port: 6379}]
    - to: [{namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: kube-system}}}]
      ports: [{protocol: UDP, port: 53}, {protocol: TCP, port: 53}]   # DNS — forget this and nothing resolves
    - to: [{ipBlock: {cidr: 0.0.0.0/0, except: [10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16]}}]
      ports: [{protocol: TCP, port: 443}]                             # ← the hosted LLM, and ONLY the backend
```

The last rule is `internal: true` expressed in Kubernetes: **only the backend has egress, and only
to 443 outside the cluster RFC1918 ranges.** Frontend, postgres and redis have none. Identical
intent, two systems — put that sentence in ENGINEERING-NOTES Q7.

> **The caveat that must be written down, or the policy is theatre:** NetworkPolicy is enforced by
> the **CNI**, not by the API server. **kind's default CNI (kindnet) does not enforce it** — the
> objects apply cleanly and do nothing. k3d/k3s ships a policy controller that does enforce it.
> So: use **k3d**, or install Calico on kind, and **verify enforcement empirically** rather than
> assuming it:
> ```bash
> kubectl -n civicpulse exec deploy/frontend -- sh -c 'nc -z -w2 postgres 5432; echo exit=$?'   # expect exit=1
> kubectl -n civicpulse exec deploy/backend  -- sh -c 'nc -z -w2 postgres 5432; echo exit=$?'   # expect exit=0
> ```
> Tee both to `docs/evidence/netpol-enforcement.txt`. If your CNI does not enforce, **say so in the
> notes** — an accurate "this is declarative only on kindnet" is worth more than a false claim.

---

## 10. PDB and scheduling hygiene

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: backend-pdb, namespace: civicpulse}
spec: {minAvailable: 1, selector: {matchLabels: {app: backend}}}
```
PDB governs **voluntary** disruption only — `kubectl drain`, node upgrades, the VPA's evictor in
`Auto` mode. It does not protect against a node dying. Say that distinction; it is commonly
overstated. With `minAvailable: 1` and `replicas: 2`, a drain evicts one pod and waits.

Also ship (cheap, shows intent):
```yaml
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: ScheduleAnyway        # NOT DoNotSchedule on a 2-node k3d cluster
    labelSelector: {matchLabels: {app: backend}}
```
`ScheduleAnyway` matters: `DoNotSchedule` on a small local cluster leaves pods `Pending` and the
HPA demo silently fails to scale past the node count.

---

## 11. Gate-6 verification

```bash
kubectl -n civicpulse get all
kubectl -n civicpulse get sts postgres -o jsonpath='{.spec.volumeClaimTemplates[0].metadata.name}'; echo
kubectl -n civicpulse get svc -o custom-columns=NAME:.metadata.name,TYPE:.spec.type   # all ClusterIP
kubectl -n civicpulse get deploy backend -o jsonpath='{.spec.template.spec.containers[0].resources}'; echo
kubectl -n civicpulse get pod -l app=backend -o jsonpath='{.items[0].spec.containers[0].livenessProbe.httpGet.path}'; echo  # /health
kubectl -n civicpulse get pod -l app=backend -o jsonpath='{.items[0].spec.containers[0].readinessProbe.httpGet.path}'; echo # /ready
kustomize build k8s/overlays/prod | kubeconform -strict -summary -ignore-missing-schemas=false
kustomize build k8s/overlays/prod | grep -n ':latest' && echo "FAIL §5.3 −8" || echo "no :latest"
grep -rniE 'gsk_|AIza|BEGIN (RSA|EC) PRIVATE' k8s/ && echo "FAIL §5.3 −15" || echo "placeholders only"
kubectl -n civicpulse delete pod postgres-0
kubectl -n civicpulse wait --for=condition=ready pod/postgres-0 --timeout=180s
kubectl -n civicpulse exec postgres-0 -- psql -U civicpulse -tAc 'select count(*) from complaints'
```
