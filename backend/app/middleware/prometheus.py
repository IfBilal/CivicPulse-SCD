"""Prometheus middleware — `path_template` labels ONLY, never a raw path (CLAUDE.md HARD rule
8: one violation is an unbounded-cardinality incident, not a style nit). Skips `/metrics`
itself so the scrape doesn't measure its own latency into the histogram."""

import time

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path_template", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path_template"],
)

_METRICS_PATH = "/metrics"


def _path_template(request: Request) -> str:
    """The matched route's path template (`/api/complaints/{id}`), never the literal URL. A
    request that matched no route (404) gets `"unmatched"` — CLAUDE.md HARD rule 8 verbatim."""
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return str(route.path)
    return "unmatched"


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path == _METRICS_PATH:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_s = time.monotonic() - start

        path_template = _path_template(request)
        REQUEST_COUNT.labels(
            method=request.method, path_template=path_template, status_code=response.status_code
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, path_template=path_template).observe(
            duration_s
        )
        return response
