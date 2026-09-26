# RUNBOOK — CivicPulse

Commands a stranger can run at 3 a.m. Every command below was checked against this repo's real
files on branch `docs/runbook-and-viva-notes` (forked from `origin/dev`) — file:line citations are
real, not reconstructed from the design docs' prose. Where a citation differs from what a design
doc implies, that's noted rather than silently reconciled (`CLAUDE.md`'s "say so" rule).

Required reading before any of this: `docs/18-DOCS-EVIDENCE-VIVA.md §5` (this file exists to
satisfy that section), `13-KUBERNETES.md §7` (rollback mechanics), `15-CICD.md §7` (the same
rollback content, CI-focused), `17-SECURITY-SECRETS.md §3` (credential rotation).

---

## 1. Deploy

**Normal path — merge to `main`.** Every change reaches `main` via a reviewed PR from `dev`
(CLAUDE.md HARD rule 2 — never a direct push). Once merged, `.github/workflows/cd.yml` runs
automatically on `push: { branches: [main] }` (`cd.yml:12-13`):

1. `test` — re-runs the full CI suite (`cd.yml:26-28`, reuses `ci.yml` via `secrets: inherit`)
   against the merged result.
2. `build-push` — gated by `needs: test` (`cd.yml:31` — §5.3's −8 armour: never publish an image
   from code already known broken). Builds and pushes `backend`/`frontend` images tagged both
   `:${{ github.sha }}` and `:latest` (`cd.yml:51-53,64-66` — `:latest` is pushed for convenience
   browsing but never deployed, see §2 below), signs both with cosign (`cd.yml:78-82`).
3. `deploy-k8s` — gated by `needs: build-push` (`cd.yml:85` — never deploy an unpublished image).
   Verifies the cosign signature (`cd.yml:90-94`), applies secrets from GitHub Secrets
   (`cd.yml:102-110` — never from the repo), pins the prod overlay to **this commit's digest**
   (`cd.yml:111-117` — `kustomize edit set image ...@<digest>`, never a floating tag), applies
   the rendered manifests, waits on `rollout status` for the StatefulSet and both Deployments
   (`cd.yml:119-122`), then runs a smoke test through the Ingress (`cd.yml:123-130`).

**Manual path — deploy without waiting for `cd.yml`** (e.g. redeploying an already-built digest to
a second cluster, or the automated pipeline is down and you need this out now):

```bash
cd k8s/overlays/prod
kustomize edit set image \
  ghcr.io/<owner>/civicpulse-backend=ghcr.io/<owner>/civicpulse-backend@<digest> \
  ghcr.io/<owner>/civicpulse-frontend=ghcr.io/<owner>/civicpulse-frontend@<digest>
kubectl apply -k .
kubectl -n civicpulse rollout status statefulset/postgres --timeout=300s
kubectl -n civicpulse rollout status deployment/backend --timeout=300s
kubectl -n civicpulse rollout status deployment/frontend --timeout=300s
```

Never apply `kustomization.yaml` with a bare `:latest` or an unpinned tag — `kubectl apply -k .`
after `kustomize edit set image ...@<digest>` is what makes this safe; skipping the `edit set
image` step and applying the base as-is would deploy whatever `PLACEHOLDER_SHA` is checked into
`k8s/base/backend-deployment.yaml:30,40` (a deliberate placeholder, never a real deployable tag).

---

## 2. Roll back

Both mechanisms exist. Know which one you're reaching for before you type anything —
`13-KUBERNETES.md §7.3`'s decision table, reproduced here because this file is the one you open
at 3 a.m., not that one:

| Situation | Use |
|---|---|
| Production is down, users affected, cause unknown | **`rollout undo`** — restore service, diagnose after |
| Bad deploy identified, no active incident | **re-apply previous SHA/digest** — one mechanism, one source of truth |
| A database migration already ran as part of the bad deploy | **neither alone** — see the migration caveat below |

### 2.1 Imperative — the 3 a.m. answer

```bash
kubectl -n civicpulse rollout history deployment/backend
kubectl -n civicpulse rollout undo deployment/backend
kubectl -n civicpulse rollout status deployment/backend --timeout=120s
kubectl -n civicpulse get deploy backend -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
```

Under 30 seconds, no repository access, no CI run, no approval — it walks the Deployment's own
ReplicaSet history (`revisionHistoryLimit`, default 10). Same four commands for `frontend`
(`deployment/frontend`).

**Its weakness, and you must know it before you run it:** the cluster is now running something
the repository does not describe. The next `kubectl apply -k .` (or a GitOps controller syncing)
**re-applies the broken version** — this buys time, it does not fix state.

### 2.2 Declarative — the correct answer once the fire is out

```bash
PREV=$(git rev-parse HEAD~1)
cd k8s/overlays/prod
kustomize edit set image \
  ghcr.io/<owner>/civicpulse-backend=ghcr.io/<owner>/civicpulse-backend:$PREV
git commit -am "revert(deploy): pin backend to $PREV after incident $(date -u +%F)"
git push   # → triggers cd.yml → full pipeline → deploy
```

Slower (a full CI/CD run), auditable, reviewable, and leaves git and the cluster in agreement.

### 2.3 The migration caveat

If a schema migration already ran as part of the deploy you're rolling back (the backend
Deployment's `migrate` initContainer, `k8s/base/backend-deployment.yaml:28-37`, runs
`alembic upgrade head` on every new pod before Phase 3's app container starts), rolling back the
**code** alone is not enough — the old code may not know how to read the new schema. You need
either a real Alembic `downgrade` for that migration (`05-DATA-LAYER.md §3.3` is why every
`upgrade` needs a working `downgrade`), or a forward-fix instead of a rollback. Check
`alembic history` and `alembic current` against the target revision before assuming a plain
`rollout undo` is sufficient.

---

## 3. Read the logs

Every log line is JSON to stdout (`backend/app/logging_config.py:29-51`, `JsonFormatter`) — never
a file handler (container filesystems are ephemeral). Read them with:

```bash
kubectl -n civicpulse logs -l app=backend --all-containers --since=1h | jq 'select(.request_id=="<id>")'
```

**How a citizen's request ID reaches you:** `backend/app/middleware/request_id.py:30,32,38` —
the middleware reads an incoming `X-Request-ID` header if present, otherwise generates one
(`request_id_var`, a `ContextVar`), stashes it on `request.state.request_id`, and echoes it back
on the response as `X-Request-ID` (`request_id.py:38`). Every JSON log line emitted during that
request carries the same value under `"request_id"` (`logging_config.py:41`, read from the same
`ContextVar`). A citizen (or the frontend, which should surface it in an error toast per
`04-CONTRACTS.md`'s error envelope) can hand you the `X-Request-ID` from their failed response,
and `jq 'select(.request_id=="...")'` pulls every log line from that one request across every pod
that touched it.

**What each log level means here** (`backend/app/settings.py:18` — `log_level: Literal["DEBUG",
"INFO", "WARNING", "ERROR"] = "INFO"`):
- `DEBUG` — not used in production; verbose enough to leak request shapes, so it stays off outside
  local dev (never enable in a shared/prod ConfigMap).
- `INFO` — the default. Normal request/response lifecycle, successful triage calls.
- `WARNING` — exactly one line per triage fallback (`triage_service.py:321-331`,
  `log.warning("triage.fallback", ...)`) — **this is the signal to watch**, see §4 below. Never
  more than one per fallback, by design (the docstring at `triage_service.py:14-15` states this
  explicitly, and it's what keeps a fallback storm from flooding the log volume).
- `ERROR` — an exception the registered handlers in `app/errors.py` mapped to a 5xx the caller
  could not avoid (should be rare; `/api/complaints` specifically is designed to never reach this
  level via a triage failure — see §4).

Secrets are never in a log line by construction, not by discipline alone: `logging_config.py:17-
26` (`_SECRET_PATTERNS`, a Groq/Google key regex) redacts any key-shaped substring that reaches a
formatted message, and `logging_config.py:54-60` (`_SecretRedactingFilter`) runs the same
redaction as a belt-and-braces filter even if a different formatter is ever swapped in.

---

## 4. Triage is failing

**This is the load-bearing entry in this file.** The whole point of CivicPulse is that this
failure mode is survivable — `POST /api/complaints` still returns **201** every time, with
`triaged_by="rules:fallback"`, never a 500 (CLAUDE.md HARD rule 5; enforced end-to-end by
`backend/app/services/triage_service.py:239-342::triage_with_fallback` and
`backend/app/services/complaint_service.py:30-76::create`).

**Trigger.** Watch the fallback rate — every fallback logs exactly one `WARNING`
(`triage_service.py:321`, `"triage.fallback"`) and is recorded into `app.state.ring`
(`triage_service.py:332-339`), which `GET /api/meta/providers` exposes as `recent[]`
(`backend/app/routes/meta.py:11-21`). A rising `fallback: true` proportion in that list, or a
rising rate of `"triage.fallback"` WARNING lines, is the signal. (`10-OBSERVABILITY.md §4`'s
PromQL alert, if wired to your Prometheus, is the automated version of watching the same signal —
check that doc for the exact query if Prometheus is deployed in your environment.)

**Steps, in order:**

1. **Check `GET /api/meta/providers`.** Look at `configured` (what `TRIAGE_PROVIDER` is set to),
   `active` (the primary provider instance actually constructed at boot — `meta.py:16`), and the
   `error_class` field on the most recent `recent[]` entries (`meta.py:13`, `TriageOutcome`, which
   carries `error_class` per the ring schema — cross-reference against
   `triage_service.py:283,320` where `error_class = type(last_exc).__name__`).
2. **If `error_class` is a rate-limit/429-shaped exception** (`SimulatedRateLimitError` in test/
   sim, or the real provider's 429 in production — classified `retryable` by
   `triage_service.py:108-109` and `134-136`): the provider's free/paid tier quota is exhausted
   for the window. One retry already happened automatically inside the 12 s budget
   (`settings.py:29-32`); if fallbacks are sustained, switch `TRIAGE_PROVIDER` via the ConfigMap
   (`k8s/base/configmap.yaml`) to `ollama` (self-hosted, no external quota) and roll the backend:
   ```bash
   kubectl -n civicpulse set env deployment/backend TRIAGE_PROVIDER=ollama
   kubectl -n civicpulse rollout status deployment/backend --timeout=120s
   ```
   (`set env` triggers a rolling restart on its own; the explicit `rollout status` just confirms
   it completed before you move on.)
3. **If `error_class` is a timeout** (`TimeoutError`/`httpx.TimeoutException` — retryable,
   `triage_service.py:52-53`): check the provider's own status page before touching anything in
   this repo. A single slow provider degrades to fallback per-request without operator action —
   this is by design, not an incident, unless the fallback rate stays elevated for an extended
   window, in which case follow step 2's switch-provider procedure.
4. **If `error_class` is a validation-shaped exception** (`ValidationError`,
   `LLMValidationError`, `OllamaValidationError` — non-retryable, `triage_service.py:93-99`, no
   retry ever attempted per CLAUDE.md HARD rule 6): the model's output shape changed — it's
   returning something that no longer parses into `TriageResult`. This will not self-heal by
   retrying (that's the whole reason it's non-retryable). Inspect `docs/TRIAGE.md`'s "Failure log"
   section for the last recorded reproduction of this class of failure, and bump the prompt
   version (`08-AI-TRIAGE.md`'s prompt-versioning convention) once you've confirmed the new output
   shape.
5. **If the provider is entirely down** (connection refused, DNS failure, or any exception not
   classified above): `classify()`'s default (`triage_service.py:141-147`) treats anything
   unrecognized as non-retryable — straight to fallback in one hop, no wasted retry budget.
   Confirm via `error_class` in `recent[]` and treat as step 2 or 3 depending on whether the
   underlying cause looks transient (network) or structural (the provider is genuinely offline).

**Expected impact throughout all of the above:** classification quality degrades — a citizen's
complaint gets `rules:fallback`'s keyword classification instead of the LLM's — but **intake never
stops**. No citizen sees a 500. `X-Cache`/`/api/stats` and the dashboard continue to function
normally; only the `triaged_by` field on new complaints and the fallback-rate metric change.

---

## 5. Database is down

Readiness fails cluster-wide (`backend/app/routes/ops.py:32-50::ready` — `_check_postgres()` at
`ops.py:53-57` raises inside `asyncio.gather(..., return_exceptions=True)` at `ops.py:40-42`,
`NotReady` is raised with `checks={"postgres": "error: ..."}` at `ops.py:49`), so every backend
pod's `readinessProbe` fails and pods leave the Service (`k8s/base/backend-deployment.yaml:57-62`).
`/health` (`ops.py:22-29`) deliberately does **not** check Postgres — it stays `200` so kubelet
does not restart-loop pods that are correctly reporting "alive, just not ready" (this is the
design; say so if asked, don't apologize for it). Check, in order:

```bash
kubectl -n civicpulse get pod postgres-0
kubectl -n civicpulse describe pod postgres-0        # events: OOMKilled? ImagePullBackOff? unbound PVC?
kubectl -n civicpulse get pvc                          # confirm the PVC backing postgres-0 is Bound
kubectl -n civicpulse exec postgres-0 -- psql -U <user> -c "select count(*) from pg_stat_activity;"
```

Compare the last query's count against `max_connections` (`k8s/base/postgres-statefulset.yaml`'s
config, or the image default if unset) — a connection-count exhaustion looks identical to
Postgres being "down" from the backend's perspective (every new connection attempt errors) but
the fix (raise `max_connections`, or find and kill a connection-leaking pod) is different from a
crashed/unscheduled pod.

---

## 6. Redis is down

Stats degrade to `MISS` on every request (the `StatsService` cache-aside path can't read a key it
can't reach — `09-CACHE-RATELIMIT.md §2` for the read path), and the rate limiter fails **open**
with the request forced to the `rules` provider rather than blocking traffic (`09-CACHE-
RATELIMIT.md §4.5`'s resolved posture — fail-open, bounded; see the `DEV-A · Phase 5 — E16
fail-open` entry in `docs/ENGINEERING-NOTES.md` for the verified-vs-deferred split of this
behavior on this branch). Readiness goes `503` the same way as §5 above
(`ops.py:60-62::_check_redis`, `request.app.state.redis.ping()`).

Check `maxmemory` evictions **first**, before anything else — `compose.yaml`'s `cache` service
runs `--maxmemory 256mb --maxmemory-policy allkeys-lru`; if the eviction counter
(`redis-cli info stats | grep evicted_keys`) is climbing, Redis is up but discarding keys under
memory pressure, which looks like "cache never has anything" without ever showing as "Redis is
down" in a health check. Only after ruling out eviction pressure should you look at whether the
pod/StatefulSet itself is unhealthy the same way §5 describes for Postgres.

---

## 7. Scale-out is not happening

Three commands, in this exact order — the order is the whole runbook entry:

```bash
kubectl -n civicpulse top pods                          # 1. is usage actually high?
kubectl -n civicpulse describe hpa backend-hpa           # 2. what does the HPA think the metric is?
kubectl -n civicpulse get deployment backend -o jsonpath='{.spec.template.spec.containers[0].resources}'; echo   # 3. do requests exist at all?
```

If step 2 shows `<unknown>/60%` instead of a real percentage, step 3 is almost always why —
`k8s/base/backend-deployment.yaml:46` marks `resources.requests.cpu` as "mandatory — HPA reads
`<unknown>` without this" for exactly this reason: the HPA's utilisation metric is
`usage / request`, and without a `request` denominator there's nothing to divide by.
`k8s/base/hpa.yaml` targets `Deployment/backend` at 60% CPU, `minReplicas: 2`, `maxReplicas: 10`,
asymmetric behavior (`scaleUp` stabilization `0s` — act on the newest reading immediately;
`scaleDown` stabilization `300s` — a brief trough can't collapse the fleet). See
`docs/ENGINEERING-NOTES.md`'s Q5 answer for why the lag between load rising and replicas rising is
minute-scale, not second-scale, and why this branch has not yet captured its own measured number
for that lag (Gate 7 evidence work, not yet run).

---

## 8. Rotate a credential

Full seven-step procedure: `docs/17-SECURITY-SECRETS.md §3`. Summary for the 3 a.m. version —
**do these in order, do not skip step 1 to "clean up first," the key is live while you rewrite**:

1. **Rotate immediately, before touching git.** Provider console → revoke → issue new
   (Groq/Google AI Studio for `LLM_API_KEY`; `ALTER USER ... PASSWORD` for Postgres). Record the
   UTC timestamp.
2. **Assess blast radius** — was the repo public, for how long, check the provider's usage
   dashboard for calls you didn't make.
3. **Rewrite history** with `git-filter-repo` (both developers present, offline) —
   `17-SECURITY-SECRETS.md §3` has the exact commands (`--invert-paths --path .env` or
   `--replace-text` for a key embedded in a tracked file), then `git push --force --mirror`.
4. **Both developers re-clone** — never `git pull` into an old clone, the old objects come back.
5. **Invalidate caches you don't control** — open a GitHub Support request to expire cached views
   of the unreachable objects, and say in your incident note that you did.
6. **Write `docs/evidence/incident-secret-exposure.md`** — detected/exposed/window/rotated/blast
   fields, per the template in `17-SECURITY-SECRETS.md §3`.
7. **Update the GitHub Secret / k8s Secret** that CI/CD reads (`cd.yml:107-109` reads
   `secrets.POSTGRES_PASSWORD`/`secrets.LLM_API_KEY` — rotating the provider key without updating
   the GitHub Secret leaves the deployed app running the *old*, now-revoked key until the next
   deploy fails and someone notices).

---

## 9. Restore from backup

```bash
make db-dump      # runs: docker compose exec -T database pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup-<date>.sql
```
(`Makefile:73` — confirmed the real recipe; `Makefile:72` is the adjacent `db-shell` target for a
live `psql` session against the running `database` service.)

To restore:
```bash
docker compose exec -T database psql -U $POSTGRES_USER -d $POSTGRES_DB < backup-<date>.sql
```

**Honest note:** there is no automated backup schedule in v1 — `make db-dump` is a manual,
on-demand snapshot. If the last dump predates the incident, you lose everything written since
that dump. This is a disclosed gap, not a hidden one: v1 ships this manual mechanism and nothing
scheduled (cron, a k8s CronJob, a managed Postgres provider's automated snapshots) sits behind it.
