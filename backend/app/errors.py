"""Registered exception handlers — the ONLY place a status code is chosen for an error.
Routes never try/except to pick a status (CLAUDE.md §3)."""

import logging
import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import InvalidTransition, NotFound, NotReady, RateLimited
from app.domain.transitions import TRANSITIONS
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


async def _on_not_found(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, NotFound)
    return error_response(request, 404, "not_found", "Resource not found.")


async def _on_invalid_transition(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, InvalidTransition)
    details = {
        "from": exc.src.value,
        "to": exc.dst.value,
        "allowed_from_current": sorted(s.value for s in TRANSITIONS[exc.src]),
        "terminal": not TRANSITIONS[exc.src],
    }
    return error_response(
        request,
        409,
        "invalid_transition",
        f"Cannot transition from '{exc.src.value}' to '{exc.dst.value}'.",
        details=details,
    )


async def _on_rate_limited(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RateLimited)
    return error_response(
        request,
        429,
        "rate_limited",
        "Too many requests.",
        headers={"Retry-After": str(exc.retry_after_s)},
    )


async def _on_not_ready(request: Request, exc: Exception) -> JSONResponse:
    # 04-CONTRACTS.md §6.8 verbatim shape: error.details.{checks,failed}, message names the
    # failed dependency (the first one, if several — `checks` still carries the full map).
    assert isinstance(exc, NotReady)
    return error_response(
        request,
        503,
        "not_ready",
        f"Dependency check failed: {', '.join(exc.failed)}",
        details={"checks": exc.checks, "failed": exc.failed},
    )


async def _on_starlette_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """A genuinely unmatched route (no path in any router) raises Starlette's own
    `HTTPException`, not one of ours — without this handler it falls through to FastAPI's
    default `{"detail": ...}` body, breaking "one envelope for every non-2xx response." Only
    reached for paths this app never declared; every endpoint this app DOES declare raises a
    domain exception or a validation error instead, which the handlers above already cover."""
    assert isinstance(exc, StarletteHTTPException)
    code = "not_found" if exc.status_code == 404 else "http_error"
    return error_response(request, exc.status_code, code, str(exc.detail))


async def _on_unhandled(request: Request, exc: Exception) -> JSONResponse:
    # Opaque body — no exception message, class name, or path (06-BACKEND-CORE.md §7). The
    # request_id is the join key: header, body, and this log line all carry it.
    logging.getLogger("app.errors").error(
        "unhandled_exception", exc_info=exc, extra={"extra_fields": {"path": request.url.path}}
    )
    return error_response(request, 500, "internal_error", "An internal error occurred.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _on_validation_error)
    app.add_exception_handler(InvalidTransition, _on_invalid_transition)
    app.add_exception_handler(NotFound, _on_not_found)
    app.add_exception_handler(RateLimited, _on_rate_limited)
    app.add_exception_handler(NotReady, _on_not_ready)
    app.add_exception_handler(StarletteHTTPException, _on_starlette_http_exception)
    app.add_exception_handler(Exception, _on_unhandled)
