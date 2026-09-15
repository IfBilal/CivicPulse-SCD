# 11 — FRONTEND (React 18 · Vite · TypeScript · nginx · 18 marks)

> **Owner:** DEV-B (DEV-A takes Stats in Swap 2) · **Days:** 2 PM–3, 6–7 · **Rubric:** B (18)
> `00-SPEC.md §2.1`: *"The frontend owns presentation and interaction; it owns no business rules."*

---

## 1. The ownership rule, made mechanical

> *"the moment your React code contains a list of valid status transitions, you have two sources of
> truth and one of them will rot."*

There is **no** `TRANSITIONS` constant in the frontend. The Dashboard renders the transition
buttons from the server's own 409 payload and from the complaint's current status, and if a
transition is disallowed the server says so:

```ts
// The ONLY status knowledge in the frontend: which statuses exist (from the generated enum).
// Which transitions are legal is asked, never assumed.
import type { components } from "../api/schema";
type Status = components["schemas"]["Status"];   // generated from the backend enum
```

Enforced by a lint rule and a test:

```bash
# in make check
! grep -rn "in_progress.*resolved\|TRANSITIONS\|allowedNext" frontend/src \
  || (echo "business rule leaked into the frontend"; exit 1)
```

The correct pattern: attempt, catch the 409, render `error.message` **verbatim**, and disable the
button optimistically only for `resolved`/`rejected`, which the server tells us via
`details.terminal` on the first refusal (or which the UI simply learns by trying).

> A cleaner, optional upgrade worth 30 seconds of viva time: have `GET /api/complaints/{id}`
> return `allowed_transitions: Status[]` computed from `TRANSITIONS` server-side. The frontend
> renders exactly those buttons and still holds zero rules. Mention it as the design you would ship
> next; it is the difference between obeying §2.1 and understanding it.

---

## 2. Runtime configuration (ADR-0002 · Rubric B, 3 marks)

> §2.1: *"A Vite build bakes `import.meta.env` values into static JavaScript at build time. If your
> API URL is baked in, your image is environment-specific and you have destroyed
> build-once-deploy-many for the frontend."*

**Decision: nginx `/api` proxy is primary; `/config.js` carries non-URL runtime flags.**

### 2.1 Primary — same-origin proxy, so there is no API URL at all

```ts
// frontend/src/api/config.ts
export const API_BASE = "/api";   // ← the entire solution. No env var can make this wrong.
```

```nginx
# frontend/nginx.conf
server {
  listen 8080;                      # non-root cannot bind < 1024
  server_name _;
  root /usr/share/nginx/html;

  location = /healthz { return 200 "ok\n"; add_header content-type text/plain; }

  location /api/ {
    proxy_pass http://backend:8000/api/;       # ← service name. NEVER localhost (§5.3 −8)
    proxy_http_version 1.1;
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;   # §09 4.3
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Request-ID      $request_id;                  # nginx generates if absent
    proxy_read_timeout 30s;                    # > the 12s triage budget, < the client's patience
    proxy_connect_timeout 2s;
  }

  location / { try_files $uri $uri/ /index.html; }        # SPA fallback

  gzip on; gzip_types application/javascript text/css application/json;
  add_header X-Content-Type-Options nosniff always;
  add_header X-Frame-Options DENY always;
  add_header Referrer-Policy no-referrer always;
}
```

**This is the answer to §5.2 question 3** — *"the exact line guaranteeing build-once-deploy-many"*
is `export const API_BASE = "/api";` in `frontend/src/api/config.ts`, backed by `proxy_pass` in
`nginx.conf`. What breaks without it: the bundle contains `https://api.staging.example` as a string
literal, so the staging image and the prod image are different artefacts, so what you tested is not
what you shipped, so the `${{ github.sha }}` tag on the image is a lie.

### 2.2 Secondary — `/config.js` generated at container start

Non-URL runtime flags (feature toggles, the display name, the poll interval) still need to vary per
environment without a rebuild:

```sh
# frontend/docker-entrypoint.d/10-config.sh   — nginx:alpine runs /docker-entrypoint.d/*.sh at boot
set -eu
cat > /usr/share/nginx/html/config.js <<EOF
window.__CIVICPULSE__ = {
  env: "${APP_ENV:-dev}",
  version: "${GIT_SHA:-dev}",
  statsPollMs: ${STATS_POLL_MS:-15000},
  showCacheBadge: ${SHOW_CACHE_BADGE:-true}
};
EOF
```

`index.html` loads `<script src="/config.js"></script>` **before** the bundle. `config.ts` reads
`window.__CIVICPULSE__` with typed defaults so the app still runs if the file is missing (local
`vite dev`).

**Never put a secret in here.** §2.1: *"anything in a browser bundle is public, and 'it's minified' is
not a defence."* `config.js` is served to every visitor. The test:

```bash
! grep -rniE "gsk_|AIza|password|secret|token" frontend/src frontend/public frontend/dist \
  || (echo "secret in browser-reachable code"; exit 1)
```

### 2.3 Proving build-once-deploy-many (Gate 8 evidence)

```bash
docker build -t fe:test frontend/
docker run -d -e APP_ENV=dev  -p 8091:8080 fe:test
docker run -d -e APP_ENV=prod -p 8092:8080 fe:test     # SAME image, different config
curl -s localhost:8091/config.js; curl -s localhost:8092/config.js
docker inspect fe:test --format '{{.Id}}'              # one digest, two environments
```
Tee to `docs/evidence/runtime-config.txt`.

---

## 3. The three views

### 3.1 Submit (Rubric B, 5 marks)

| Requirement | Implementation |
|---|---|
| Free text, location, optional contact | controlled inputs bound to `ComplaintCreate` |
| Client validation **mirroring** server rules | bounds come from the **generated schema**, not hand-typed: `schema.components.schemas.ComplaintCreate.properties.text.minLength`. §2.1 says *mirrors without replacing* — generating the mirror is how you guarantee it never drifts |
| **Honest loading state** | not a 200 ms spinner. A three-stage state: `submitting` → after 1.5 s *"Classifying with AI…"* → after 6 s *"The model is slow — we'll fall back to keyword rules if needed."* §2.1: *"Render the loading state honestly — AI calls take seconds."* This is also user-facing documentation of the fallback design |
| Render category, priority, AI summary **and provider** | a result card with a `ProviderBadge`: `llm:groq` = solid, `rules:fallback` = outlined + tooltip *"AI provider unavailable; classified by keyword rules"*. **Showing the degradation to the citizen is the honest choice**, and it is what makes the fallback demo legible on video |
| Field-level errors | `error.fields[]` mapped to inputs by `field` name; the server's `message` rendered under the input |
| Disabled submit while in flight | prevents the double-POST that would otherwise be absorbed by the triage cache and look like it worked |

### 3.2 Dashboard (Rubric B, 5 marks)

- **Pagination** — page controls driven by `total`/`pages` from the envelope; page size selector
  capped at 100 by the generated type.
- **Filters** — category, priority, status; multi-select; serialised as repeated query params;
  reflected in the URL (`?status=open&status=in_progress&page=2`) so a filtered view is
  shareable and a refresh does not reset the operator's context.
- **Status transitions** — a button per candidate next status; on click, `PATCH`.
- **The 409, verbatim** — this is the marked line, so it gets its own test:

```tsx
catch (e) {
  if (e instanceof ApiError && e.status === 409) {
    setBanner({ kind: "conflict", text: e.body.error.message });  // ← NOT a mapped string
  }
}
```
```tsx
// tests/Dashboard.transition.test.tsx
it("surfaces the server's 409 message verbatim", async () => {
  server.use(http.patch("/api/complaints/:id/status", () => HttpResponse.json(
    { error: { code: "invalid_status_transition",
               message: "Invalid status transition: resolved -> in_progress. 'resolved' is terminal.",
               details: { from: "resolved", to: "in_progress", terminal: true } } },
    { status: 409 })));
  await user.click(screen.getByRole("button", { name: /in progress/i }));
  expect(await screen.findByText(
    "Invalid status transition: resolved -> in_progress. 'resolved' is terminal."
  )).toBeVisible();
});
```
Asserting the **exact string** is what makes the test prove the requirement. A regex like
`/invalid/i` would pass against a generic error message and prove nothing.

### 3.3 Stats (Rubric B, 3 marks)

- Aggregate counts by category and priority (and status, from the merge-conflict field).
- **`X-Cache` badge** — `HIT` green with *"cached 12 s ago"* from `cache_age_seconds`, `MISS`
  amber with *"computed just now"*.
- Reading a response header requires the fetch wrapper to return it:

```ts
const res = await fetch(`${API_BASE}/stats`);
return { data: await res.json(), cache: res.headers.get("X-Cache") };
```
Cross-origin (the `vite dev` path) this only works because the backend sets
`expose_headers=["X-Cache", …]` (`06-BACKEND-CORE.md §3.3`). Same-origin through the proxy it
works regardless. **Test both**, because the dev path is the one that silently breaks.
- Poll every `statsPollMs` (default 15 s) so the badge visibly flips MISS→HIT→MISS across a TTL
  boundary and an invalidation. On camera, that flipping badge is the cache demo.

### 3.4 Error boundary (§2.1, required engineering)

```tsx
class ErrorBoundary extends React.Component<Props, State> {
  static getDerivedStateFromError(e: Error) { return { error: e }; }
  componentDidCatch(e: Error, info: React.ErrorInfo) { console.error({ e, info }); }
  render() { return this.state.error ? <Fallback requestId={lastRequestId()} /> : this.props.children; }
}
```
The fallback UI shows the **last `X-Request-ID`** the client saw, with a copy button. That turns
*"it broke"* into a grep-able join key (`10-OBSERVABILITY.md §3`) and is a 10-line feature that
reads as production experience.

Note what an error boundary does **not** catch: event handlers, async code, SSR. API errors are
handled by the client wrapper; the boundary is for render-time crashes. Say that distinction in the
PR — knowing the limits of a tool is the point.

---

## 4. The typed client (§2.1: *generated from or checked against the OpenAPI schema*)

```
backend app factory ──▶ make openapi ──▶ openapi.json
                                             │
                                  openapi-typescript
                                             ▼
                                frontend/src/api/schema.d.ts   (committed, generated)
                                             │
                                    client.ts (hand-written, ~60 lines, fully typed)
```

```ts
export class ApiError extends Error {
  constructor(readonly status: number, readonly body: ErrorEnvelope) { super(body.error.message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<{ data: T; res: Response }> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json",
               "x-request-id": crypto.randomUUID(), ...init?.headers },
  });
  const body = res.status === 204 ? null : await res.json();
  if (!res.ok) throw new ApiError(res.status, body as ErrorEnvelope);
  return { data: body as T, res };
}
```

**CI drift gate** (`15-CICD.md §3.1`): `make gen-client && git diff --exit-code`. A backend contract
change that the frontend has not absorbed becomes a **red `tsc`** in CI instead of `undefined` in
the demo video. That is the mechanism §2.1 is asking for, and it is worth one sentence in the
README: *"the frontend cannot compile against a contract it does not have."*

---

## 5. Multi-stage image (Rubric G, part of 4 marks; §3.1: **under ~60 MB**)

```dockerfile
# frontend/Dockerfile
FROM node:22.11.0-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./          # ← deps BEFORE source: cache-correct layer order
RUN npm ci --no-audit --no-fund
COPY . .
ARG GIT_SHA=dev
RUN npm run build                                # → /app/dist

FROM nginx:1.27.2-alpine AS runtime
RUN addgroup -g 10001 -S app && adduser -u 10001 -S app -G app \
 && mkdir -p /var/cache/nginx /var/run /tmp/nginx \
 && chown -R app:app /var/cache/nginx /var/run /usr/share/nginx/html /tmp/nginx
COPY --chown=app:app frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --chown=app:app frontend/docker-entrypoint.d/10-config.sh /docker-entrypoint.d/10-config.sh
COPY --from=build --chown=app:app /app/dist /usr/share/nginx/html
USER app
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=2s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
CMD ["nginx", "-g", "daemon off;"]
```

**The non-root nginx gotchas, all four of them** — this is where teams lose an afternoon:

1. `listen 8080`, not 80 — an unprivileged process cannot bind a port below 1024.
2. `pid /tmp/nginx.pid;` in the main config (add via `nginx.conf` include or a
   `/etc/nginx/nginx.conf` patch) — the default `/var/run/nginx.pid` is root-owned.
3. `client_body_temp_path`, `proxy_temp_path` etc. must be writable — point them under
   `/tmp/nginx` or `chown` the defaults.
4. The official image's entrypoint runs `/docker-entrypoint.d/*.sh` **as the current user**, so the
   script must be executable and must write to a directory `app` owns.

**Size discipline.** The runtime stage contains `dist/` + nginx and **no Node, no `node_modules`,
no source** (§3.1). Measure and commit:

```bash
docker build --target build   -t fe:build .   && docker images fe:build   --format '{{.Size}}'
docker build --target runtime -t fe:runtime . && docker images fe:runtime --format '{{.Size}}'
```
Expected order of magnitude: build stage 400–600 MB, runtime 45–55 MB. Over ~60 MB means
something from the build stage leaked — check for a stray `COPY . .` in the runtime stage or a
`dist/` containing sourcemaps (`build.sourcemap: false` for prod, or ship them to a separate
artefact).

`frontend/.dockerignore`:
```
node_modules
dist
coverage
.git
.env*
*.log
tests
.vite
```

---

## 6. The five component tests (Rubric B, 2 marks — *meaningful*)

MSW intercepts at the network layer, so the component under test uses the **real** client and the
**real** types. Mocking `client.ts` would test the mock.

| # | File | Asserts | Why meaningful |
|---|---|---|---|
| 1 | `Submit.validation.test.tsx` | 9-char text ⇒ submit blocked, bound message matches the generated `minLength` | proves the mirror is generated, not typed |
| 2 | `Submit.result.test.tsx` | 201 with `triaged_by:"rules:fallback"` ⇒ the outlined provider badge + tooltip render | proves the fallback is user-visible |
| 3 | `Submit.loading.test.tsx` | fake timers: at 1.6 s the *"Classifying with AI…"* copy appears | proves the *honest* loading state, not a spinner |
| 4 | `Dashboard.transition.test.tsx` | 409 ⇒ the exact server string appears in the DOM | the verbatim-409 marked line |
| 5 | `Stats.cache.test.tsx` | `X-Cache: HIT` + `cache_age_seconds: 12` ⇒ *"cached 12 s ago"* | the cache-badge marked line |
| 6 | `ErrorBoundary.test.tsx` | a throwing child ⇒ fallback UI with the last request id | bonus sixth; the boundary is required engineering |
| 7 | `Dashboard.filters.test.tsx` | selecting two statuses produces `?status=open&status=in_progress` | proves repeated-param serialisation matches the contract |

> "Meaningful" is doing work in that rubric line. A snapshot test of a `<Button>` is not meaningful.
> Each test above maps to a **specific sentence in §2.1**, and the mapping is written as a comment
> at the top of each file citing the clause.

Config: `vitest` + `@testing-library/react` + `jsdom` + `msw@2`, `--coverage` reported but not
gated (the spec gates backend coverage only).

---

## 7. Accessibility and honesty (cheap, and it reads well)

- Every input has a `<label htmlFor>`; errors are `aria-live="polite"` and `aria-describedby`-linked.
- The loading state is `role="status"`, so a screen reader announces *"Classifying with AI"* rather
  than silence for six seconds.
- Buttons for terminal statuses are `disabled` **and** `aria-disabled` with a title explaining why —
  the explanation coming from the server's message, not a local string.
- Colour is never the only channel: the provider badge differs by outline and by text, the cache
  badge by icon and by text. A marker watching a compressed video on a phone can still read it.
