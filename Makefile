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
check: lint type test lint-localhost lint-layers secret-scan ## full local gate
lint-layers: ## CLAUDE.md HARD rule 3 — SQL only in repositories/, no HTTP concerns below routes
	@! grep -rnE "select\(|session|execute\(|text\(" backend/app/routes/ || (echo "FAIL: SQL in routes"; exit 1)
	@! grep -rnE "HTTPException|status_code|Response" backend/app/repositories/ || (echo "FAIL: HTTP concerns in repositories"; exit 1)
	@! grep -rn "from app.routes" backend/app/services backend/app/repositories backend/app/providers 2>/dev/null || (echo "FAIL: upward import — arrows point one way"; exit 1)
lint:
	cd backend && ruff check . && ruff format --check .
	@if [ -f frontend/vite.config.ts ]; then cd frontend && npm run lint; else echo "skip: frontend/ not scaffolded yet (Phase 2b)"; fi
	@! grep -rnE "in_progress.*resolved|TRANSITIONS|allowedNext" frontend/src --include=*.ts --include=*.tsx --exclude=schema.d.ts \
	  || (echo "FAIL: business rule leaked into the frontend (CLAUDE.md HARD rule 9)"; exit 1)
type:
	cd backend && mypy app
	@if [ -f frontend/vite.config.ts ]; then cd frontend && npx tsc --noEmit; else echo "skip: frontend/ not scaffolded yet (Phase 2b)"; fi
test: test-be test-fe
test-be:
	cd backend && pytest
test-fe:
	@if [ -f frontend/vite.config.ts ]; then cd frontend && npm run test -- --run; else echo "skip: frontend/ not scaffolded yet (Phase 2b)"; fi

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
	python3 scripts/check_submission.py

## ── contract ──────────────────────────────────────────────────────────────
openapi: ## dump OpenAPI WITHOUT running a server
	cd backend && python3 -m app.cli.openapi_dump > ../openapi.json.tmp
	mv openapi.json.tmp openapi.json
gen-client: openapi ## regenerate the typed client; must be a no-op diff in CI
	cd frontend && npm ci --silent && npx --no-install openapi-typescript ../openapi.json --empty-objects-unknown -o src/api/schema.d.ts && cp ../openapi.json src/api/openapi.json

lock: ## re-pin backend/requirements.lock (hashed) from pyproject.toml — commit the result
	cd backend && uv pip compile pyproject.toml --generate-hashes --universal --python-version 3.12 -q -o requirements.lock

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
