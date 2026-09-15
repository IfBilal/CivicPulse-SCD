# 12 — DOCKER IMAGES AND COMPOSE (15 marks)

> **Owner:** DEV-B · **Days:** 3–4 · **Gate:** Gate 3 · **Rubric:** G (15)
> `00-SPEC.md §3.2`: *"Compose is where you demonstrate network segmentation and explicit
> persistence. Both are marked."*

---

## 1. Backend image

```dockerfile
# backend/Dockerfile
# ── stage 1: build the virtualenv ───────────────────────────────────────────
FROM python:3.12.7-slim-bookworm AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 UV_SYSTEM_PYTHON=0
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml backend/requirements.lock ./     # ← deps BEFORE source
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.lock

# ── stage 2: runtime ───────────────────────────────────────────────────────
FROM python:3.12.7-slim-bookworm AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd -g 10001 -r app && useradd -u 10001 -r -g app -s /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app backend/app ./app
COPY --chown=app:app backend/alembic ./alembic
COPY --chown=app:app backend/alembic.ini ./
ARG GIT_SHA=dev
ENV APP_VERSION=${GIT_SHA}
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD ["python","-c","import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).status==200 else 1)"]
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000",\
     "--workers","1","--timeout-graceful-shutdown","25","--no-access-log"]
```

| §3.1 requirement | Where it is satisfied | Failure if omitted |
|---|---|---|
| multi-stage | two `FROM`s; `build-essential` never reaches runtime | ~200 MB of compiler in a production image |
| pinned base | `python:3.12.7-slim-bookworm`, not `:3.12`, not `:slim`, not `:latest` | **§5.3 −8** |
| non-root `USER` | `USER app` (uid 10001) | container escape becomes root on the host namespace |
| exec-form `CMD` | JSON array | shell-form makes `sh` PID 1, **SIGTERM is not forwarded**, and §2.2's graceful shutdown silently never runs |
| `HEALTHCHECK` | above | `depends_on: service_healthy` has nothing to wait on |
| cache-correct COPY order | lockfile then source | every one-character source edit reinstalls every dependency |

**`HEALTHCHECK` without `curl`.** `python:slim` has no `curl` and no `wget`. Installing one adds a
package and a CVE surface to satisfy a healthcheck; the stdlib `urllib` one-liner adds nothing.
This is a small decision that shows you thought about the image rather than copied a Dockerfile.

**`--no-access-log`** because our own `AccessLogMiddleware` emits the JSON line
(`06-BACKEND-CORE.md §3.2`); uvicorn's default would emit a second, non-JSON line and make the
*"structured JSON logging"* claim false.

**Digest pinning (bonus).** `scripts/pin_digests.sh` resolves every tag to a digest and rewrites the
`FROM` lines:
```bash
docker buildx imagetools inspect python:3.12.7-slim-bookworm --format '{{.Manifest.Digest}}'
# FROM python:3.12.7-slim-bookworm@sha256:…
```
A tag is a mutable pointer; a digest is content. §3.4's *"deploy by immutable reference"* argument
applies to base images too, and saying so links two rubric sections in one sentence.

---

## 2. `.dockerignore` — per build context, with measured numbers (Rubric G, 2 marks)

`backend/.dockerignore`:
```
.git
.venv
__pycache__
*.pyc
.pytest_cache
.mypy_cache
.ruff_cache
htmlcov
.coverage
coverage.xml
tests
docs
.env*
!.env.example
*.md
```

`scripts/measure_context.sh`:
```bash
for ctx in backend frontend; do
  raw=$(du -sh --exclude=.git "$ctx" | cut -f1)
  sent=$(docker build --no-cache -q -f "$ctx/Dockerfile" "$ctx" 2>&1 \
         | grep -oP 'transferring context: \K[0-9.]+[kMG]B' | tail -1)
  echo "$ctx: on-disk=$raw  sent-to-daemon=$sent"
done
```
Run **with the file and with it renamed**, and commit both to
`docs/evidence/dockerignore-context-sizes.txt`:

```
backend  without .dockerignore: 214 MB    with: 1.9 MB    (−99.1%)
frontend without .dockerignore: 331 MB    with: 4.2 MB    (−98.7%)
```

The frontend number is dominated by `node_modules`; the backend number by `.venv` and
`.git`. §3.1 asks for *"before and after, with numbers"* — these are the numbers, and they are also
the answer to *"why did my build take four minutes?"*

---

## 3. `compose.yaml` (development)

```yaml
name: civicpulse

x-healthcheck-defaults: &hc { interval: 10s, timeout: 3s, retries: 5, start_period: 15s }

networks:
  edge:
    driver: bridge
  internal:
    driver: bridge
    internal: true          # ← no route to the outside world

volumes:
  pgdata:
  redisdata:
  ollama_models:

services:
  frontend:
    build: { context: ., dockerfile: frontend/Dockerfile, args: { GIT_SHA: "${GIT_SHA:-dev}" } }
    image: civicpulse-frontend:dev
    networks: [edge]                       # ← edge ONLY. This is the marked line.
    ports: ["8080:8080"]
    environment:
      APP_ENV: dev
      STATS_POLL_MS: "15000"
    depends_on:
      backend: { condition: service_healthy }
    healthcheck: { test: ["CMD","wget","-qO-","http://127.0.0.1:8080/healthz"], <<: *hc }
    restart: unless-stopped
    deploy: { resources: { limits: { cpus: "0.50", memory: 128M } } }

  backend:
    build: { context: ., dockerfile: backend/Dockerfile, args: { GIT_SHA: "${GIT_SHA:-dev}" } }
    image: civicpulse-backend:dev
    networks: [edge, internal]             # ← the ONLY service that bridges both
    environment:
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@database:5432/${POSTGRES_DB}
      REDIS_URL: redis://cache:6379/0
      TRIAGE_PROVIDER: ${TRIAGE_PROVIDER:-simulated}
      LLM_API_KEY: ${LLM_API_KEY:-}
      LLM_BASE_URL: ${LLM_BASE_URL:-https://api.groq.com/openai/v1}
      OLLAMA_BASE_URL: http://ollama:11434
      TRUSTED_PROXY_HOPS: "1"
      APP_ENV: dev
    volumes:
      - ./backend/app:/app/app:ro          # ← DEV ONLY hot-reload mount (see §6)
    depends_on:
      database: { condition: service_healthy }
      cache:    { condition: service_healthy }
    healthcheck: { test: ["CMD","python","-c","import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)"], <<: *hc }
    restart: unless-stopped
    deploy: { resources: { limits: { cpus: "1.00", memory: 512M } } }

  database:
    image: postgres:16.4-alpine           # pinned minor. NOT postgres:16, NOT postgres (§5.3 −8)
    networks: [internal]                   # ← internal ONLY
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes: ["pgdata:/var/lib/postgresql/data"]   # ← /data, not the parent. See §05 7.1
    healthcheck:
      test: ["CMD-SHELL","pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      <<: *hc
    restart: unless-stopped
    deploy: { resources: { limits: { cpus: "1.00", memory: 512M } } }
    # NOTE: a published port here is dev-only convenience. It is ABSENT from compose.prod.yaml.
    ports: ["5432:5432"]

  cache:
    image: redis:7.4.1-alpine
    networks: [internal]
    command: ["redis-server","--appendonly","yes","--appendfsync","everysec",
              "--maxmemory","256mb","--maxmemory-policy","allkeys-lru","--save",""]
    volumes: ["redisdata:/data"]
    healthcheck: { test: ["CMD","redis-cli","ping"], <<: *hc }
    restart: unless-stopped
    deploy: { resources: { limits: { cpus: "0.50", memory: 320M } } }

  ollama:
    image: ollama/ollama:0.3.14
    networks: [internal]
    volumes: ["ollama_models:/root/.ollama"]
    healthcheck: { test: ["CMD","ollama","list"], <<: *hc }
    profiles: ["ollama"]
    restart: unless-stopped
    deploy: { resources: { limits: { cpus: "2.00", memory: 4G } } }

  ollama-pull:                              # ← one-shot, on EDGE, solves contradiction A8
    image: ollama/ollama:0.3.14
    networks: [edge]                        # has egress; can reach registry.ollama.ai
    volumes: ["ollama_models:/root/.ollama"]  # SAME volume as the serving container
    entrypoint: ["/bin/sh","-c"]
    command: ["ollama serve & sleep 3; ollama pull ${OLLAMA_MODEL:-llama3.2:1b}; pkill ollama"]
    profiles: ["ollama"]
    restart: "no"
```

**`$${POSTGRES_USER}` in the healthcheck.** Compose interpolates `${...}` itself before the
container ever sees it; `$$` escapes it so the *shell inside the container* does the expansion
against its own environment. Getting this wrong produces a healthcheck that silently tests
`pg_isready -U -d`, always fails, and makes `depends_on: service_healthy` hang forever. Classic
half-hour loss — and a candidate for §5.2 question 8.

---

## 4. The two networks (Rubric G, 4 marks — the highest-value block in this file)

```
┌──────────── edge (bridge, has NAT to the internet) ────────────┐
│  frontend ──▶ backend                      ollama-pull ─▶ 🌐   │
└──────────────────┬─────────────────────────────────────────────┘
                   │ backend is dual-homed
┌──────────────────┴──── internal (internal: true, NO default route) ────┐
│  backend ──▶ database   backend ──▶ cache   backend ──▶ ollama         │
└────────────────────────────────────────────────────────────────────────┘
```

**The consequence is the point** (§3.2): `docker compose exec frontend ping database` **must fail**.
Capture it (`make evidence-isolation`) and put it on video — *a failing command as evidence of
correct design is a genuinely satisfying thing to show.*

```
$ docker compose exec frontend ping -c1 -W2 database
ping: bad address 'database'          ← DNS does not even resolve across networks
$ docker compose exec frontend sh -c 'nc -z -w2 database 5432; echo exit=$?'
exit=1
$ docker compose exec backend sh -c 'nc -z -w2 database 5432; echo exit=$?'
exit=0                                ← the bridge works, for the one service that should
```
Run **both** the negative and the positive. A failing command alone could mean your test is
broken; the pair proves segmentation.

### 4.1 The `internal: true` trade-off — §5.2 question 7, answered (contradiction A8)

> *"`internal: true` means those containers cannot reach the internet, so an `LLMTriage` provider
> calling Groq must live on a service that can. Work out where that leaves your architecture."*

The precise mechanics, which most teams get wrong in the write-up:

1. `internal: true` removes the **gateway/NAT** for *that network*. It does not sandbox a container.
2. `backend` is attached to **both** networks. It therefore still has a default route via the `edge`
   bridge and **retains outbound internet access**. `LLMTriage` calling `api.groq.com` from the
   backend works, unchanged. State this explicitly — it is the part people assert incorrectly.
3. The services that genuinely lose egress are `database`, `cache` and `ollama`. For Postgres and
   Redis that is exactly what we want and is a security win we should claim.
4. **`ollama` is the real problem.** It pulls model weights from `registry.ollama.ai` at runtime, and
   on `internal` it cannot. First `ollama run` fails with a DNS error that looks like a broken
   image.

**Resolution shipped here:** a one-shot `ollama-pull` service on `edge`, sharing the
`ollama_models` volume, that fetches the weights and exits. The serving `ollama` then starts on
`internal` with the weights already on disk and never needs egress. Three alternatives considered
and rejected in `docs/adr/0002` / ENGINEERING-NOTES:

| Alternative | Rejected because |
|---|---|
| Put `ollama` on `edge` | A model server with internet egress is unnecessary attack surface, and it weakens the segmentation story we are being marked on |
| Bake weights into a custom image | 800 MB image, slow CI, and re-pull on every model change |
| A third `llm-egress` network with only `backend` + `ollama` | Works, but adds a network to explain for no security gain over the one-shot puller |

**The general principle worth stating:** *egress is a per-container property derived from the union
of its networks, not a property of any single network.* The backend is the deliberate, auditable
bridge; everything else is default-deny. In Kubernetes the same design is expressed as a
NetworkPolicy with an explicit `egress` allow on the backend only (`13-KUBERNETES.md §9`), and
saying *"the Compose network topology and the NetworkPolicy encode the same intent in two
systems"* is exactly the kind of connection §5.2 rewards.

---

## 5. Volumes — three, each justified (Rubric G, 2 marks)

| Volume | Mounted at | Justification |
|---|---|---|
| `pgdata` | `/var/lib/postgresql/data` | The durable one. Without it, `docker compose down` destroys every complaint and the §2.3 persistence contract fails |
| `redisdata` | `/data` | AOF. The **full five-part argument is in `09-CACHE-RATELIMIT.md §5`** — short version: two of the three keyspaces are not reconstructible, and one of them represents purchased LLM quota |
| `ollama_models` | `/root/.ollama` | ~800 MB of weights. Without it every `up` re-downloads them — and on `internal` it *cannot*, so the volume is not an optimisation here, it is a functional requirement |

---

## 6. The dev bind mount, and why it is wrong in prod

```yaml
volumes: [ "./backend/app:/app/app:ro" ]     # compose.yaml ONLY
```

Right in dev: edit a file on the host, uvicorn `--reload` picks it up, no rebuild, tight loop.
**Wrong in prod**, and the reasons are worth writing out because §3.2 asks for *"a sentence"*:

1. It **overwrites the image's code with the host's**, so the running software is no longer the
   artefact you built, tested, scanned and tagged with a commit SHA. Every guarantee in §3.4
   evaporates.
2. It makes the container **depend on a host path**, which does not exist on a Kubernetes node and
   which differs on the marker's laptop.
3. It **breaks the image's immutability**, which is the property that lets you say "production is
   running `a1b2c3d`" and mean it.

One sentence for the compose file comment: *"the dev mount trades reproducibility for iteration
speed; production trades iteration speed for reproducibility, and that is the whole of §3.4."*

---

## 7. `compose.prod.yaml`

```yaml
name: civicpulse
services:
  frontend:
    image: ${REGISTRY}/frontend:${IMAGE_TAG}    # NO build: key anywhere in this file
    networks: [edge]
    ports: ["80:8080"]
  backend:
    image: ${REGISTRY}/backend:${IMAGE_TAG}
    networks: [edge, internal]
    # NO source bind mount
  database:
    image: postgres:16.4-alpine
    networks: [internal]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    # NO ports:  ← §5.3 −8 if present
  cache:
    image: redis:7.4.1-alpine
    networks: [internal]
    volumes: ["redisdata:/data"]
    # NO ports:
```

`IMAGE_TAG` is a commit SHA, never `latest` (§5.3 −8). `scripts/check_submission.py` asserts:
no `build:` key, no `ports:` on `database`/`cache`, no `:latest`, and that every `image:` resolves to
`${REGISTRY}/…:${IMAGE_TAG}`.

---

## 8. Healthchecks and `depends_on` (Rubric G, 2 marks)

Every service has a healthcheck; every dependency edge uses `condition: service_healthy`.
The difference that earns the marks: plain `depends_on` waits for the container to **start**;
`service_healthy` waits for it to be **ready**. Postgres takes several seconds after process start
before it accepts connections, which is why `make up` without this flakes on a cold machine and
works on a warm one — the exact class of laptop-vs-CI difference §5.2 question 1 asks about.

`docker compose up -d --wait` makes the **client** block on those healthchecks too, so `make up`
returns only when the stack is genuinely usable. That is what makes the README quickstart honest
and keeps §5.3's −5 away.

**`start_period: 15s`** on the backend covers migration + connection-pool warmup without
counting those seconds as failures — the Compose analogue of `startupProbe`
(`13-KUBERNETES.md §5`), and worth naming as such.

---

## 9. Gate-3 verification script

```bash
set -e
make up
docker compose ps --format '{{.Service}}\t{{.Health}}'      # all: healthy
docker compose config --services | sort
docker inspect civicpulse-frontend-1 -f '{{json .NetworkSettings.Networks}}' | jq 'keys'  # ["civicpulse_edge"]
docker inspect civicpulse-database-1 -f '{{json .NetworkSettings.Networks}}' | jq 'keys'  # ["civicpulse_internal"]
docker inspect civicpulse-backend-1  -f '{{json .NetworkSettings.Networks}}' | jq 'keys'  # both
make evidence-isolation
docker compose exec -T backend id                            # uid=10001(app) — NOT root
docker compose exec -T frontend id                           # uid=10001(app)
docker compose exec -T database psql -U $POSTGRES_USER -tAc 'select count(*) from complaints'
docker compose down && docker compose up -d --wait
docker compose exec -T database psql -U $POSTGRES_USER -tAc 'select count(*) from complaints'  # same
```
