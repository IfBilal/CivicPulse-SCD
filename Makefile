SHELL := /bin/bash
.DEFAULT_GOAL := help

# This is a Phase 0 partial Makefile: only the targets DEV-B's tooling depends on
# today (pre-commit's no-localhost hook). The full Makefile — up/down, k8s-*, load,
# and the backend-dependent check/lint/type/test targets from 03-REPO-BOOTSTRAP.md §5
# — lands once backend/frontend scaffolding exists (DEV-A's Phase 0 half + Phase 2).

help: ## list targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "\033[36m%-22s\033[0m %s\n",$$1,$$2}'

lint-localhost: ## §5.3 −8: no localhost in service-to-service config
	@! grep -rnI --exclude-dir={node_modules,.git,dist,tests,docs} \
	  -e 'localhost' -e '127\.0\.0\.1' \
	  backend/app compose.yaml compose.prod.yaml k8s/ \
	  || (echo "FAIL: localhost used for service-to-service"; exit 1)
