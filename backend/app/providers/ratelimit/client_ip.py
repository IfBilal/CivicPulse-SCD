"""Client IP resolution -- `09-CACHE-RATELIMIT.md section 4.3` verbatim (contradiction A9).

The request reaches the backend through nginx (and, in Kubernetes, the Ingress
controller too), so `request.client.host` is the *proxy's* IP, not the citizen's --
naive use would bucket every citizen behind one shared limit.

`X-Forwarded-For` is client-appendable: a hostile client can send its own forged
`X-Forwarded-For: 1.2.3.4` and rotate that value per request. Counting from the LEFT
would let them bypass the limiter entirely. The rightmost `trusted_hops` entries are the
ones our own infrastructure appended, so we always count from the right.
"""

from starlette.requests import Request


def client_ip(request: Request, trusted_hops: int) -> str:
    if trusted_hops <= 0:
        return _peer_host(request)
    xff = [p.strip() for p in request.headers.get("X-Forwarded-For", "").split(",") if p.strip()]
    if len(xff) < trusted_hops:
        return _peer_host(request)  # header shorter than expected -> do not trust
    return xff[-trusted_hops]  # count from the RIGHT, never the left


def _peer_host(request: Request) -> str:
    client = request.client
    return client.host if client is not None else "unknown"
