# ADR-0002 — Frontend runtime configuration

- **Status:** Accepted · 2026-09-23 · Phase 2 (`feat/fe-scaffold`)
- **Deciders:** DEV-B (author), DEV-A (review; `/docs/adr/` needs both owners)
- **Satisfies:** PDF §2.1 *"Runtime configuration … State your choice in an ADR"* · Rubric B
  *"Runtime configuration — no baked-in API URL; one image runs in any environment"* (3)

## Context

A Vite build bakes every `import.meta.env.*` value into static JavaScript. If the API URL is one
of them, the image built for staging is a different artefact from the one built for prod: what
was tested is not what ships, and the image's `${{ github.sha }}` tag no longer identifies what
is running (build-once-deploy-many, PDF §2.1). The frontend still needs some per-environment
values that are *not* URLs: environment name, version, stats poll interval, a feature toggle.

## Options considered

| | Where the API URL lives | Rebuild per env? | Extra moving parts | CORS needed? |
|---|---|---|---|---|
| A. `VITE_API_URL` at build time | in the bundle, as a string literal | **yes** | none | yes (cross-origin) |
| B. `/config.js` generated at container start | `window.__CIVICPULSE__.apiUrl` | no | entrypoint script | yes (cross-origin) |
| C. nginx proxies `/api` (same origin) | **nowhere** — the app calls the relative `/api` | no | nginx `location /api/` | no |
| C + B. proxy for the URL, `/config.js` for non-URL flags | nowhere | no | both | no |

## Decision

**C + B.** The API is always same-origin behind nginx, and the one line that guarantees
build-once-deploy-many is:

```ts
// frontend/src/api/config.ts:3
export const API_BASE = "/api";
```

backed by `proxy_pass http://$backend_upstream;` in `frontend/nginx.conf`. No environment
variable can make that line wrong, because it contains no environment.

Non-URL flags come from `/config.js`, written at container start by
`frontend/docker-entrypoint.d/10-config.sh` from `APP_ENV`, `GIT_SHA`, `STATS_POLL_MS`,
`SHOW_CACHE_BADGE`. `index.html` loads it **before** the bundle; `config.ts` reads it with typed
defaults so `vite dev` works without it. The script **validates every value** (word characters,
integers, `true|false`) before writing it, because `config.js` is served to every browser — an
unvalidated env var would be a script-injection vector. It never holds a credential.

The proxy's upstream is also set at boot (`BACKEND_UPSTREAM`, default `backend:8000`) and resolved
**per request** via the container's own nameserver, so nginx starts even when the backend is not
up yet, and Kubernetes can pass an FQDN (nginx's resolver ignores DNS search domains).

## Consequences

- One image, any environment: `docker run -e APP_ENV=dev` and `-e APP_ENV=prod` on the **same
  digest** serve different `/config.js` (evidence: `docs/evidence/runtime-config.txt`, Gate 8).
- No CORS on the production path — the browser only ever talks to its own origin.
- The same `/api` prefix works under `vite dev` (Vite proxy), compose (nginx → `backend`) and
  Kubernetes (Ingress `/api` → backend, or nginx with an FQDN upstream).
- `/config.js` is served `Cache-Control: no-store`; hashed assets are `immutable`.
- **CORS consequence (contradiction A7).** PDF §1.3 says a real frontend "forces CORS", and the
  proxy removes that need. So the competency is kept demonstrable separately: the backend ships a
  restrictive, tested `CORSMiddleware` for the direct-origin dev path (DEV-A, Phase 3), exposing
  `X-Cache`/`X-Request-ID` so the Stats badge still works cross-origin.

## Rejected alternatives and why

- **A — build-time `VITE_API_URL`.** Rejected outright: it is exactly the failure PDF §2.1 names.
  One image per environment; the SHA tag stops identifying the running artefact.
- **B alone — API URL in `/config.js`.** Build-once-deploy-many holds, but every request becomes
  cross-origin: CORS preflights on each `POST`/`PATCH`, response headers (`X-Cache`) invisible
  unless explicitly exposed, and the URL still has to be kept correct per environment — a second
  thing to get wrong for no benefit over C.
- **C alone — proxy only, no `/config.js`.** Leaves nowhere to put non-URL per-environment flags
  without a rebuild; the poll interval and version badge would be baked in.
- **Static `proxy_pass http://backend:8000/api/;` (the plan's first draft).** Resolved once at
  nginx start: the container exits if `backend` isn't resolvable yet, and the short name never
  resolves inside Kubernetes. Replaced by the per-request variable upstream above.
