"""Rate limit middleware — innermost, scoped to `POST /api/complaints` only
(`06-BACKEND-CORE.md §3`). Wired to the real distributed limiter
(`app/providers/ratelimit/limiter.py`, `09-CACHE-RATELIMIT.md §4`) — Phase 5's `RateLimiter`
(atomic Lua `INCR`+`EXPIRE`+`TTL` via `EVALSHA`) and `client_ip()` (right-to-left
`X-Forwarded-For` trusted-hop resolution, §4.3).

Reconciled at the Phase 3+4+5 merge into `dev` (2026-09-25): this file previously held an
in-memory fixed-window stub (Phase 3, `docs/ENGINEERING-NOTES.md` — "process-local, resets on
restart, undercounts by a factor of replica count under multiple pods") that existed only to
prove middleware ordering/scoping before Phase 5's real limiter existed on the same branch. That
stub is gone; this is the real thing.

`RateLimiter` is constructed lazily, on first use inside `dispatch()`, not in `__init__` —
Starlette builds middleware instances at app-startup time (`create_app()`), before
`app.state.redis` exists (that's set inside the `lifespan` context manager, which runs after
middleware registration). Reading `request.app.state.redis` inside `dispatch()` instead means
this middleware never needs its own Redis connection lifecycle; it borrows the one the app
already owns and closes on shutdown."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.providers.ratelimit.client_ip import client_ip
from app.providers.ratelimit.limiter import RateLimiter
from app.settings import Settings

_SCOPED_METHOD = "POST"
_SCOPED_PATH = "/api/complaints"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: object, settings: Settings, *, limiter: RateLimiter | None = None
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._settings = settings
        self._enabled = settings.ratelimit_enabled
        self._limit = settings.ratelimit_requests
        self._window_s = settings.ratelimit_window_s
        self._trusted_hops = settings.trusted_proxy_hops
        # `limiter`, if given, is used as-is — lets a test inject a `RateLimiter` built on a
        # fake Redis client instead of the real `app.state.redis` (which doesn't exist yet
        # at __init__ time anyway; see module docstring), the same optional-override pattern
        # `TriageService.__init__`'s `ring` param uses.
        self._limiter: RateLimiter | None = limiter

    def _limiter_for(self, request: Request) -> RateLimiter:
        # One RateLimiter per app process, lazily built on first use — app.state.redis
        # doesn't exist yet when __init__ runs (see module docstring).
        if self._limiter is None:
            self._limiter = RateLimiter(request.app.state.redis)
        return self._limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        in_scope = request.method == _SCOPED_METHOD and request.url.path == _SCOPED_PATH
        if not self._enabled or not in_scope:
            return await call_next(request)

        key = f"rl:{client_ip(request, self._trusted_hops)}"
        try:
            allowed, retry_after = await self._limiter_for(request).check(
                key, self._limit, self._window_s
            )
        except Exception:
            # `09-CACHE-RATELIMIT.md §4.5`: fail-open, bounded — a Redis outage during a
            # rate-limit check must not become a full intake outage. `RateLimiter.check()`
            # deliberately doesn't catch Redis errors itself (its own docstring: "the
            # fail-open decision belongs to the caller, which knows whether 'Redis is down'
            # should mean 'allow the request'") — this is that caller making that call.
            return await call_next(request)

        if not allowed:
            from app.middleware.ratelimit import rate_limited_response

            return rate_limited_response(
                request, limit=self._limit, window_s=self._window_s, retry_after_s=retry_after
            )
        return await call_next(request)
