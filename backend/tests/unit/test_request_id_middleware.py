"""`06-BACKEND-CORE.md §3.1`: hostile inbound X-Request-ID input must never be echoed —
that's a log-injection vector (`\\n` in a header forges log records)."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    # `/health` reads `app.state.started_at`, set by the lifespan — TestClient only runs
    # startup/shutdown when used as a context manager.
    with TestClient(create_app()) as c:
        yield c


def test_hostile_request_id_header_is_discarded(client: TestClient) -> None:
    r = client.get("/health", headers={"X-Request-ID": "x\nlevel=ERROR"})
    got = r.headers["X-Request-ID"]
    assert "\n" not in got
    assert "level=ERROR" not in got
    assert uuid.UUID(got).version == 4


def test_valid_v4_request_id_is_echoed_verbatim(client: TestClient) -> None:
    rid = str(uuid.uuid4())
    r = client.get("/health", headers={"X-Request-ID": rid})
    assert r.headers["X-Request-ID"] == rid


def test_non_v4_uuid_is_replaced_not_echoed(client: TestClient) -> None:
    v1 = str(uuid.uuid1())
    r = client.get("/health", headers={"X-Request-ID": v1})
    got = r.headers["X-Request-ID"]
    assert got != v1
    assert uuid.UUID(got).version == 4


def test_empty_request_id_generates_fresh_one(client: TestClient) -> None:
    r = client.get("/health", headers={"X-Request-ID": ""})
    assert uuid.UUID(r.headers["X-Request-ID"]).version == 4
