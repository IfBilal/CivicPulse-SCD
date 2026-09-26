"""`/ready` — `06-BACKEND-CORE.md §5`, `04-CONTRACTS.md §6.8`: concurrent checks, 503 in the
one `ErrorEnvelope` shape naming the failed dependency, short-circuits on `state.ready == False`.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.unit


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def test_ready_503_when_postgres_unreachable(client: TestClient) -> None:
    # No real Postgres in this sandbox (unit tier, no testcontainers) — `check_connection()`
    # hits the default `database_url`, which has nothing listening, so this proves the real
    # failure path: /ready must degrade to 503 and NAME "postgres" as the failed dependency.
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["error"]["details"]["checks"]["postgres"] != "ok"


def test_ready_503_is_error_envelope_shaped(client: TestClient) -> None:
    """04-CONTRACTS.md §6.8 verbatim: {"error":{"code":"not_ready","message":...,
    "request_id":...,"details":{"checks":{...},"failed":[...]}}} — NOT the 200 ReadyOut shape.
    A generated TS client types every declared 503 as ErrorEnvelope; shipping anything else
    means `error.request_id` reads as undefined at runtime for a real client."""
    r = client.get("/ready")
    body = r.json()
    assert body["error"]["code"] == "not_ready"
    assert "request_id" in body["error"]
    assert "postgres" in body["error"]["details"]["failed"]


def test_ready_body_names_which_dependency_failed(client: TestClient) -> None:
    r = client.get("/ready")
    body = r.json()["error"]["details"]
    assert "postgres" in body["checks"]
    assert "redis" in body["checks"]


def test_ready_short_circuits_when_not_ready(client: TestClient) -> None:
    client.app.state.ready = False
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["error"]["details"]["checks"] == {"lifecycle": "shutting_down"}
    client.app.state.ready = True


def test_health_never_returns_503_regardless_of_db_state(client: TestClient) -> None:
    """The wiring-backwards failure this proves the ABSENCE of: /health must stay 200 even
    while /ready is 503, or a DB stall becomes a cluster-wide restart loop (06-BACKEND-CORE.md
    §5)."""
    ready_resp = client.get("/ready")
    assert ready_resp.status_code == 503  # dependency genuinely down in this sandbox

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
