"""Access log middleware — sits above Prometheus so the log line can report the duration
Prometheus also measured (`06-BACKEND-CORE.md §3`: "log last-in-first-out so the log line is
emitted after metrics are recorded"). Probe paths are filtered out to keep the log readable
(`06-BACKEND-CORE.md §5`: probes fire every 2-10s x N pods)."""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger("app.access")

_UNLOGGED_PATHS = frozenset({"/health", "/ready", "/metrics"})


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        if request.url.path not in _UNLOGGED_PATHS:
            log.info(
                "http.request",
                extra={
                    "extra_fields": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    }
                },
            )
        return response
