"""Encodes 04-CONTRACTS.md §6.10 / §9 against the generated schema — no server, no DB."""

from typing import Any

import pytest

from app.main import create_app

pytestmark = pytest.mark.contract

GOLDEN_OPERATIONS = {
    ("post", "/api/complaints"): "create_complaint",
    ("get", "/api/complaints"): "list_complaints",
    ("get", "/api/complaints/{id}"): "get_complaint",
    ("patch", "/api/complaints/{id}/status"): "update_complaint_status",
    ("get", "/api/stats"): "get_stats",
    ("get", "/api/meta/providers"): "get_providers",
    ("get", "/health"): "health",
    ("get", "/ready"): "ready",
}

DECLARED_CODES = {
    "create_complaint": {"201", "400", "429"},
    "list_complaints": {"200", "400"},
    "get_complaint": {"200", "404"},
    "update_complaint_status": {"200", "400", "404", "409"},
    "get_stats": {"200"},
    "get_providers": {"200"},
    "health": {"200"},
    "ready": {"200", "503"},
}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return create_app().openapi()


def _ops(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {op["operationId"]: op for item in schema["paths"].values() for op in item.values()}


def test_operation_ids_match_golden_list(schema: dict[str, Any]) -> None:
    actual = {
        (method, path): op["operationId"]
        for path, item in schema["paths"].items()
        for method, op in item.items()
    }
    assert actual == GOLDEN_OPERATIONS


def test_servers_relative(schema: dict[str, Any]) -> None:
    assert schema["servers"] == [{"url": "/"}]


def test_422_never_in_schema(schema: dict[str, Any]) -> None:
    assert '"422"' not in str(schema).replace("'", '"')
    assert "HTTPValidationError" not in schema["components"]["schemas"]


@pytest.mark.parametrize(("op_id", "codes"), DECLARED_CODES.items())
def test_all_documented_status_codes_declared(
    schema: dict[str, Any], op_id: str, codes: set[str]
) -> None:
    assert set(_ops(schema)[op_id]["responses"]) == codes


def test_error_responses_use_envelope(schema: dict[str, Any]) -> None:
    for op in _ops(schema).values():
        for code, resp in op["responses"].items():
            if code.startswith(("4", "5")):
                ref = resp["content"]["application/json"]["schema"]["$ref"]
                assert ref.endswith("/ErrorEnvelope")


def test_every_response_declares_x_request_id(schema: dict[str, Any]) -> None:
    for op in _ops(schema).values():
        for resp in op["responses"].values():
            assert "X-Request-ID" in resp["headers"]


def test_header_contract(schema: dict[str, Any]) -> None:
    ops = _ops(schema)
    assert ops["get_stats"]["responses"]["200"]["headers"]["X-Cache"]["schema"]["enum"] == [
        "HIT",
        "MISS",
    ]
    assert "Retry-After" in ops["create_complaint"]["responses"]["429"]["headers"]
    assert "Location" in ops["create_complaint"]["responses"]["201"]["headers"]
    for op_id, op in ops.items():
        if op_id != "get_stats":
            assert all("X-Cache" not in r["headers"] for r in op["responses"].values())


def test_enums_in_schema_match_domain(schema: dict[str, Any]) -> None:
    comps = schema["components"]["schemas"]
    assert comps["Status"]["enum"] == ["open", "in_progress", "resolved", "rejected"]
    assert "simulated" in comps["TriagedBy"]["enum"]
