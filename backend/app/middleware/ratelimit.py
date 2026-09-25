"""Rate-limit 429 response builder -- `09-CACHE-RATELIMIT.md section 4.2/4.4`.

Written before Phase 3's middleware stack (`feat/backend-api`) merged into `dev`, so this
file originally shipped only the response-shape builder with no middleware class to call
it -- `app/middleware/rate_limit.py` (Phase 3's file, same directory) now imports
`rate_limited_response` from here and is the real, wired `RateLimitMiddleware`, built on
this module plus `app/providers/ratelimit/{limiter,client_ip}.py`. Reconciled at the
Phase 3+4+5 merge into `dev` (2026-09-25) -- see that file's own docstring for the wiring.
"""

import time

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.errors import error_response


def rate_limited_response(
    request: Request,
    *,
    limit: int,
    window_s: int,
    retry_after_s: int,
    now: float | None = None,
) -> JSONResponse:
    """The 429 response contract, section 4.2:

    `Retry-After` is integer seconds, clamped to >= 1 (a `Retry-After: 0` invites an
    immediate retry). `X-RateLimit-Reset` is a Unix timestamp (section 4.2's own example:
    `Retry-After: 37` alongside `X-RateLimit-Reset: 1757830860`) -- `now + retry_after`,
    not the same value as `Retry-After` itself. `now` is injectable for deterministic
    tests; defaults to the wall clock.
    """
    retry_after = max(1, int(retry_after_s))
    clock = time.time() if now is None else now
    reset_at = int(clock) + retry_after
    return error_response(
        request,
        429,
        "rate_limited",
        f"Rate limit exceeded: {limit} requests per {window_s}s.",
        details={
            "limit": limit,
            "window_seconds": window_s,
            "retry_after_seconds": retry_after,
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(reset_at),
        },
    )
