"""A genuinely unmatched route (no path this app declares) must still return the one
`ErrorEnvelope` shape — `app/errors.py`'s own docstring: "one envelope for every non-2xx
response." Without a Starlette `HTTPException` handler, FastAPI's default `{"detail": ...}`
body leaks through for this one case, breaking that guarantee."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.unit


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def test_unmatched_route_returns_error_envelope_not_default_detail_body(
    client: TestClient,
) -> None:
    r = client.get("/this/path/does/not/exist/anywhere")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert "detail" not in body
    assert body["error"]["code"] == "not_found"
    assert "request_id" in body["error"]


def test_unmatched_route_response_carries_request_id_header(client: TestClient) -> None:
    r = client.get("/another/unmatched/path")
    assert "X-Request-ID" in r.headers
