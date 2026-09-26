# CivicPulse

Citizen submits a free-text complaint → an LLM (or a keyword-rule fallback) classifies it into
category/priority/summary → persisted → shown on an operator dashboard. The classifier is
replaceable and the system never falls over when it is rate-limited, slow, or wrong — every
provider failure ends in `201` with `triaged_by="rules:fallback"`, never a 500.

Two-developer assignment build. Full design docs live in [`docs/`](docs/) — `docs/00-SPEC.md`
is the source of truth; this file is the entry point, not a substitute for it.

## Quickstart

Requires Docker and Docker Compose.

```bash
make up
```

This builds every image, starts the stack, runs migrations, seeds the database, and waits for
the app to report ready. Once it prints the URL, open it:

```bash
# http://localhost:8080
```

Stop it (keeps data):

```bash
make down
```

Stop it and destroy all data:

```bash
make nuke
```

## Everyday commands

```bash
make check      # full local gate: lint, type-check, tests, layer/secret checks
make test       # backend + frontend test suites
make lint       # ruff + eslint
make type       # mypy + tsc --noEmit
make migrate    # alembic upgrade head, against the running stack
make seed       # re-run the seed script
make db-shell   # psql into the running database
```

Run `make help` for the full target list.

## Kubernetes (local k3d)

```bash
make k8s-up     # cluster + ingress-nginx + metrics-server + deploy the dev overlay
make k8s-down   # tear the cluster down
```

See [`docs/13-KUBERNETES.md`](docs/13-KUBERNETES.md) and
[`docs/14-LOAD-AUTOSCALING.md`](docs/14-LOAD-AUTOSCALING.md) for the full manifest set, HPA/VPA,
and load-test runbook.

## Project layout

```
backend/    FastAPI app — routes/ → services/ → repositories/ → providers/, one-way imports
frontend/   React + Vite dashboard, typed against backend/openapi.json (never hand-edited)
k8s/        Kustomize base + dev/prod overlays
load/       k6 load-test scripts (HPA/VPA proof)
docs/       Design docs, one per phase — docs/00-SPEC.md is authoritative
scripts/    check_submission.py (automated rubric-deduction detectors) and friends
```

## Configuration

Copy `.env.example` to `.env` (done automatically by `make up` if `.env` doesn't exist yet) and
edit as needed. `TRIAGE_PROVIDER=simulated` is the default — no external API key required to
run the full stack. See `.env.example`'s own comments for what each provider option needs.

## Rules this repo enforces on itself

`docs/CLAUDE.md` is binding — secrets never committed, no direct pushes to `main`, SQL only in
`repositories/`, no `if status == ...` chains for the state machine, a triage-provider failure
never becomes a 500, and a fixed deduction ledger for anything from an unpinned image tag to a
broken quickstart. `scripts/check_submission.py` runs an automated detector for every line in
that ledger — see `make submission-check`.
