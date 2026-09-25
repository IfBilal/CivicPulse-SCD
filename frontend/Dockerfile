# Build context: repo root (compose: `context: .`). Ignore file: frontend/Dockerfile.dockerignore.
# ── stage 1: build the static bundle ───────────────────────────────────────
FROM node:22.11.0-alpine AS build
WORKDIR /app
# deps BEFORE source: cache-correct
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build                                           # → /app/dist (no sourcemaps, no MSW)

# ── stage 2: runtime — nginx + dist/ only. No Node, no node_modules, no source. ─
# -slim: nginx's own variant without GeoIP/XSLT/image-filter/njs — dynamic modules nginx.conf
# never loads, which otherwise add ~37 MB the app gets no benefit from (12-DOCKER-COMPOSE.md §1:
# "runtime 45-55 MB"; the non-slim tag alone is 80 MB before any app content is even added).
FROM nginx:1.27.5-alpine-slim AS runtime
RUN addgroup -g 10001 -S app && adduser -u 10001 -S app -G app \
 && rm -f /etc/nginx/conf.d/default.conf \
      /docker-entrypoint.d/10-listen-on-ipv6-by-default.sh \
      /docker-entrypoint.d/20-envsubst-on-templates.sh \
 && mkdir -p /tmp/nginx \
 && chown -R app:app /tmp/nginx /usr/share/nginx/html /var/cache/nginx
COPY --chown=app:app frontend/nginx.conf /etc/nginx/nginx.conf
COPY --chown=app:app --chmod=0755 frontend/docker-entrypoint.d/10-config.sh /docker-entrypoint.d/10-config.sh
COPY --from=build --chown=app:app /app/dist /usr/share/nginx/html
RUN rm -f /usr/share/nginx/html/mockServiceWorker.js    # MSW worker is dev-only
USER app
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=2s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
CMD ["nginx", "-g", "daemon off;"]
