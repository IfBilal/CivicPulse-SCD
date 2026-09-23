"""Registered exception handlers — the ONLY place a status code is chosen for an error.
Routes never try/except to pick a status (CLAUDE.md §3)."""

import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.errors import ErrorBody, ErrorEnvelope, FieldError

# Pydantic error type → our stable `fields[].code`. Anything unlisted becomes "invalid".
_CODE_BY_TYPE = {
    "missing": "missing",
    "string_too_short": "too_short",
    "string_too_long": "too_long",
    "extra_forbidden": "unexpected_field",
    "enum": "invalid_choice",
    "literal_error": "invalid_choice",
    "greater_than_equal": "out_of_range",
    "less_than_equal": "out_of_range",
    "int_parsing": "not_an_integer",
    "json_invalid": "invalid_json",
}
_CONSTRAINT_KEYS = {"min_length": "min", "max_length": "max", "ge": "min", "le": "max"}
_LOC_PREFIXES = {"body", "query", "path", "header"}


def request_id_of(request: Request) -> str:
    """Set by the request-id middleware (Phase 3); falls back to the header or a new UUIDv4."""
    rid = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    # NB: uuid.UUID(rid, version=4) would *overwrite* the version bits of a v1/v7 id and echo
    # back a forged value — parse, then check the version explicitly.
    try:
        parsed = uuid.UUID(rid) if rid else None
    except ValueError:
        parsed = None
    return str(parsed) if parsed and parsed.version == 4 else str(uuid.uuid4())


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    fields: list[FieldError] | None = None,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    rid = request_id_of(request)
    body = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, request_id=rid, fields=fields, details=details)
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json", exclude_none=True),
        headers={"X-Request-ID": rid, **(headers or {})},
    )


def _field_path(loc: Sequence[int | str]) -> str:
    parts = [str(p) for p in loc]
    if len(parts) > 1 and parts[0] in _LOC_PREFIXES:
        parts = parts[1:]
    return ".".join(parts)


def _to_field_error(err: dict[str, Any]) -> FieldError:
    ctx = err.get("ctx") or {}
    constraint = {out: ctx[k] for k, out in _CONSTRAINT_KEYS.items() if k in ctx} or None
    return FieldError(
        field=_field_path(err["loc"]),
        code=_CODE_BY_TYPE.get(err["type"], "invalid"),
        message=err["msg"],
        constraint=constraint,
    )


async def _on_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = exc.errors()
    # A malformed path id means the resource doesn't exist — 404, don't leak the id format
    # (04-CONTRACTS.md §6.2).
    if any(e["loc"] and e["loc"][0] == "path" for e in errors):
        return error_response(request, 404, "not_found", "Resource not found.")
    # FastAPI's default is 422; 00-SPEC §2.2 says 400 (04-CONTRACTS.md §5.4).
    return error_response(
        request,
        400,
        "validation_error",
        "Request body failed validation.",
        fields=[_to_field_error(e) for e in errors],
    )


async def _on_not_implemented(request: Request, exc: Exception) -> JSONResponse:
    # Phase 1 route stubs only. Remove this handler once Phase 3 fills every handler.
    return error_response(request, 501, "not_implemented", "Endpoint not implemented yet.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _on_validation_error)
    app.add_exception_handler(NotImplementedError, _on_not_implemented)
