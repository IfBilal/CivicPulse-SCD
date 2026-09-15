# 21 — ARCHITECTURE DIAGRAMS

> **Owner:** both · **Use:** README §Architecture (Rubric J1), the video's opening slide, and the
> whiteboard you will be asked to draw at the viva.
> Every diagram here is Mermaid, so it renders on GitHub without a build step and stays in version
> control as text. **Paste diagram §1 into the README** — Rubric J1 names a Mermaid architecture
> diagram explicitly.

---

## 1. System context (the README diagram)

```mermaid
graph TB
    citizen["👤 Citizen<br/>submits a complaint"]
    operator["👤 Municipal operator<br/>triages and resolves"]

    subgraph civicpulse["CivicPulse"]
        fe["Frontend<br/>React 18 + Vite + TS<br/>served by nginx"]
        be["Backend API<br/>FastAPI + Pydantic v2<br/>routes → services → repos → providers"]
        pg[("PostgreSQL 16<br/>complaints<br/>Alembic-managed")]
        rd[("Redis 7<br/>① stats cache<br/>② rate limiter<br/>③ triage cache")]
    end

    llm["🌐 Hosted LLM<br/>Groq / Gemini free tier<br/>JSON mode"]
    ol["Ollama<br/>llama3.2:1b<br/>local, zero egress"]
    rules["RuleBasedTriage<br/>keyword fallback<br/>cannot fail"]

    citizen -->|"POST /api/complaints"| fe
    operator -->|"dashboard, PATCH status"| fe
    fe -->|"/api proxied, same-origin"| be
    be --> pg
    be --> rd
    be -.->|"TRIAGE_PROVIDER=llm<br/>10s timeout, 1 retry"| llm
    be -.->|"TRIAGE_PROVIDER=ollama"| ol
    be ==>|"on timeout / 429 / 5xx / bad JSON"| rules

    classDef ext fill:#4a4a4a,stroke:#222,color:#fff
    classDef core fill:#1f6feb,stroke:#0d419d,color:#fff
    classDef data fill:#238636,stroke:#116329,color:#fff
    classDef fb fill:#9e6a03,stroke:#7d4e00,color:#fff
    class llm,ol ext
    class fe,be core
    class pg,rd data
    class rules fb
```

**The thick arrow is the thesis.** Everything else is plumbing; the `==>` to `RuleBasedTriage` is
§1.1's *"the reader must be replaceable… and must not fall over when the clever one is
rate-limited, slow, or simply wrong."* When you present this diagram, point at that arrow first.

---

## 2. Container view with network boundaries

```mermaid
graph TB
    subgraph edge["🌐 network: edge  (bridge, NAT to internet)"]
        FE["frontend<br/>nginx:1.27-alpine<br/>uid 10001, :8080"]
        BE["backend<br/>python:3.12-slim<br/>uid 10001, :8000"]
        PULL["ollama-pull<br/>one-shot<br/>fetches weights, exits"]
    end

    subgraph internal["🔒 network: internal  (internal: true — NO default route)"]
        DB[("database<br/>postgres:16.4-alpine")]
        CA[("cache<br/>redis:7.4.1-alpine")]
        OL["ollama<br/>llama3.2:1b"]
    end

    VP[("vol pgdata")]
    VR[("vol redisdata")]
    VO[("vol ollama_models")]

    USER((browser)) -->|":8080"| FE
    FE -->|"proxy_pass /api"| BE
    BE --> DB
    BE --> CA
    BE --> OL
    BE -.->|"egress via the EDGE gateway"| NET(("api.groq.com"))
    PULL -.->|"egress"| REG(("registry.ollama.ai"))

    DB --- VP
    CA --- VR
    OL --- VO
    PULL --- VO

    FE -. "✗ ping database:<br/>bad address" .-x DB

    classDef edgeC fill:#1f6feb,stroke:#0d419d,color:#fff
    classDef intC fill:#238636,stroke:#116329,color:#fff
    classDef vol fill:#6e40c9,stroke:#4c2889,color:#fff
    class FE,BE,PULL edgeC
    class DB,CA,OL intC
    class VP,VR,VO vol
```

**Three facts this diagram encodes** (`12-DOCKER-COMPOSE.md §4.1`):
1. `frontend` is on `edge` only — the red crossed arrow is the marked demonstration.
2. `backend` is **dual-homed**, so it keeps internet egress via the `edge` gateway. `internal: true`
   does not sandbox a container; it removes a route from *one* of its networks.
3. `ollama` has no egress, which is why `ollama-pull` exists on `edge` sharing the same volume.

---

## 3. Backend component view (the four layers)

```mermaid
graph LR
    subgraph routes["routes/ — HTTP only"]
        R1["complaints.py"]; R2["stats.py"]; R3["meta.py"]; R4["health.py"]; R5["metrics.py"]
    end
    subgraph services["services/ — business rules"]
        S1["ComplaintService"]; S2["TriageService"]; S3["StatsService"]
    end
    subgraph repos["repositories/ — ALL SQL"]
        P1["ComplaintRepository"]; P2["StatsRepository"]
    end
    subgraph providers["providers/ — outbound, behind interfaces"]
        V1["TriageProvider<br/>(Protocol)"]; V2["RedisCache"]; V3["RedisLimiter"]
    end
    subgraph domain["domain/ — pure"]
        D1["enums.py"]; D2["transitions.py"]; D3["errors.py"]
    end

    R1 --> S1; R2 --> S3; R3 --> S2
    S1 --> S2; S1 --> P1; S3 --> P2; S3 --> V2; S2 --> V1; S2 --> V2
    S1 --> D2; S1 --> D3
    P1 --> D1

    R1 -.->|"❌ FORBIDDEN"| P1
    R1 -.->|"❌ FORBIDDEN"| V1

    classDef forbidden stroke:#da3633,stroke-width:3px,stroke-dasharray:5 5
```

The dashed red edges are what `make lint-layers` fails the build on
(`05-DATA-LAYER.md §5`). §2.2: *"A route that opens a database session is a design failure worth
marks."* Arrows point **downward only** — nothing under `routes/` may import from `routes/`.

---

## 4. The POST /api/complaints happy path

```mermaid
sequenceDiagram
    autonumber
    actor C as Citizen
    participant N as nginx
    participant M as Middleware stack
    participant R as routes/complaints
    participant S as ComplaintService
    participant T as TriageService
    participant RD as Redis
    participant L as LLMTriage
    participant DB as Postgres

    C->>N: POST /api/complaints
    N->>M: + X-Forwarded-For, X-Request-ID
    M->>M: ① RequestID ② AccessLog ③ Prometheus ④ CORS
    M->>RD: ⑤ RateLimit EVALSHA rl:{ip}
    RD-->>M: count=3, ttl=57  → allowed
    M->>R: routed
    R->>R: Pydantic validate (400 on failure)
    R->>S: create(text, location, contact)
    S->>T: triage_with_fallback()
    T->>RD: GET triage:v1:{model}:{sha256}
    RD-->>T: nil (MISS)
    T->>L: chat.completions (JSON mode, temp 0, 10s cap)
    L-->>T: {"category":"water","priority":"high",…}
    T->>T: TriageResult.model_validate_json  ← distrust, always
    T->>RD: SETEX triage:… 86400
    T-->>S: TriageOutcome(llm:groq, 842ms)
    S->>DB: INSERT complaints RETURNING *
    DB-->>S: row
    S->>RD: DEL stats:v1        ← invalidate AFTER commit
    S-->>R: Complaint
    R-->>C: 201 + Location + X-Request-ID
```

Note step 5: the rate limiter runs **before body parsing**, so a flood of 2 MB malformed bodies
costs one Redis call, not a Pydantic parse each (`04-CONTRACTS.md §6.1`).

---

## 5. The fallback ladder — the diagram to draw at the viva

```mermaid
flowchart TD
    A["triage_with_fallback(text, location)"] --> B{"cache hit?<br/>triage:v1:{model}:{sha256}"}
    B -->|yes| C["return cached<br/>triaged_by = ORIGINAL provider<br/>cached: true"]
    B -->|no| D["deadline = now + 12s<br/>attempts = 0"]
    D --> E["attempt += 1<br/>asyncio.timeout(remaining)"]
    E --> F{"outcome"}

    F -->|"TriageResult ok"| G["post-validate:<br/>enum · ≤140 · confidence"]
    G -->|valid| H["SETEX 24h<br/>return llm:groq"]
    G -->|"invalid"| K

    F -->|"ValidationError<br/>JSONDecodeError<br/>HTTP 400/401/403"| K["NON-RETRYABLE"]
    F -->|"Timeout · 429 · 5xx<br/>ConnectError"| I["RETRYABLE"]

    I --> J{"attempts ≤ 1<br/>AND time left?"}
    J -->|yes| L["sleep(uniform(0, 250ms))"] --> E
    J -->|no| K

    K --> M["RuleBasedTriage.triage()<br/>⚠ cannot raise, by contract"]
    M --> N["log.warning('triage.fallback')<br/>EXACTLY ONE, with<br/>complaint_id · provider · error_class"]
    N --> O["triage_fallback_total.inc()"]
    O --> P["return rules:fallback<br/>HTTP status is still 201"]

    classDef ok fill:#238636,stroke:#116329,color:#fff
    classDef bad fill:#da3633,stroke:#a40e26,color:#fff
    classDef fb fill:#9e6a03,stroke:#7d4e00,color:#fff
    class C,H ok
    class K bad
    class M,N,O,P fb
```

**Four things to say while drawing it:**
- `ValidationError` is on the **non-retryable** side (contradiction A14, §2.5 item 3 — *"never retry a
  400; the request was wrong and will be wrong again"*). A malformed response is deterministic
  under retry.
- The deadline guard means worst case is bounded at ~12 s, not 2 × 10 s + jitter.
- Fallback results are **not cached** — a transient outage must not freeze into 24 hours of
  keyword classification.
- The terminal node still says **201**. *"A user must never see a 500 because a third party was
  rate-limited."*

---

## 6. Status state machine

```mermaid
stateDiagram-v2
    [*] --> open : POST /api/complaints
    open --> in_progress : PATCH ✔
    open --> rejected : PATCH ✔
    in_progress --> resolved : PATCH ✔
    in_progress --> rejected : PATCH ✔
    resolved --> [*]
    rejected --> [*]

    note right of resolved
      TERMINAL
      any PATCH → 409
      allowed_from_current: []
    end note
    note right of open
      12 of the 16 (from,to) pairs
      are 409, including open→open.
      Table lookup, never an if-chain.
    end note
```

---

## 7. Kubernetes deployment view

```mermaid
graph TB
    IN["Ingress: civicpulse.localhost<br/>/ → frontend · /api → backend"]

    subgraph ns["namespace: civicpulse"]
        subgraph fe["Deployment frontend (2–N)"]
            F1["pod"]; F2["pod"]
        end
        subgraph be["Deployment backend (2–10, HPA)"]
            B1["initContainer: alembic upgrade head<br/>+ uvicorn, 3 probes, preStop sleep 5"]
            B2["pod"]
        end
        subgraph sts["StatefulSet postgres (1)"]
            P0["postgres-0"]
        end
        RD["Deployment redis (1)<br/>strategy: Recreate"]

        SF(["svc frontend<br/>ClusterIP"]); SB(["svc backend<br/>ClusterIP"])
        SP(["svc postgres<br/>ClusterIP None"]); SR(["svc redis<br/>ClusterIP"])

        CM["ConfigMap app-config"]; SE["Secret app-secrets<br/>placeholders in git"]
        HPA["HPA v2<br/>cpu 60%, 2–10<br/>up 0s / down 300s"]
        VPA["VPA updateMode: Off<br/>recommender only"]
        PDB["PDB minAvailable: 1"]
        NP["NetworkPolicy<br/>default-deny + allows"]
    end

    PVC1[("PVC pgdata-postgres-0<br/>re-bound by ordinal")]
    PVC2[("PVC redis-data")]

    IN --> SF --> fe
    IN --> SB --> be
    be --> SP --> sts
    be --> SR --> RD
    sts --- PVC1
    RD --- PVC2
    CM -.-> be
    SE -.-> be
    HPA -.->|scales| be
    VPA -.->|recommends only| be
    PDB -.->|guards| be
    NP -.->|enforced by CNI| ns
    be -.->|"egress :443 only"| EXT(("hosted LLM"))
```

**`PVC pgdata-postgres-0` is the whole StatefulSet argument in one label:** the claim is named
after the **ordinal**, so deleting the pod returns the same disk to the same identity. A Deployment
cannot promise that, which is why §3.3 calls it *"a marked error."*

---

## 8. CI/CD pipeline

```mermaid
graph LR
    subgraph ci["ci.yml — PR to main, push to dev"]
        L["lint-and-type<br/>+ schema drift gate"]
        TB["test-backend<br/>cov ≥65%, simulated"]
        TF["test-frontend<br/>≥5 tests"]
        BU["build<br/>push: false<br/>+ 60MB size gate"]
        SC["scan<br/>Trivy HIGH/CRIT<br/>ignore-unfixed"]
        MA["manifests<br/>kustomize | kubeconform"]
        IT["integration<br/>compose: /ready → POST → GET<br/>→ X-Cache MISS→HIT → nc FAILS → 429"]
        BU --> SC
    end

    PR(("PR")) --> ci --> GATE{"all 7 required<br/>checks green?"}
    GATE -->|no| BLOCK["🚫 merge button disabled<br/>evidence: ci-red.png"]
    GATE -->|yes| MERGE(("squash-merge to main"))

    subgraph cd["cd.yml — push to main"]
        T2["test<br/>(full suite on the MERGED result)"]
        BP["build-push<br/>needs: test<br/>GHCR :SHA + :latest<br/>Syft SBOM · Cosign sign<br/>→ outputs.digest"]
        DP["deploy-k8s<br/>needs: build-push<br/>kind + ingress<br/>kustomize edit set image @digest<br/>rollout status · smoke · get hpa"]
        T2 --> BP --> DP
    end

    MERGE --> cd --> PROD(("ephemeral cluster<br/>running a DIGEST"))
    PROD -.->|"rollout undo (30s)"| PREV(("previous ReplicaSet"))
    PROD -.->|"re-apply previous SHA (auditable)"| GIT(("git"))

    classDef gate fill:#da3633,stroke:#a40e26,color:#fff
    class GATE,BLOCK gate
```

The two `needs:` edges are worth **−16** if missing (§5.3, twice over). They are the reason a
broken commit cannot reach the registry with a plausible SHA tag.

---

## 9. Three-signal observability

```mermaid
graph LR
    REQ["request<br/>X-Request-ID: 6f1c…"]
    REQ --> LOG["LOGS — stdout JSON<br/>request_id · complaint_id<br/>provider · error_class"]
    REQ --> MET["METRICS — /metrics<br/>path_template · status · provider<br/>NEVER an id (cardinality)"]
    REQ --> TRC["TRACES — OTLP (bonus)<br/>trace_id, span tree"]

    LOG -->|"grep request_id"| DEBUG["one request, across pods"]
    MET -->|PromQL| ALERT["fallback rate > 20%<br/>p95 triage > 5s<br/>hit rate < 10%<br/>sustained 429s"]
    TRC -->|"trace_id in every log line"| DEBUG
    ALERT --> RB["RUNBOOK §4<br/>'triage is failing'"]
```

Logs answer *what happened to this one request*; metrics answer *what is happening to all
requests*; traces answer *where the time went*. The join key is `request_id`, present in the
response header, the response body's error envelope, and every log line
(`10-OBSERVABILITY.md §3`).

---

## 10. Two-developer parallel schedule (Gantt)

```mermaid
gantt
    title CivicPulse — 14-day two-window plan (◆ = joint, ⏱ = wall-clock bound)
    dateFormat X
    axisFormat D%s

    section Critical path
    P0 bootstrap            :crit, 1, 1
    P1 contract freeze ◆    :crit, 2, 1
    P2 data                 :crit, 2, 2
    P3 backend API          :crit, 4, 1
    P4 AI triage            :crit, 5, 3
    P5 cache + limiter      :crit, 8, 1
    P5b compose integration :crit, 4, 1
    P6a CI                  :crit, 7, 2
    P6b kubernetes          :crit, 9, 2
    P7 load + autoscale ⏱   :crit, 10, 2
    P8a CD + rollback       :crit, 11, 2
    P8b evidence + video ⏱  :crit, 13, 2

    section DEV-B parallel (has float)
    FE scaffold             :2, 2
    Docker images           :3, 1
    FE views                :6, 2
    FE tests + runtime cfg  :7, 2
    Observability           :9, 1

    section Wall-clock, start Day 0
    Keys + k3d + VPA ⏱      :milestone, 0, 0
    Merge-conflict drill ◆  :milestone, 7, 0
    Red-gate evidence       :milestone, 8, 0
```

---

## 11. Which diagram goes where

| Diagram | Destination | Why |
|---|---|---|
| §1 context | **README** (Rubric J1) | Mermaid architecture diagram is named in the rubric |
| §2 networks | README §Architecture + video beat 4 | makes the crossed arrow legible before you demo it |
| §3 components | ENGINEERING-NOTES §Layering | evidence for Rubric C2 |
| §4 sequence | `docs/TRIAGE.md §1` | the request path, once, precisely |
| §5 fallback ladder | ADR-0001 + **the viva whiteboard** | the single most-asked design |
| §6 state machine | README §API + ADR | 16 cells, four legal |
| §7 k8s | README §Kubernetes + RUNBOOK | the ordinal-named PVC label is the StatefulSet argument |
| §8 pipeline | README §CI/CD | the two `needs:` edges are the deduction armour |
| §9 observability | `docs/RUNBOOK.md §3` | how a citizen's id becomes a log query |
| §10 Gantt | `01-WORKFLOW.md` / your planning issue | not for the marker; for you |

> **Viva tip:** be able to draw §5 from memory in sixty seconds, and §2 in thirty. Those two
> diagrams cover roughly half of the likely questions, and drawing beats describing.
