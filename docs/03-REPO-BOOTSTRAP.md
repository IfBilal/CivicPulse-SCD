# 03 — PHASE 0: REPOSITORY BOOTSTRAP

> **Owner:** both · **Day:** 1 · **Gate:** Gate 0 in `02-CRITICAL-PATH.md`
> **Rubric served:** A (all 15), G (partial), I (partial), plus **deduction armour for all of §5.3**.

---

## 1. Directory layout (exactly §5.7, expanded)

```
civicpulse/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # app factory + lifespan + signal wiring ONLY
│   │   ├── config.py                  # pydantic-settings; the ONLY os.environ reader
│   │   ├── deps.py                    # FastAPI Depends providers (session, redis, triage)
│   │   ├── domain/
│   │   │   ├── enums.py               # Category, Priority, Status, TriagedBy
│   │   │   └── transitions.py         # the explicit transition TABLE (§2.2)
│   │   ├── schemas/                   # Pydantic DTOs — the wire contract
│   │   │   ├── complaint.py  errors.py  stats.py  meta.py  triage.py
│   │   ├── routes/                    # HTTP ONLY
│   │   │   ├── complaints.py  stats.py  meta.py  health.py  metrics.py
│   │   ├── services/                  # business rules
│   │   │   ├── triage_service.py  complaint_service.py  stats_service.py
│   │   ├── repositories/              # ALL SQL, nowhere else
│   │   │   ├── base.py  complaint_repo.py  stats_repo.py
│   │   ├── providers/
│   │   │   ├── cache/{base.py,redis_cache.py}
│   │   │   ├── ratelimit/{base.py,redis_limiter.py,lua/fixed_window.lua}
│   │   │   └── triage/{base.py,llm.py,ollama.py,rules.py,simulated.py,factory.py}
│   │   ├── middleware/
│   │   │   ├── request_id.py  logging.py  metrics.py  ratelimit.py
│   │   ├── db/{session.py,models.py}
│   │   ├── obs/{logging_config.py,metrics.py,ring.py}
│   │   └── cli/{seed.py,openapi_dump.py}
│   ├── alembic/{env.py,script.py.mako,versions/}
│   ├── alembic.ini
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── unit/{test_transitions.py,test_rules_triage.py,test_validation.py,...}
│   │   ├── integration/{test_complaints_api.py,test_stats_cache.py,test_ratelimit.py,...}
│   │   └── contract/{test_openapi_shape.py,test_status_codes.py}
│   ├── Dockerfile
│   ├── .dockerignore
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── main.tsx  App.tsx  ErrorBoundary.tsx
│   │   ├── api/{client.ts,schema.d.ts,config.ts}     # schema.d.ts is GENERATED
│   │   ├── components/{ComplaintForm.tsx,ComplaintTable.tsx,StatusBadge.tsx,CacheBadge.tsx,Pagination.tsx,FilterBar.tsx}
│   │   └── pages/{Submit.tsx,Dashboard.tsx,Stats.tsx}
│   ├── tests/{setup.ts,msw/handlers.ts,*.test.tsx}
│   ├── public/config.js                  # placeholder; OVERWRITTEN at container start
│   ├── Dockerfile  .dockerignore  nginx.conf  docker-entrypoint.d/10-config.sh
│   ├── package.json  tsconfig.json  vite.config.ts  vitest.config.ts  eslint.config.js
├── k8s/
│   ├── base/{namespace,configmap,secret,postgres,redis,backend,frontend,ingress,hpa,vpa,pdb,networkpolicy}.yaml
│   ├── base/kustomization.yaml
│   └── overlays/{dev,prod}/kustomization.yaml
├── load/{k6-script.js,k6-rollout.js,plot_hpa.py}
├── docs/
│   ├── ENGINEERING-NOTES.md  RUNBOOK.md  AI-USAGE.md  TRIAGE.md
│   ├── adr/{0001-provider-interface.md,0002-frontend-runtime-config.md,
│   │        0003-deploy-by-sha.md,0004-pii-and-data-governance.md}
│   ├── handover/HANDOVER-<branch>.md
│   └── evidence/                      # see 18-DOCS-EVIDENCE-VIVA.md §3 for the exact filename list
├── scripts/{check_submission.py,wait_for.sh,measure_context.sh,pin_digests.sh}
├── .github/
│   ├── workflows/{ci.yml,cd.yml,release.yml}
│   ├── ISSUE_TEMPLATE/{task.yml,bug.yml}
│   ├── pull_request_template.md
│   └── CODEOWNERS
├── compose.yaml  compose.prod.yaml
├── .env.example  .gitignore  .gitleaks.toml  .pre-commit-config.yaml
├── Makefile  README.md  LICENSE
```

**Deviations from §5.7 and why:** `domain/`, `middleware/`, `obs/`, `db/`, `cli/`, `schemas/` are
additions *inside* `backend/app/`. §5.7 lists `{routes,services,repositories,providers}` — those four
still exist and still hold exactly what §2.2 says. The extra packages hold things §2.2 never assigned
to a layer (enums, DTOs, middleware, logging config). Note this in the README so a marker reading
§5.7 literally sees the mapping.

---

## 2. `.gitignore` (the −20 line of defence)

```gitignore
# secrets — FIRST, so it is never scrolled past
.env
.env.*
!.env.example
*.pem
*.key
!**/lua/*.lua
secrets/
kubeconfig*
*.kubeconfig

# python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
coverage.xml

# node
node_modules/
dist/
.vite/
coverage/
*.tsbuildinfo

# docker / k8s scratch
*.tar
sbom-*.json
trivy-*.json

# os / editor
.DS_Store
Thumbs.db
.idea/
.vscode/*
!.vscode/extensions.json
```

> **`.env` must be gitignored before the first `git add`.** If it lands even once, it is in history and
> §5.3 fires at −20 *plus* mandatory rotation *plus* an incident note. See `01-WORKFLOW.md §9`.

---

## 3. `.env.example` (committed; placeholders only)

Every variable the system reads lives here. `config.py` must fail loudly on a missing one — a
silently-defaulted secret is how `localhost` ends up in production.

```bash
# ── App ───────────────────────────────────────────────────────────────────
APP_ENV=dev                       # dev | prod
LOG_LEVEL=INFO
LOG_FORMAT=json                   # json | console (console for local TTY only)

# ── Postgres ──────────────────────────────────────────────────────────────
POSTGRES_USER=civicpulse
POSTGRES_PASSWORD=CHANGE_ME_LOCAL_ONLY
POSTGRES_DB=civicpulse
POSTGRES_HOST=database            # ← service name. NEVER "localhost" (§5.3 −8)
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT_S=5

# ── Redis ─────────────────────────────────────────────────────────────────
REDIS_HOST=cache                  # ← service name, not localhost
REDIS_PORT=6379
REDIS_URL=redis://${REDIS_HOST}:${REDIS_PORT}/0

# ── Triage ────────────────────────────────────────────────────────────────
TRIAGE_PROVIDER=simulated         # simulated | rules | llm | ollama   ← DEFAULT IS SIMULATED
TRIAGE_TIMEOUT_S=10               # §2.5 item 2 — hard cap
TRIAGE_TOTAL_BUDGET_MS=12000      # attempt + retry must fit inside this
TRIAGE_MAX_RETRIES=1              # §2.5 item 3 — exactly one
TRIAGE_RETRY_JITTER_MS=250
TRIAGE_CACHE_TTL_S=86400          # §2.5 item 5 — 24 h
TRIAGE_MIN_CONFIDENCE=0.35        # below this → treat as low-confidence, see ADR-0001
TRIAGE_RING_SIZE=20               # /api/meta/providers — last 20 outcomes

LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.1-8b-instant
LLM_API_KEY=REPLACE_ME            # ← never a real key in this file
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b

# ── Cache / rate limit ────────────────────────────────────────────────────
STATS_CACHE_TTL_S=30              # §2.4 Job 1
STATS_CACHE_KEY=stats:v1
RATELIMIT_ENABLED=true
RATELIMIT_REQUESTS=10             # §2.4 Job 2
RATELIMIT_WINDOW_S=60
TRUSTED_PROXY_HOPS=1              # nginx=1, nginx+ingress=2. See 09-CACHE-RATELIMIT.md §4.3

# ── CORS (dev direct-origin path only; prod uses the nginx /api proxy) ─────
CORS_ALLOW_ORIGINS=http://localhost:5173

# ── Images (compose.prod.yaml) ────────────────────────────────────────────
IMAGE_TAG=REPLACE_WITH_COMMIT_SHA
REGISTRY=ghcr.io/<org>/civicpulse
```

**Rule:** if `grep -c '=' .env.example` differs from the field count in `backend/app/config.py`,
CI fails. That check lives in `scripts/check_submission.py`.

---

## 4. `backend/pyproject.toml`

```toml
[project]
name = "civicpulse-backend"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi==0.115.*", "uvicorn[standard]==0.32.*", "pydantic==2.9.*",
  "pydantic-settings==2.6.*", "sqlalchemy==2.0.*", "psycopg[binary,pool]==3.2.*",
  "alembic==1.13.*", "redis==5.2.*", "httpx==0.27.*", "openai==1.54.*",
  "prometheus-client==0.21.*", "python-json-logger==2.0.*", "orjson==3.10.*",
]

[project.optional-dependencies]
dev = ["pytest==8.3.*","pytest-asyncio==0.24.*","pytest-cov==5.0.*","anyio==4.6.*",
       "ruff==0.7.*","mypy==1.13.*","types-redis","testcontainers[postgres,redis]==4.8.*","hypothesis==6.112.*"]

[tool.ruff]
line-length = 100
target-version = "py312"
[tool.ruff.lint]
select = ["E","F","I","UP","B","SIM","ASYNC","S","T20","RUF"]
# S = bandit. S105/S106 hardcoded-password checks stay ON — that is deduction armour.
ignore = ["S101"]           # assert is fine in tests
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S","T20"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_unreachable = true
disallow_any_generics = true
plugins = ["pydantic.mypy"]
[[tool.mypy.overrides]]
module = ["testcontainers.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
addopts = "-q --strict-markers --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=65"
markers = ["unit","integration","contract","slow"]
asyncio_mode = "auto"
filterwarnings = ["error::DeprecationWarning"]

[tool.coverage.run]
branch = true
source = ["app"]
omit = ["app/cli/*", "alembic/*"]
```

> `--cov-fail-under=65` puts Rubric C's coverage threshold **in the tool**, not in a human's memory.
> The number is from §3.4 (`coverage ≥ 65% on app/`) and Rubric C's last line.

---

## 5. `Makefile` — the one-command promise (§1.4)

`make up` **is** the README quickstart. If it does not work from a clean clone, §5.3 fires at −5.

```makefile
SHELL := /bin/bash
.DEFAULT_GOAL := help
COMPOSE := docker compose
NS := civicpulse

help: ## list targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "\033[36m%-22s\033[0m %s\n",$$1,$$2}'

## ── one-command promise ───────────────────────────────────────────────────
up: ## THE quickstart: build, start, migrate, seed, wait for ready
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build --wait
	$(COMPOSE) exec -T backend alembic upgrade head
	$(COMPOSE) exec -T backend python -m app.cli.seed
	@./scripts/wait_for.sh http://localhost:8080/api/stats 60
	@echo "→ http://localhost:8080"
down: ## stop, KEEP volumes (persistence contract §2.3)
	$(COMPOSE) down
nuke: ## stop and DESTROY volumes
	$(COMPOSE) down -v

## ── quality gate (run before every commit) ────────────────────────────────
check: lint type test lint-localhost secret-scan ## full local gate
lint:
	cd backend && ruff check . && ruff format --check .
	cd frontend && npm run lint
type:
	cd backend && mypy app
	cd frontend && npx tsc --noEmit
test: test-be test-fe
test-be:
	cd backend && pytest
test-fe:
	cd frontend && npm run test -- --run

## ── deduction armour ──────────────────────────────────────────────────────
lint-localhost: ## §5.3 −8: no localhost in service-to-service config
	@! grep -rnI --exclude-dir={node_modules,.git,dist,tests,docs} \
	  -e 'localhost' -e '127\.0\.0\.1' \
	  backend/app compose.yaml compose.prod.yaml k8s/ \
	  || (echo "FAIL: localhost used for service-to-service"; exit 1)
secret-scan: ## §5.3 −20: no secrets in the working tree or history
	@gitleaks detect --no-banner --redact -c .gitleaks.toml
history-scan:
	@gitleaks detect --no-banner --redact --log-opts="--all" -c .gitleaks.toml
submission-check:
	python scripts/check_submission.py

## ── contract ──────────────────────────────────────────────────────────────
openapi: ## dump OpenAPI WITHOUT running a server
	cd backend && python -m app.cli.openapi_dump > ../openapi.json
gen-client: openapi ## regenerate the typed client; must be a no-op diff in CI
	cd frontend && npx openapi-typescript ../openapi.json -o src/api/schema.d.ts

## ── data ──────────────────────────────────────────────────────────────────
migrate:   ; $(COMPOSE) exec -T backend alembic upgrade head
downgrade: ; $(COMPOSE) exec -T backend alembic downgrade -1
seed:      ; $(COMPOSE) exec -T backend python -m app.cli.seed
db-shell:  ; $(COMPOSE) exec database psql -U $$POSTGRES_USER -d $$POSTGRES_DB
db-dump:   ; $(COMPOSE) exec -T database pg_dump -U $$POSTGRES_USER $$POSTGRES_DB > backup-$$(date +%F-%H%M).sql

## ── kubernetes (the SECOND command of §1.4) ───────────────────────────────
k8s-up: ## cluster + metrics-server + VPA + deploy dev overlay
	k3d cluster create $(NS) --agents 2 -p "8081:80@loadbalancer" --wait
	kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
	kubectl -n kube-system patch deploy metrics-server --type=json \
	  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
	kubectl apply -k k8s/overlays/dev
	kubectl -n $(NS) rollout status deploy/backend --timeout=300s
k8s-down:  ; k3d cluster delete $(NS)
k8s-logs:  ; kubectl -n $(NS) logs -l app=backend --tail=200 -f
rollback:  ; kubectl -n $(NS) rollout undo deployment/backend && kubectl -n $(NS) rollout status deployment/backend

## ── load ──────────────────────────────────────────────────────────────────
load:      ; k6 run load/k6-script.js
hpa-watch: ; kubectl -n $(NS) get hpa backend-hpa -w | tee docs/evidence/hpa-watch.txt
vpa-show:  ; kubectl -n $(NS) describe vpa backend-vpa | tee docs/evidence/vpa-describe-$${RUN:-run1}.txt

## ── evidence ──────────────────────────────────────────────────────────────
evidence-isolation: ## §3.2 — the failing ping IS the evidence
	-@$(COMPOSE) exec -T frontend ping -c1 -W2 database 2>&1 | tee docs/evidence/network-isolation.txt
	-@$(COMPOSE) exec -T frontend sh -c 'nc -z -w2 database 5432; echo "exit=$$?"' 2>&1 | tee -a docs/evidence/network-isolation.txt
evidence-context: ; ./scripts/measure_context.sh | tee docs/evidence/dockerignore-context-sizes.txt
evidence-shortlog: ; git shortlog -sn --no-merges | tee docs/evidence/shortlog.txt
```

> **`up` uses `--wait`**, which makes Compose block on *healthchecks*, not on container start. That
> single flag is the difference between a quickstart that works on a fast laptop and one that works
> on a marker's laptop. Rubric G's healthcheck line and §5.3's −5 quickstart line meet here.

---

## 6. GitHub scaffolding

### `.github/pull_request_template.md`

```markdown
## What
<!-- one paragraph, not a changelog -->

## Why
Closes #

## Spec clauses satisfied
<!-- cite 00-SPEC.md, e.g. §2.5 item 3, Rubric F line 3 -->

## Phase gate
- [ ] Gate checklist from 02-CRITICAL-PATH.md pasted below, all ticked

## Evidence
<!-- paths under docs/evidence/ added or updated by this PR -->

## Deduction armour
- [ ] no secret / key / `.env` in the diff (`make secret-scan`)
- [ ] no `localhost` for service-to-service (`make lint-localhost`)
- [ ] no `:latest` in anything deployed
- [ ] every publishing/deploying job still `needs:`-gated

## AI usage
- [ ] `docs/AI-USAGE.md` updated (§5.5)

## Reviewer
- [ ] **≥ 2 substantive comments with file:line** (Rubric A — "LGTM" scores zero)
```

### `.github/ISSUE_TEMPLATE/task.yml` (abbrev.)

Fields: `Phase` (dropdown P0–P8), `Owner` (DEV-A/DEV-B/both), `Spec clause` (text, required),
`Rubric line` (text, required), `Acceptance test` (textarea, required), `Evidence artefact` (text).

> Requiring *Spec clause* and *Rubric line* on every Issue is what makes
> `20-RUBRIC-TRACEABILITY.md` fill itself in.

---

## 7. `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks: [{id: end-of-file-fixer}, {id: trailing-whitespace},
            {id: check-merge-conflict}, {id: check-added-large-files, args: ["--maxkb=512"]},
            {id: detect-private-key}, {id: check-yaml, args: ["--allow-multiple-documents"]}]
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.2
    hooks: [{id: gitleaks}]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4
    hooks: [{id: ruff, args: ["--fix"]}, {id: ruff-format}]
  - repo: local
    hooks:
      - id: no-localhost
        name: no localhost in service config
        entry: make lint-localhost
        language: system
        pass_filenames: false
      - id: conventional-commit
        name: conventional commit subject
        entry: bash -c 'grep -qE "^(feat|fix|docs|test|refactor|perf|build|ci|chore|revert)(\(.+\))?!?: .{1,72}$" "$1"' --
        language: system
        stages: [commit-msg]
```

### `.gitleaks.toml` — project-specific rules

```toml
title = "civicpulse"
[extend]
useDefault = true

[[rules]]
id = "groq-key"
description = "Groq API key"
regex = '''gsk_[A-Za-z0-9]{40,}'''
tags = ["key","groq"]

[[rules]]
id = "google-ai-key"
description = "Google AI Studio key"
regex = '''AIza[0-9A-Za-z\-_]{35}'''

[[rules]]
id = "k8s-secret-nonplaceholder"
description = "base64 blob in a committed k8s Secret (§5.3 −15)"
path = '''k8s/.*secret.*\.ya?ml'''
regex = '''(?i)(api[_-]?key|password)\s*:\s*(?!PLACEHOLDER|CHANGE_ME|""|'')[A-Za-z0-9+/=]{16,}'''

[allowlist]
paths = ['''\.env\.example$''', '''docs/.*\.md$''', '''.*\.test\.tsx?$''']
```

> The third rule is the one that matters. §5.3 is explicit: *base64 is encoding, not encryption*. A
> real key in a committed `Secret` manifest is **−15** even though it looks scrambled.

---

## 8. `scripts/check_submission.py` — the lint that mirrors §5.3

Not a grader (§5.8). It encodes the eleven deductions plus the mechanical rubric lines. Exit 0 or
print a table of violations and exit 1.

| Check ID | §5.3 / Rubric | Implementation |
|---|---|---|
| `SEC-ENV-HISTORY` | −20 | `gitleaks detect --log-opts=--all`; also `git log --all --diff-filter=A --name-only -- .env '*.pem' '*.key'` |
| `SEC-K8S-SECRET` | −15 | parse every `kind: Secret` in `k8s/`; assert every `data`/`stringData` value is in the placeholder allowlist |
| `IMG-UNPINNED` | −8 | regex every `FROM ` in Dockerfiles and every `image:` in compose/k8s; fail if no `:tag` **or** tag is `latest` |
| `NET-LOCALHOST` | −8 | grep `localhost`/`127.0.0.1` in `backend/app`, `compose*.yaml`, `k8s/`, excluding tests/docs |
| `NET-SEGMENT` | −8 | parse `compose.yaml`: assert `internal.internal == true`, `frontend.networks == [edge]`, `database.networks == [internal]`, `cache.networks == [internal]`, `backend.networks == [edge, internal]` |
| `PORT-EXPOSED-PROD` | −8 | assert no `ports:` on `database`/`cache` in `compose.prod.yaml`; assert no `NodePort`/`LoadBalancer` Service selecting postgres or redis |
| `CI-NEEDS` | −8 | parse workflow YAML; for any job whose steps contain `push`, `docker/build-push-action` with `push: true`, `kubectl apply`, or `helm upgrade` → assert non-empty `needs` |
| `CD-LATEST-DEPLOY` | −8 | `kustomize build` each overlay; assert no image reference ends in `:latest` |
| `K8S-DB-DEPLOYMENT` | −8 | assert postgres is `kind: StatefulSet` with `volumeClaimTemplates` |
| `VCS-DIRECT-MAIN` | −5 | `git log --first-parent main --no-merges --format=%H` minus PR-merge SHAs; any remainder after the scaffold commit is a violation |
| `DOC-QUICKSTART` | −5 | extract fenced `bash` blocks under the README `## Quickstart` heading; assert every command exists as a Makefile target or resolves on `PATH` |
| `ENV-PARITY` | hygiene | every `Settings` field in `config.py` appears in `.env.example` and vice versa |
| `RUBRIC-COMMITS` | A | `git shortlog -sn --no-merges` → total ≥ 35, min share ≥ 35% |
| `RUBRIC-PRS` | A | `gh pr list --state merged --json number` → ≥ 5, each with a linked issue and ≥1 review |
| `RUBRIC-TESTS` | C/B | `pytest --collect-only -q \| wc -l` ≥ 14; vitest test count ≥ 5 |
| `RUBRIC-SEED` | D | run seed twice against a throwaway DB, assert equal counts, assert count ≥ 30 |
| `RUBRIC-ADR` | J | assert the four ADR filenames exist and each is > 40 lines |
| `RUBRIC-EVIDENCE` | J/H/A | assert every filename in `18-DOCS-EVIDENCE-VIVA.md §3` exists and is non-empty |

**Output format** (make it paste-able into a PR):

```
civicpulse submission check — 18 checks
  PASS  SEC-ENV-HISTORY        no secret in 87 commits
  PASS  NET-SEGMENT            frontend∉internal, database∉edge
  FAIL  CD-LATEST-DEPLOY       k8s/overlays/prod → ghcr.io/…/backend:latest  (§5.3 −8)
  WARN  RUBRIC-COMMITS         dev-b at 34.1% (floor 35%)
2 issues. Exit 1.
```

---

## 9. Branch protection — the exact clicks

`Settings → Branches → Add branch ruleset` on `main`:

1. **Require a pull request before merging** → Required approvals **1** → *Dismiss stale approvals
   when new commits are pushed* ✔ → *Require review from Code Owners* ✔
2. **Require status checks to pass** → *Require branches to be up to date* ✔ → add checks by their
   **exact job names**: `lint-and-type`, `test-backend`, `test-frontend`, `build`, `scan`,
   `manifests`, `integration`
3. **Require linear history** ✔
4. **Require conversation resolution before merging** ✔
5. **Block force pushes** ✔ · **Restrict deletions** ✔
6. **Do not allow bypassing the above settings** ✔ ← *this is the one people leave off, and it is
   how a `git push origin main` at 2 a.m. costs −5*

Screenshot the whole page → `docs/evidence/branch-protection.png` (Rubric A, 3 marks).

> **Ordering trap:** required status checks can only be selected **after** those job names have run
> at least once. So: push the hello-world `ci.yml` to a throwaway PR first, let it run, then add the
> checks, then screenshot.
