"""The 400/404 envelopes are produced before any handler body runs, so they are testable in
Phase 1 against the stub routes (04-CONTRACTS.md §5, §6.2, §6.3)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.contract

VALID = {"text": "burst water main on Street 12", "location": "G-9/1, Islamabad"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def _fields(resp_json: dict) -> dict[str, dict]:  # type: ignore[type-arg]
    return {f["field"]: f for f in resp_json["error"]["fields"]}


def test_short_text_is_400_with_field_and_constraint(client: TestClient) -> None:
    r = client.post("/api/complaints", json={**VALID, "text": "short"})
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    f = _fields(body)["text"]
    assert f["code"] == "too_short"
    assert f["constraint"] == {"min": 10}


def test_blank_text_is_rejected_after_strip(client: TestClient) -> None:
    r = client.post("/api/complaints", json={**VALID, "text": " " * 50})
    assert r.status_code == 400
    assert _fields(r.json())["text"]["code"] == "too_short"


def test_missing_location_is_field_level(client: TestClient) -> None:
    r = client.post("/api/complaints", json={"text": VALID["text"]})
    assert r.status_code == 400
    assert _fields(r.json())["location"]["code"] == "missing"


def test_unknown_field_is_400_not_silently_dropped(client: TestClient) -> None:
    r = client.post("/api/complaints", json={**VALID, "catagory": "water"})
    assert r.status_code == 400
    assert _fields(r.json())["catagory"]["code"] == "unexpected_field"


def test_bad_contact_is_400(client: TestClient) -> None:
    r = client.post("/api/complaints", json={**VALID, "reporter_contact": "call me maybe"})
    assert r.status_code == 400
    assert "reporter_contact" in _fields(r.json())


def test_malformed_json_is_400(client: TestClient) -> None:
    r = client.post(
        "/api/complaints", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert r.status_code == 400
    assert r.json()["error"]["fields"][0]["code"] == "invalid_json"


@pytest.mark.parametrize("size", [0, 101])
def test_page_size_out_of_bounds_is_400(client: TestClient, size: int) -> None:
    r = client.get("/api/complaints", params={"page_size": size})
    assert r.status_code == 400
    assert _fields(r.json())["page_size"]["code"] == "out_of_range"


def test_unknown_status_filter_is_400(client: TestClient) -> None:
    r = client.get("/api/complaints", params={"status": "closed"})
    assert r.status_code == 400
    assert _fields(r.json())["status.0"]["code"] == "invalid_choice"


def test_non_uuid_id_is_404_not_400(client: TestClient) -> None:
    r = client.get("/api/complaints/not-a-uuid")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_patch_bad_status_value_is_400(client: TestClient) -> None:
    r = client.patch(f"/api/complaints/{uuid.uuid4()}/status", json={"status": "closed"})
    assert r.status_code == 400


def test_422_never_emitted(client: TestClient) -> None:
    r = client.post("/api/complaints", json={})
    assert r.status_code == 400


def test_request_id_echoed_when_valid(client: TestClient) -> None:
    rid = str(uuid.uuid4())
    r = client.post("/api/complaints", json={}, headers={"X-Request-ID": rid})
    assert r.headers["X-Request-ID"] == rid
    assert r.json()["error"]["request_id"] == rid


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    r = client.post("/api/complaints", json={}, headers={"X-Request-ID": "not-a-uuid"})
    assert uuid.UUID(r.headers["X-Request-ID"]).version == 4


def test_stub_routes_are_501_until_phase_3(client: TestClient) -> None:
    r = client.post("/api/complaints", json=VALID)
    assert r.status_code == 501
    assert r.json()["error"]["code"] == "not_implemented"


def test_non_v4_request_id_is_replaced_not_rewritten(client: TestClient) -> None:
    sent = str(uuid.uuid1())
    r = client.post("/api/complaints", json={}, headers={"X-Request-ID": sent})
    got = r.headers["X-Request-ID"]
    assert uuid.UUID(got).version == 4
    # a version-bit rewrite would keep the first 12 hex digits of the client's id
    assert sent.replace("-", "")[:12] not in got.replace("-", "")


def test_empty_contact_normalises_to_null() -> None:
    from app.schemas.complaint import ComplaintCreate

    assert ComplaintCreate(**VALID, reporter_contact="  ").reporter_contact is None


@pytest.mark.parametrize("contact", ["+923001234567", "ali@example.pk", "0300 1234567"])
def test_valid_contacts_accepted(client: TestClient, contact: str) -> None:
    r = client.post("/api/complaints", json={**VALID, "reporter_contact": contact})
    assert r.status_code == 501  # passed validation, reached the Phase 1 stub
