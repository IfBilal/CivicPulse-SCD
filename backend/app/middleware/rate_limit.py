"""Rate limit middleware — innermost, scoped to `POST /api/complaints` only
(`06-BACKEND-CORE.md §3`). Phase 3 stub: in-memory fixed-window counter, gated on
`settings.ratelimit_enabled`. The distributed Redis Lua sliding-window limiter is Phase 5 scope
(`09-CACHE-RATELIMIT.md`) — see `docs/ENGINEERING-NOTES.md` "RateLimitMiddleware is an
in-memory stub" for why this is intentionally not production-grade yet.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.errors import error_response
from app.settings import Settings

_SCOPED_METHOD = "POST"
_SCOPED_PATH = "/api/complaints"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._settings = settings
        self._enabled = settings.ratelimit_enabled
        self._limit = settings.ratelimit_requests
        self._window_s = settings.ratelimit_window_s
        # client_key -> (window_start_epoch_s, count). Process-local; resets on restart.
        self._buckets: dict[str, tuple[float, int]] = {}

    def _client_key(self, request: Request) -> str:
        client = request.client
        return client.host if client else "unknown"

    def _is_over_limit(self, key: str) -> int | None:
        """Returns `None` if under limit, else the seconds until the window resets."""
        now = time.monotonic()
        window_start, count = self._buckets.get(key, (now, 0))
        if now - window_start >= self._window_s:
            window_start, count = now, 0
        count += 1
        self._buckets[key] = (window_start, count)
        if count > self._limit:
            retry_after = max(1, int(self._window_s - (now - window_start)))
            return retry_after
        return None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        in_scope = request.method == _SCOPED_METHOD and request.url.path == _SCOPED_PATH
        if not self._enabled or not in_scope:
            return await call_next(request)

        retry_after = self._is_over_limit(self._client_key(request))
        if retry_after is not None:
            resp: JSONResponse = error_response(
                request,
                429,
                "rate_limited",
                "Too many requests.",
                headers={"Retry-After": str(retry_after)},
            )
            return resp
        return await call_next(request)
