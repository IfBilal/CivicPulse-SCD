"""E16, partial -- `09-CACHE-RATELIMIT.md section 4.5`: "Our choice: fail-open, bounded.
Allow the request, but force TRIAGE_PROVIDER degradation for that request to rules."

**Deferred, disclosed:** the "degrade the actual triage provider to rules" half needs
Phase 4's provider factory (`app/providers/triage/`), which is empty on this branch
(only `__pycache__` -- Phase 4's `feat/ai-triage` hasn't merged into `dev` yet, same
branch-divergence gap noted throughout `docs/AI-USAGE.md`'s Phase 5 kickoff entry). What
CAN be verified now and is verified below: a Redis outage during the rate-limit check
itself must not turn into a 503 or a blocked request -- the caller (middleware, once it
exists) is expected to catch `RateLimiter.check()`'s propagated exception and allow the
request through. `RateLimiter.check()` deliberately does not swallow Redis errors itself
(see its docstring) -- the fail-open decision belongs to the caller, which is the only
layer that knows what "allow" and "degrade the provider" both mean. This test proves the
error propagates cleanly (so a caller's `try/except -> allow` wrapper is exercisable and
correct), which is the verifiable half of E16 in this sandbox.
"""

import pytest

from app.providers.ratelimit.limiter import RateLimiter
from tests.unit.fakes import FakeRedis

pytestmark = pytest.mark.unit


async def test_ratelimit_check_raises_on_redis_down_not_silently_false() -> None:
    """`check()` must propagate the Redis failure rather than silently returning
    `(False, ...)` -- a silent False would fail-CLOSED (block every request), which is
    the opposite of the spec's chosen posture. The caller decides to fail-open by
    catching this and allowing the request."""
    redis = FakeRedis(fail_on={"evalsha"})
    limiter = RateLimiter(redis)

    with pytest.raises(Exception):  # noqa: B017 -- any Redis-layer failure qualifies
        await limiter.check("rl:1.2.3.4:0", limit=10, window_s=60)


async def test_fail_open_wrapper_allows_request_when_redis_down() -> None:
    """Simulates the middleware-layer wrapper this phase's spec describes (section 4.5):
    on a `RateLimiter.check()` failure, allow the request. Written against the real
    `RateLimiter`, not a stub, so it would fail if `check()` stopped raising cleanly."""
    redis = FakeRedis(fail_on={"evalsha"})
    limiter = RateLimiter(redis)

    async def fail_open_check(key: str, limit: int, window_s: int) -> bool:
        try:
            allowed, _ = await limiter.check(key, limit, window_s)
            return allowed
        except Exception:
            return True  # fail-open: Redis down -> allow the request

    allowed = await fail_open_check("rl:1.2.3.4:0", 10, 60)
    assert allowed is True
