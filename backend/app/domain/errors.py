"""Domain exceptions — carry data, not HTTP status (`06-BACKEND-CORE.md §7`).

Only the registered exception handler in `app/errors.py` knows these map to 409/404/429.
`services/` may raise these; it may never import a status code (CLAUDE.md §3, `make lint-layers`
greps for `status_code` under `services/`).
"""

from uuid import UUID

from app.domain.enums import Status


class NotFound(Exception):
    """A resource the caller asked for by id does not exist."""

    def __init__(self, cid: UUID) -> None:
        self.cid = cid
        super().__init__(f"complaint {cid} not found")


class InvalidTransition(Exception):
    """`src -> dst` is not in `TRANSITIONS`, or the conditional UPDATE lost a race."""

    def __init__(self, src: Status, dst: Status) -> None:
        self.src = src
        self.dst = dst
        super().__init__(f"cannot transition {src} -> {dst}")


class RateLimited(Exception):
    """Caller is over the configured rate limit. `retry_after_s` is seconds, not a timestamp."""

    def __init__(self, retry_after_s: int) -> None:
        self.retry_after_s = retry_after_s
        super().__init__(f"rate limited, retry after {retry_after_s}s")


class NotReady(Exception):
    """A `/ready` dependency check failed, or the app is draining (`04-CONTRACTS.md §6.8`).

    `checks` is the full per-dependency status map (including the passing ones); `failed` is
    the subset of keys that did not pass. The route never builds the 503 body itself — only
    the registered handler does, keeping one envelope shape for every non-2xx response.
    """

    def __init__(self, checks: dict[str, str], failed: list[str]) -> None:
        self.checks = checks
        self.failed = failed
        super().__init__(f"not ready: {', '.join(failed)}")
