"""Phase 1: signatures are the contract; bodies arrive in Phase 3 (DEV-A)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.domain.enums import Category, Priority, Status
from app.domain.limits import PAGE_MIN, PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX, PAGE_SIZE_MIN
from app.routes._responses import errors
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintOut,
    ComplaintPage,
    SortKey,
    StatusUpdate,
)

router = APIRouter(prefix="/api/complaints", tags=["complaints"])

_CREATED_HEADERS = {
    "Location": {"description": "/api/complaints/{id}", "schema": {"type": "string"}},
    "X-RateLimit-Limit": {"schema": {"type": "integer"}},
    "X-RateLimit-Remaining": {"schema": {"type": "integer"}},
    "X-RateLimit-Reset": {"schema": {"type": "integer"}},
}


@router.post(
    "",
    operation_id="create_complaint",
    status_code=201,
    response_model=ComplaintOut,
    responses={201: {"headers": _CREATED_HEADERS}, **errors(400, 429)},
)
async def create_complaint(body: ComplaintCreate) -> ComplaintOut:
    raise NotImplementedError


@router.get(
    "",
    operation_id="list_complaints",
    response_model=ComplaintPage,
    responses=errors(400),
)
async def list_complaints(
    category: Annotated[list[Category] | None, Query()] = None,
    priority: Annotated[list[Priority] | None, Query()] = None,
    status: Annotated[list[Status] | None, Query()] = None,
    page: Annotated[int, Query(ge=PAGE_MIN)] = 1,
    page_size: Annotated[int, Query(ge=PAGE_SIZE_MIN, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
    sort: SortKey = "-created_at",
) -> ComplaintPage:
    raise NotImplementedError


@router.get(
    "/{id}",
    operation_id="get_complaint",
    response_model=ComplaintOut,
    responses=errors(404),
)
async def get_complaint(id: UUID) -> ComplaintOut:
    raise NotImplementedError


@router.patch(
    "/{id}/status",
    operation_id="update_complaint_status",
    response_model=ComplaintOut,
    responses=errors(400, 404, 409),
)
async def update_complaint_status(id: UUID, body: StatusUpdate) -> ComplaintOut:
    raise NotImplementedError
