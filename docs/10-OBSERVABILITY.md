# 10 — OBSERVABILITY (`/metrics` · Prometheus · Grafana · OTel)

> **Owner:** DEV-A · **Day:** 9 · **Rubric:** C1 (part), F6 (2), J; **Bonus:** Prometheus+Grafana
> (+2), OpenTelemetry (+2)
> Three signals, three jobs: **logs** answer *what happened to this one request*, **metrics** answer
> *what is happening to all requests*, **traces** answer *where the time went*.

---

## 1. The required series (§2.2: *request count, request latency histogram, triage latency, fallback counter*)

```python
# backend/app/obs/metrics.py
HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests",
                        ["method", "path_template", "status"])
HTTP_DURATION = Histogram("http_request_duration_seconds", "HTTP latency",
                          ["method", "path_template"],
                          buckets=(.005,.01,.025,.05,.1,.25,.5,1,2.5,5,10))
TRIAGE_SECONDS = Histogram("triage_duration_seconds", "Triage latency",
                           ["provider", "outcome"],           # outcome: ok|fallback|cached
                           buckets=(.05,.1,.25,.5,1,2,5,10,15))
TRIAGE_FALLBACK = Counter("triage_fallback_total", "Triage fallbacks",
                          ["provider", "error_class"])
TRIAGE_CACHE_HITS   = Counter("triage_cache_hits_total", "Triage cache hits")
TRIAGE_CACHE_MISSES = Counter("triage_cache_misses_total", "Triage cache misses")
RATELIMIT_REJECTS   = Counter("ratelimit_rejections_total", "429s issued")
INFLIGHT = Gauge("http_requests_inflight", "In-flight requests")
APP_INFO = Gauge("app_info", "Build info", ["version", "provider"])
```

### 1.1 Bucket choices are engineering, not defaults

- **HTTP buckets top out at 10 s** because a request that takes longer has already blown the
  triage budget (`08-AI-TRIAGE.md §5`); anything above 10 s is `+Inf` and that is the right
  granularity — you do not need to distinguish 40 s from 60 s, you need to know it happened.
- **Triage buckets start at 50 ms** because `RuleBasedTriage` completes in single-digit ms and would
  otherwise pile into the first bucket, making the fallback path invisible. They end at **15 s**,
  above the 12 s total budget, so a budget breach is visible rather than clipped.
- The two histograms deliberately share no bucket layout. Copying HTTP buckets onto a
  10-second-scale metric is the most common way to end up with a p95 you cannot read.

### 1.2 The cardinality rule — `path_template`, never the raw path

`/api/complaints/018f3a2c-…` as a label value creates **one new time series per complaint**.
At 10,000 complaints that is 10,000 series × 11 buckets × 4 label combinations — a Prometheus
instance eaten by its own instrumentation. Always:

```python
route = request.scope.get("route")
path_template = getattr(route, "path", "unmatched")   # "/api/complaints/{id}"
```

`"unmatched"` (not the raw path) for 404s, otherwise a scanner probing random URLs manufactures
unbounded cardinality on your behalf. That sentence — *"a 404 scanner is a cardinality attack"* — is
a good viva answer and a real incident class.

Also excluded from labels: `X-Request-ID`, user IP, complaint text, query strings. Those belong in
logs, which are indexed differently and retained differently.

### 1.3 `/metrics` hygiene

| Rule | Reason |
|---|---|
| Excluded from `HTTP_DURATION` | A scrape measuring itself pollutes the latency distribution |
| Not routed through the Ingress | `13-KUBERNETES.md §7` — internal Service port only |
| Not rate-limited | Limiting a scrape produces gaps that look like an outage |
| `multiprocess` mode **not** used | One uvicorn worker per container (`06-BACKEND-CORE.md §6`), so the default single-process registry is correct. With `--workers 4` you would need `PROMETHEUS_MULTIPROC_DIR` and a shared mmap dir — note this as the reason the single-worker choice simplifies two things at once |
| `Content-Type: text/plain; version=0.0.4; charset=utf-8` | Prometheus text exposition format, exactly as §2.2 requires |

---

## 2. Metrics ↔ `/api/meta/providers` — one source of truth

`/api/meta/providers` does **not** keep its own counters. It reads the Prometheus registry:

```python
hits   = REGISTRY.get_sample_value("triage_cache_hits_total") or 0.0
misses = REGISTRY.get_sample_value("triage_cache_misses_total") or 0.0
rate   = round(hits / (hits + misses), 3) if (hits + misses) else 0.0
```

Two counters would eventually disagree, and a dashboard that disagrees with an API is worse than
either alone. This is the same "one source of truth" argument §2.1 makes about status transitions,
applied to telemetry.

---

## 3. Log ↔ metric ↔ trace correlation

| Signal | Carries | Join key |
|---|---|---|
| Log line | `request_id`, `complaint_id`, `provider`, `error_class`, `latency_ms` | `request_id` |
| Metric | `path_template`, `status`, `provider`, `outcome` | none (aggregate by design) |
| Trace (bonus) | span tree with `trace_id` | `trace_id` logged alongside `request_id` |
| HTTP response | `X-Request-ID` header **and** `error.request_id` in the body | `request_id` |

A citizen quotes the `request_id` from the error page; the operator runs
`kubectl logs -l app=backend --since=1h | jq 'select(.request_id=="…")'` and sees every line from
that request across whichever pod served it. That flow is the answer to *"how do you debug a
production 500?"* and it should be in `docs/RUNBOOK.md §Read the logs`.

---

## 4. The four alert conditions worth naming (even without an Alertmanager)

Documented in `docs/RUNBOOK.md` with the PromQL, so *"what to do when triage starts failing"*
(Rubric J) has a trigger, not just a procedure.

```promql
# 1. Triage is degrading — more than 20% of triages falling back over 5 minutes
sum(rate(triage_fallback_total[5m]))
  / sum(rate(triage_duration_seconds_count[5m])) > 0.2

# 2. The provider is slow — p95 above 5s
histogram_quantile(0.95, sum by (le,provider) (rate(triage_duration_seconds_bucket[5m]))) > 5

# 3. The cache stopped working — hit rate collapsed below 10%
sum(rate(triage_cache_hits_total[10m]))
  / sum(rate(triage_cache_hits_total[10m]) + rate(triage_cache_misses_total[10m])) < 0.1

# 4. We are shedding citizens — sustained 429s
sum(rate(ratelimit_rejections_total[5m])) > 1
```

Each maps to a runbook action: (1) check `/api/meta/providers.recent` for `error_class`, consider
`TRIAGE_PROVIDER=ollama`; (2) check the provider status page and the org-level rate limit;
(3) check Redis memory and `maxmemory-policy` evictions; (4) check whether it is an attack or a
too-tight limit, and raise `RATELIMIT_REQUESTS` via ConfigMap rather than code.

---

## 5. Prometheus + Grafana (bonus +2)

Two ways, pick by time available.

**Compose (fast):** add `prometheus` and `grafana` services on the `edge` network with a static
scrape config targeting `backend:8000/metrics`, and a provisioned dashboard JSON committed at
`docs/dashboards/civicpulse.json`.

**Kubernetes (better):** `kube-prometheus-stack` via Helm, plus a `ServiceMonitor`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata: {name: backend, namespace: civicpulse, labels: {release: kps}}
spec:
  selector: {matchLabels: {app: backend}}
  endpoints: [{port: http, path: /metrics, interval: 15s}]
```

`kubeconform` will fail on the `ServiceMonitor` CRD unless you add the CRD schema location —
see `15-CICD.md §3.6`. That is a real 20-minute trap; note it here so nobody rediscovers it.

**Dashboard panels (six, one screenshot for `docs/evidence/grafana.png`):**

1. Request rate by status — `sum by (status) (rate(http_requests_total[1m]))`
2. Latency p50/p95/p99 — `histogram_quantile(…)` over `http_request_duration_seconds_bucket`
3. Triage latency by provider and outcome — stacked
4. **Fallback rate** — the single most important panel in this system, since it is the health of the
   thesis: *the reader is replaceable and the system does not fall over*
5. Cache hit rate — `triage_cache_hits_total / (hits + misses)`
6. Replicas vs CPU utilisation — overlaid with the HPA target line at 60%, which makes the
   `14-LOAD-AUTOSCALING.md` chart reproducible from Grafana instead of hand-plotted

---

## 6. OpenTelemetry tracing (bonus +2)

Required span chain (§Bonus: *"frontend → backend → LLM call"*):

```
frontend fetch  (browser, @opentelemetry/sdk-trace-web + fetch instrumentation)
└── HTTP POST /api/complaints            [server span]
    ├── triage.cache.get                 [internal]
    ├── triage.llm.call                  [client]  ← attrs: provider, model, attempt, outcome
    │   └── HTTP POST api.groq.com/...   [client, auto-instrumented httpx]
    ├── triage.fallback.rules            [internal, only on the fallback path]
    └── db.insert complaints             [client, auto-instrumented sqlalchemy]
```

Wiring: `opentelemetry-instrumentation-fastapi`, `-httpx`, `-sqlalchemy`, `-redis`; OTLP exporter
to a `jaeger` or `otel-collector` container on `edge`. Propagate `traceparent` from the browser; the
frontend must send it through the nginx proxy (`proxy_set_header traceparent $http_traceparent;`).

**Attribute hygiene, non-negotiable:** never put complaint text, `reporter_contact` or the API key
on a span. Spans leave your process and land in a system with different access controls. This is
ADR-0004's scope applied to telemetry — and it is exactly the kind of connection that reads well at
viva.

**Bind the trace id into the log formatter** so `trace_id` sits beside `request_id` in every JSON
line. Without that, you have two correlation systems that do not correlate.

---

## 7. Tests

| Test | Asserts |
|---|---|
| `test_metrics_exposes_required_series` | all four §2.2-mandated names present in the exposition |
| `test_metrics_path_template_label` | a request to `/api/complaints/{uuid}` produces `path_template="/api/complaints/{id}"` and **not** the uuid |
| `test_404_labelled_unmatched` | random path ⇒ `path_template="unmatched"` |
| `test_metrics_not_self_measured` | `/metrics` absent from `http_request_duration_seconds` |
| `test_fallback_counter_increments` | one fallback ⇒ `triage_fallback_total{error_class="…"} == 1` |
| `test_cache_counters_match_meta_endpoint` | registry values equal `/api/meta/providers.cache` |
| `test_content_type_is_prometheus_text` | `version=0.0.4` in the header |
| `test_no_pii_in_labels` | seeded complaint text absent from the whole exposition |
