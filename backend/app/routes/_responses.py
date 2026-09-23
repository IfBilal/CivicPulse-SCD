"""OpenAPI `responses=` fragments, so every documented status code carries its model and
the generated client types include the error envelope (04-CONTRACTS.md §6.10)."""

from typing import Any

from app.schemas.errors import ErrorEnvelope

_DESCRIPTIONS = {
    400: "Validation failed — field-level errors in `error.fields`",
    404: "Not found",
    409: "Invalid status transition — `error.details` names `from` and `to`",
    429: "Rate limited",
    503: "A dependency is unreachable — `error.details.failed` names it",
}

RETRY_AFTER = {
    "Retry-After": {
        "description": "Integer seconds until the rate-limit window resets",
        "schema": {"type": "integer"},
    }
}


def errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    out: dict[int | str, dict[str, Any]] = {
        c: {"model": ErrorEnvelope, "description": _DESCRIPTIONS[c]} for c in codes
    }
    if 429 in out:
        out[429]["headers"] = RETRY_AFTER
    return out
