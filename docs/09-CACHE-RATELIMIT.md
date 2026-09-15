# 09 — CACHE LAYER (Redis 7 doing two jobs · 10 marks)

> **Owner:** DEV-A · **Day:** 8 · **Gate:** Gate 5 · **Rubric:** E (10)
> `00-SPEC.md §2.4`: *"Redis 7 does two different jobs, deliberately, so you learn that
> infrastructure is a capability and not a single-purpose box."*

Three distinct keyspaces, one Redis:

| Keyspace | Job | TTL | Owner doc |
|---|---|---|---|
| `stats:v1` | read-through aggregate cache | 30 s | this file §2 |
| `rl:{ip}:{window}` | distributed rate limiter | window length | this file §4 |
| `triage:v1:{model}:{sha256}` | content-hash triage cache | 24 h | `08-AI-TRIAGE.md §6` |

The prefixes are not cosmetic: `SCAN MATCH triage:*` during an incident must not touch the
limiter, and a `FLUSHDB` during development must be a conscious decision about all three.

---

## 1. Client configuration

```python
Redis.from_url(str(settings.redis_url),
    decode_responses=True,
    socket_timeout=2.0, socket_connect_timeout=2.0,   # a stalled cache must not stall the request
    retry_on_timeout=False,                            # WE decide; see §3
    health_check_interval=30,
    max_connections=20)
```

**Cache failures are never user-visible.** Every read is wrapped so that a Redis outage degrades
to a cache miss (recompute from Postgres) rather than a 500. The rate limiter's failure posture is a
separate, deliberate decision — see §4.5, because it is the interesting one.

---

## 2. Job 1 — read-through cache for `/api/stats` (Rubric E, 3 + 2 marks)

```python
class StatsService:
    async def get(self) -> tuple[StatsResponse, bool, int]:
        raw = await self._safe_get(KEY)
        if raw is not None:
            payload = StatsResponse.model_validate_json(raw)
            age = int(time.time() - payload.generated_at.timestamp())
            return payload, True, age                          # X-Cache: HIT

        async with self._stampede_lock(KEY) as acquired:
            if not acquired:                                   # someone else is computing
                if (raw := await self._await_fill(KEY, 300)) is not None:
                    return StatsResponse.model_validate_json(raw), True, 0
            payload = await self._repo.aggregate()             # the one SQL statement, §07 §5
            await self._safe_setex(KEY, settings.stats_cache_ttl_s, payload.model_dump_json())
            return payload, False, 0                           # X-Cache: MISS
```

### 2.1 `X-Cache` semantics — say exactly what the token means

`HIT` = *this response body was read from Redis and not recomputed*.
`MISS` = *this request executed the aggregate query*.
A request that waited on another request's stampede lock and then read the filled key is a **HIT** —
it did not run the query. Write that definition in `docs/ENGINEERING-NOTES.md`; an undefined
`X-Cache` is exactly the kind of thing a viva will press on.

`cache_age_seconds` is `0` on a MISS and `now - generated_at` on a HIT, so the frontend badge can
render *"cached 12 s ago"* instead of a bare boolean. That is Rubric B's *"Showing your own cache
behaviour in the UI is unusual and is exactly the kind of thing that makes a portfolio repo
memorable"* taken seriously.

### 2.2 The viva question, pre-answered: **why TTL *and* explicit invalidation?**

§2.4 announces this will be asked. The answer has four parts and each is a real failure mode:

1. **Invalidation alone is not sufficient, because invalidation can be lost.** The `DEL` is a network
   call that can fail — Redis blips, the pod is SIGKILLed between `COMMIT` and `DEL`, a
   `NetworkPolicy` change drops one packet. With no TTL, that single lost `DEL` freezes the stats
   page **forever**. The TTL is the bounded-staleness backstop: worst case 30 s, not infinity.
2. **Invalidation alone is not sufficient, because not every writer goes through the app.** `make seed`
   inserts 36 rows with raw SQL. A `psql` hotfix during the demo. A future batch importer. TTL
   covers every writer, including ones that do not exist yet.
3. **TTL alone is not sufficient, because 30 seconds is visible.** *"A newly submitted complaint
   appears in the stats immediately rather than up to 30 seconds later"* (§2.4). On camera, submitting
   a complaint and watching the stats not change for half a minute looks broken.
4. **They fail in opposite directions.** TTL bounds staleness but cannot make anything fresh sooner;
   invalidation makes things fresh immediately but cannot bound staleness when it fails. Belt and
   braces is the correct posture for a cheap cache in front of an expensive aggregate.

> Compressed for the viva: *"invalidation is the fast path, TTL is the correctness floor. Either
> alone leaves a hole the other covers."*

### 2.3 Invalidation points — every write, no exceptions

| Write | Invalidates |
|---|---|
| `POST /api/complaints` (after commit) | `stats:v1` |
| `PATCH /api/complaints/{id}/status` (after commit) | `stats:v1` |
| `python -m app.cli.seed` | `stats:v1` (the seed calls it explicitly — a seeded DB with stale stats is a broken demo) |

**After commit, not before.** Invalidating inside the transaction creates a window where the cache
is empty, a concurrent read repopulates it from the *pre-commit* state, and the stale value then
lives for a full TTL. Order: `COMMIT` → `DEL`. Test it:

```python
async def test_invalidate_happens_after_commit(client, redis, monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(redis, "delete", record(seen, "del"))
    monkeypatch.setattr(Session, "commit", record(seen, "commit"))
    await client.post("/api/complaints", json=GOOD)
    assert seen.index("commit") < seen.index("del")
```

### 2.4 Stampede protection (not required by the spec — do it and say why)

At TTL expiry under load, N concurrent requests all miss and all run the aggregate. With the HPA
at ten pods and k6 at 300 VU, that is a self-inflicted thundering herd on the database at a
predictable 30-second cadence. `SET lock:stats NX PX 3000` elects one computer; the rest poll the
key for up to 300 ms and then fall through to computing anyway (never block a citizen on a lock).

The alternative — probabilistic early expiry (XFetch) — is better and more complex; mention it as
the rejected option in the notes. What matters for marks is noticing that a cache has a
**correlated-miss** failure mode at all.

### 2.5 Gate-5 evidence commands

```bash
curl -si localhost:8080/api/stats | grep -i x-cache          # X-Cache: MISS
curl -si localhost:8080/api/stats | grep -i x-cache          # X-Cache: HIT
curl -s  -XPOST localhost:8080/api/complaints -H 'content-type: application/json' -d @fixtures/one.json >/dev/null
curl -si localhost:8080/api/stats | grep -i x-cache          # X-Cache: MISS  ← invalidation proven
sleep 31
curl -si localhost:8080/api/stats | grep -i x-cache          # X-Cache: MISS  ← TTL proven
```
Tee to `docs/evidence/cache-behaviour.txt`. The same four assertions run in the CI `integration`
job (§3.4 requires *"check `X-Cache` goes MISS → HIT"*).

---

## 3. Cache failure posture

| Failure | Behaviour | Reason |
|---|---|---|
| Redis down on `GET` | treat as MISS, compute from Postgres, `X-Cache: MISS`, log WARNING once per 60 s | Availability > cache. A cache outage must not become an application outage |
| Redis down on `SETEX` | serve the computed payload, swallow the error | The user already has their answer |
| Redis down on `DEL` (invalidate) | log WARNING, continue | This is precisely the lost-invalidation case the TTL exists to bound (§2.2 point 1) |
| Redis down for **rate limiting** | **see §4.5 — this one is not the same answer** | |
| Redis down | `/ready` returns **503** naming `redis` | §2.2 is explicit: readiness is 200 *"only if Postgres and Redis are both reachable"*. So the pod leaves the Service — but requests already in flight still degrade gracefully rather than 500 |

That last row is a real tension worth stating in the notes: readiness says Redis is essential, while
the cache path says Redis is optional. Both are right — readiness governs *traffic admission* at the
Service level, the degradation path governs *in-flight correctness*. A pod with a dead Redis should
stop receiving new traffic, and should still answer the request it is holding.

---

## 4. Job 2 — distributed rate limiter (Rubric E, 4 marks)

> §2.4: *"it must be distributed, in Redis, not an in-process dictionary, because the moment the
> HPA scales you to four pods an in-process limiter permits four times the traffic. Understanding
> that sentence is worth more than the marks attached to it."*

### 4.1 Algorithm — fixed window, with the trade-off stated

`RATELIMIT_REQUESTS=10` per `RATELIMIT_WINDOW_S=60`, keyed by client IP, protecting
`POST /api/complaints` only.

```lua
-- backend/app/providers/ratelimit/lua/fixed_window.lua
-- KEYS[1] = rl:{ip}:{window_start}   ARGV[1] = limit   ARGV[2] = window_seconds
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end
local ttl = redis.call('TTL', KEYS[1])
return {n, ttl}
```

**Why Lua and not `INCR` + `EXPIRE` from Python:** two round trips are not atomic. If the pod is
killed between them, the key has no TTL and that IP is banned **forever**. Under an HPA that is
not hypothetical — pods are killed on every scale-down. `EVALSHA` makes it one atomic server-side
operation. This is the single best sentence to have ready if the viva asks *"why Lua?"*

**Fixed window's known flaw, disclosed:** a client can send 10 requests at `t=59.9` and 10 more at
`t=60.1` — 20 in 200 ms. The mitigations, in ascending order of complexity: sliding-window log
(`ZADD`/`ZREMRANGEBYSCORE`, exact, O(log n), unbounded memory per key), sliding-window counter
(weighted blend of the current and previous window, approximate, cheap), token bucket
(smooth, supports bursts, needs `redis.call('TIME')` for clock-authority). We ship fixed window
because it is what the spec offers first, and we put the sliding-window-counter upgrade in the
notes as the named next step. **Both the flaw and the fix belong in `docs/ENGINEERING-NOTES.md`.**

A token-bucket implementation is included in the repo as `token_bucket.lua` behind
`RATELIMIT_ALGO=token_bucket`, unit-tested, so the comparison is demonstrable rather than
asserted. Redis's `TIME` command is the clock authority — never the application's clock, which
differs per pod.

### 4.2 Response contract

```
HTTP/1.1 429 Too Many Requests
Retry-After: 37
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1757830860
Content-Type: application/json
{"error":{"code":"rate_limited","message":"Rate limit exceeded: 10 requests per 60s.",
 "request_id":"…","details":{"limit":10,"window_seconds":60,"retry_after_seconds":37}}}
```

`Retry-After` is **integer seconds** = the key's remaining TTL, clamped to ≥ 1 (a `Retry-After: 0`
invites an immediate retry). HTTP-date form is legal but useless to a browser client and harder to
test. Say which form you chose and why.

### 4.3 Client IP resolution — the trap the spec sets and does not mention (contradiction A9)

The limiter is *"keyed by client IP"*. But the request reaches the backend through **nginx** (the
`/api` proxy, ADR-0002) and in Kubernetes through the **Ingress controller** as well. Naively,
`request.client.host` is the **proxy's** IP — so every citizen shares one bucket and the first ten
requests of the minute lock out the whole city.

```python
def client_ip(request: Request, trusted_hops: int) -> str:
    if trusted_hops <= 0:
        return request.client.host
    xff = [p.strip() for p in request.headers.get("X-Forwarded-For", "").split(",") if p.strip()]
    if len(xff) < trusted_hops:
        return request.client.host                    # header shorter than expected ⇒ do not trust
    return xff[-trusted_hops]                         # count from the RIGHT
```

**Count from the right, never the left.** `X-Forwarded-For` is client-appendable: a hostile client
sends `X-Forwarded-For: 1.2.3.4` and, if you take `xff[0]`, they rotate that value per request and
bypass the limiter entirely. The rightmost `trusted_hops` entries are the ones **your own**
infrastructure appended. `TRUSTED_PROXY_HOPS=1` for compose (nginx only), `2` in the
Kubernetes overlay (ingress-nginx + the frontend nginx), set via ConfigMap.

nginx must actually append it:
```nginx
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Request-ID $request_id;
```

Tests:
- `test_xff_spoof_ignored`: two requests with different forged left-most values map to the **same**
  bucket.
- `test_xff_hops_configurable`: with `hops=2`, `1.1.1.1, 2.2.2.2, 3.3.3.3` resolves to `2.2.2.2`.
- `test_short_xff_falls_back_to_peer`: a header with fewer entries than `hops` does not index out of
  range or trust the client.

This is the kind of detail that separates a limiter that exists from a limiter that works. Put it in
the notes.

### 4.4 Placement in the request path

Middleware, scoped to `POST /api/complaints`, running **before body parsing**
(`04-CONTRACTS.md §6.1`). A flood of 2 MB malformed bodies should cost one Redis `EVALSHA`,
not a Pydantic parse each. Probes (`/health`, `/ready`, `/metrics`) are never limited — a limited
probe is a self-inflicted outage.

### 4.5 Fail-open or fail-closed when Redis is down?

The one place where the cache's "degrade silently" posture is wrong, and you must choose:

- **Fail-open** (allow the request): availability preserved; but the limiter's *purpose* is protecting
  a finite free-tier quota (§2.4), and a Redis outage is exactly when a `for` loop would drain the
  day's allowance.
- **Fail-closed** (503 everything): protects the quota; turns a cache outage into a full intake outage.

**Our choice: fail-open, bounded.** Allow the request, but force `TRIAGE_PROVIDER` degradation for
that request to `rules` — so an unlimited flood costs zero inferences. Intake stays up, the quota
stays safe, and the degradation is visible in `/api/meta/providers`. Log one WARNING per 60 s.

Write this in `docs/ENGINEERING-NOTES.md` **and** in ADR-0001. It is a genuine, defensible,
non-obvious decision, and the viva rewards exactly this shape of reasoning.

### 4.6 Proving it is distributed (Gate 5)

```bash
docker compose up -d --scale backend=2 --wait
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code} " -XPOST localhost:8080/api/complaints \
    -H 'content-type: application/json' -d @fixtures/one.json
done; echo
# expect: 201 ×10 then 429 429   ← ACROSS BOTH REPLICAS
docker compose exec cache redis-cli --scan --pattern 'rl:*'
```
Tee to `docs/evidence/ratelimit-distributed.txt`. The negative control is worth capturing too:
temporarily set `RATELIMIT_BACKEND=inprocess`, re-run, observe **20** successes before the first
429, and keep that output beside the Redis one. A side-by-side that shows 2× leakage with two
pods is the most direct possible demonstration of the sentence §2.4 says is worth more than the
marks.

---

## 5. AOF persistence — the required justification (Rubric E, 1 mark)

```yaml
cache:
  image: redis:7.4.1-alpine
  command: ["redis-server","--appendonly","yes","--appendfsync","everysec",
            "--maxmemory","256mb","--maxmemory-policy","allkeys-lru",
            "--save",""]
  volumes: [ "redisdata:/data" ]
```

> §2.4 asks directly: *"why does the cache need a volume when the whole point of a cache is that it
> can be rebuilt? There is a defensible answer either way. Give yours."*

**Our answer: because this Redis is not only a cache.**

1. **Two of the three keyspaces are not reconstructible.** `stats:v1` is derived from Postgres and
   can be rebuilt in one query — that part genuinely does not need a volume. But `rl:{ip}` is
   **authoritative state with no other source**: losing it hands every rate-limited client a fresh
   quota, which is a security-relevant reset, not a performance blip. And `triage:v1:*` holds
   **purchased** results — each entry cost a real inference against a finite free-tier allowance.
   Losing 2,000 cached triages is not a cache miss, it is 2,000 calls against a quota measured in
   tens per minute.
2. **The cold-start cost is asymmetric.** Rebuilding `stats` costs one query. Rebuilding
   `triage:*` costs hours of quota and, if the quota is exhausted, cannot be rebuilt at all that day —
   the system falls back to `rules` and the demo shows keyword classification.
3. **`appendfsync everysec` is the right knob.** `always` fsyncs every write and would make the
   limiter's `INCR` disk-bound; `no` leaves up to 30 s of writes to the OS buffer. `everysec` bounds
   loss to one second, which is the correct durability tier for "expensive to rebuild but not
   financial data."
4. **`--save ""` disables RDB.** Running both AOF and RDB doubles disk work for a dataset we can
   afford to lose one second of. One persistence mechanism, chosen deliberately.
5. **`maxmemory 256mb` + `allkeys-lru`** bounds the volume. Without it, 24-hour triage entries
   grow without limit and Redis is eventually OOM-killed by the container limit — which on
   Kubernetes is a restart loop that looks like a Redis bug and is actually a missing eviction policy.

**The honest counter-argument, which you should also state:** if this Redis held *only* the stats
cache, the volume would be waste — it would slow every write to protect data that one SQL query
regenerates. The volume is justified by the *other two jobs*, which is itself the §2.4 lesson:
infrastructure is a capability, and its persistence requirements follow from **what you put in it**,
not from its category name.

**Verification for the gate:**
```bash
docker compose exec cache redis-cli CONFIG GET appendonly       # → "yes"
docker compose exec cache redis-cli SET probe 1 EX 600
docker compose restart cache && sleep 3
docker compose exec cache redis-cli GET probe                   # → "1"  (survived)
docker compose exec cache sh -c 'ls -la /data/appendonlydir'
```

---

## 6. Test matrix (Rubric E evidence)

| # | Test | Asserts | Rubric |
|---|---|---|---|
| E1 | `test_stats_miss_then_hit` | header sequence MISS, HIT | E1 |
| E2 | `test_stats_ttl_expiry` | fake clock advanced 31 s ⇒ MISS | E1 |
| E3 | `test_cache_age_seconds` | 0 on MISS, ≈ elapsed on HIT | E1, B3 |
| E4 | `test_invalidated_on_create` | POST ⇒ next GET is MISS | E2 |
| E5 | `test_invalidated_on_status_change` | PATCH ⇒ next GET is MISS | E2 |
| E6 | `test_invalidate_happens_after_commit` | call ordering (§2.3) | E2 |
| E7 | `test_stats_degrades_to_miss_when_redis_down` | 200 + MISS, no 500 | E1 |
| E8 | `test_stampede_single_computation` | 20 concurrent misses ⇒ 1 aggregate query | E1 |
| E9 | `test_ratelimit_429_after_limit` | 10×201 then 429 | E3 |
| E10 | `test_retry_after_is_positive_int` | `1 <= int(h) <= 60` | E3 |
| E11 | `test_ratelimit_is_shared_across_instances` | two app instances, one Redis ⇒ combined count | E3 |
| E12 | `test_lua_sets_expire_atomically` | kill between INCR/EXPIRE impossible: TTL always > 0 | E3 |
| E13 | `test_xff_spoof_ignored` | forged left-most XFF shares a bucket | E3 |
| E14 | `test_xff_hops_configurable` | hops=2 picks the right element | E3 |
| E15 | `test_probes_not_rate_limited` | 100 `/health` calls all 200 | E3 |
| E16 | `test_ratelimit_fail_open_degrades_provider` | Redis down ⇒ 201 with `triaged_by="rules"` | E3 |
| E17 | `test_aof_enabled` | `CONFIG GET appendonly == yes` | E4 |
