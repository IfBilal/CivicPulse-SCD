"""`client_ip()` unit tests -- `09-CACHE-RATELIMIT.md section 4.3`, E13/E14 plus the
short-header edge case the spec calls out by name."""

import pytest
from starlette.requests import Request

from app.providers.ratelimit.client_ip import client_ip

pytestmark = pytest.mark.unit


def _make_request(xff: str | None, peer_host: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    scope = {
        "type": "http",
        "headers": headers,
        "client": (peer_host, 12345),
        "method": "GET",
        "path": "/",
        "query_string": b"",
    }
    return Request(scope)


def test_xff_spoof_ignored() -> None:
    """E13: two requests with different forged left-most XFF values map to the same
    bucket -- proves counting-from-the-right actually defeats a naive spoof."""
    hops = 1
    req_a = _make_request("9.9.9.9, 203.0.113.7", peer_host="203.0.113.7")
    req_b = _make_request("1.1.1.1, 203.0.113.7", peer_host="203.0.113.7")

    ip_a = client_ip(req_a, hops)
    ip_b = client_ip(req_b, hops)

    assert ip_a == ip_b == "203.0.113.7"


def test_xff_hops_configurable() -> None:
    """E14: hops=2, '1.1.1.1, 2.2.2.2, 3.3.3.3' -> resolves to '2.2.2.2'."""
    req = _make_request("1.1.1.1, 2.2.2.2, 3.3.3.3")
    assert client_ip(req, 2) == "2.2.2.2"


def test_short_xff_falls_back_to_peer() -> None:
    """A header with fewer entries than hops does not index out of range or trust the
    client -- falls back to the peer (proxy) address instead of the attacker-controlled
    value."""
    req = _make_request("1.1.1.1", peer_host="10.0.0.99")  # only 1 entry, hops=2
    result = client_ip(req, 2)  # must not raise IndexError
    assert result == "10.0.0.99"


def test_zero_hops_uses_peer_directly() -> None:
    req = _make_request("1.1.1.1, 2.2.2.2", peer_host="10.0.0.5")
    assert client_ip(req, 0) == "10.0.0.5"


def test_missing_xff_header_falls_back_to_peer() -> None:
    req = _make_request(None, peer_host="10.0.0.7")
    assert client_ip(req, 1) == "10.0.0.7"


def test_xff_with_stray_whitespace_and_empty_segments() -> None:
    req = _make_request(" 1.1.1.1 ,, 2.2.2.2 ", peer_host="9.9.9.9")
    # Empty segments filtered out; hops=1 -> rightmost real entry.
    assert client_ip(req, 1) == "2.2.2.2"
