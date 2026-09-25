"""Request ID middleware — must be outermost (`06-BACKEND-CORE.md §3.1`).

`ContextVar`, not thread-local: async tasks inherit the context, so a log line emitted three
awaits deep inside `TriageService` carries the id with no parameter threading.
"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def _is_uuid4(candidate: str) -> bool:
    """Reject hostile input (e.g. `"x\\nlevel=ERROR"` — a log-injection vector) by requiring a
    well-formed UUIDv4. Anything else, including a syntactically valid non-v4 UUID, is replaced
    with a freshly generated one rather than echoed."""
    try:
        parsed = uuid.UUID(candidate)
    except (ValueError, AttributeError, TypeError):
        return False
    return parsed.version == 4 and str(parsed) == candidate.lower()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if _is_uuid4(incoming) else str(uuid.uuid4())
        token = request_id_var.set(rid)
        request.state.request_id = rid
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response
