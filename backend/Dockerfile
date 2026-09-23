# Build context: repo root (compose: `context: .`). Ignore file: backend/Dockerfile.dockerignore.
# ── stage 1: build the virtualenv from the hash-locked requirements ─────────
FROM python:3.12.7-slim-bookworm AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
# deps BEFORE source: cache-correct
COPY backend/requirements.lock ./
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --require-hashes --no-deps -r requirements.lock

# ── stage 2: runtime — venv + app code only, non-root ──────────────────────
FROM python:3.12.7-slim-bookworm AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd -g 10001 -r app && useradd -u 10001 -r -g app -s /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# The ignore file allow-lists app/, alembic/, alembic.ini — so the Alembic tree (DEV-A, Phase 2)
# is picked up automatically once it exists, without this line changing.
COPY --chown=app:app backend/ ./
ARG GIT_SHA=dev
ENV APP_VERSION=${GIT_SHA}
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD ["python","-c","import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).status==200 else 1)"]
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1","--timeout-graceful-shutdown","25","--no-access-log"]
