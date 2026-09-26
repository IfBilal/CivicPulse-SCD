"""Phase 3: route bodies. Each handler stays short, depends only on a service, and has no
try/except (CLAUDE.md §3 — exception handlers map domain errors to status codes, not routes)."""

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.deps import get_complaint_service
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
from app.services.complaint_service import ComplaintService

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
async def create_complaint(
    body: ComplaintCreate,
    response: Response,
    svc: Annotated[ComplaintService, Depends(get_complaint_service)],
) -> ComplaintOut:
    complaint = await svc.create(
        text=body.text, location=body.location, contact=body.reporter_contact
    )
    response.headers["Location"] = f"/api/complaints/{complaint.id}"
    return ComplaintOut.model_validate(complaint)


@router.get(
    "",
    operation_id="list_complaints",
    response_model=ComplaintPage,
    responses=errors(400),
)
async def list_complaints(
    svc: Annotated[ComplaintService, Depends(get_complaint_service)],
    category: Annotated[list[Category] | None, Query()] = None,
    priority: Annotated[list[Priority] | None, Query()] = None,
    status: Annotated[list[Status] | None, Query()] = None,
    page: Annotated[int, Query(ge=PAGE_MIN)] = 1,
    page_size: Annotated[int, Query(ge=PAGE_SIZE_MIN, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
    sort: SortKey = "-created_at",
) -> ComplaintPage:
    items, total = await svc.list(
        categories=tuple(category or ()),
        priorities=tuple(priority or ()),
        statuses=tuple(status or ()),
        page=page,
        page_size=page_size,
        sort=sort,
    )
    filters_applied = {
        k: [str(v) for v in vs]
        for k, vs in (("category", category), ("priority", priority), ("status", status))
        if vs
    }
    pages = math.ceil(total / page_size) if total else 0
    return ComplaintPage(
        items=[ComplaintOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        filters_applied=filters_applied,
    )


@router.get(
    "/{id}",
    operation_id="get_complaint",
    response_model=ComplaintOut,
    responses=errors(404),
)
async def get_complaint(
    id: UUID, svc: Annotated[ComplaintService, Depends(get_complaint_service)]
) -> ComplaintOut:
    complaint = await svc.get(id)
    return ComplaintOut.model_validate(complaint)


@router.patch(
    "/{id}/status",
    operation_id="update_complaint_status",
    response_model=ComplaintOut,
    responses=errors(400, 404, 409),
)
async def update_complaint_status(
    id: UUID,
    body: StatusUpdate,
    svc: Annotated[ComplaintService, Depends(get_complaint_service)],
) -> ComplaintOut:
    complaint = await svc.change_status(id, body.status)
    return ComplaintOut.model_validate(complaint)
