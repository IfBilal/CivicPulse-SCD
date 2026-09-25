"""The 400/404 envelopes are produced before any handler body runs, so they are testable here
without a database (04-CONTRACTS.md §5, §6.2, §6.3). The handful of tests that DO reach a route
body with a fully valid payload override `get_complaint_service` with an in-memory fake so this
file stays DB-free — a real persistence round trip belongs in `tests/integration/`."""

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.deps import get_complaint_service
from app.domain.enums import Category, Priority, Status, TriagedBy
from app.main import create_app

pytestmark = pytest.mark.contract

VALID = {"text": "burst water main on Street 12", "location": "G-9/1, Islamabad"}


class _FakeComplaint:
    """Stands in for `app.db.models.Complaint` — `ComplaintOut.model_validate` only needs
    attribute access (`from_attributes=True`), not a real ORM row."""

    def __init__(self, text: str, location: str, contact: str | None) -> None:
        self.id: UUID = uuid.uuid4()
        self.text = text
        self.location = location
        self.reporter_contact = contact
        self.category = Category.WATER
        self.priority = Priority.NORMAL
        self.status = Status.OPEN
        self.ai_summary = "stub summary"
        self.triaged_by = TriagedBy.SIMULATED
        self.triage_latency_ms = 1
        self.triage_confidence = 0.9
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


class _FakeComplaintService:
    async def create(self, *, text: str, location: str, contact: str | None) -> Any:
        return _FakeComplaint(text, location, contact)


@pytest.fixture(scope="module")
def client() -> TestClient:
    # This file exercises the error envelope, not rate limiting — dozens of POSTs across its
    # tests would otherwise trip the innermost middleware's fixed-window counter and turn
    # unrelated tests flaky. Rate limiting itself is covered by its own middleware-scoped test.
    # `Settings` is frozen, so swap in a copy with rate limiting off rather than mutate it.
    original = main_module.settings
    main_module.settings = original.model_copy(update={"ratelimit_enabled": False})
    try:
        app = create_app()
    finally:
        main_module.settings = original
    app.dependency_overrides[get_complaint_service] = lambda: _FakeComplaintService()
    return TestClient(app)


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


def test_valid_body_reaches_the_route_and_creates(client: TestClient) -> None:
    # Phase 1 asserted 501 here (stub routes). Phase 3 fills the handler bodies, so a valid
    # body now reaches `ComplaintService.create` (faked above) and returns 201 with a Location
    # header — this is the same "passed validation" assertion updated for the real behavior.
    r = client.post("/api/complaints", json=VALID)
    assert r.status_code == 201
    assert r.headers["Location"].startswith("/api/complaints/")


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
    assert r.status_code == 201  # passed validation, reached the route body
