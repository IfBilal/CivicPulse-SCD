"""One error envelope for every non-2xx response — `04-CONTRACTS.md §5`."""

from typing import Any

from pydantic import BaseModel


class FieldError(BaseModel):
    field: str
    code: str
    message: str
    constraint: dict[str, Any] | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    fields: list[FieldError] | None = None
    details: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
