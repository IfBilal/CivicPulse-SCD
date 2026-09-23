"""Complaint wire shapes — `04-CONTRACTS.md §7`, `§6.3`."""

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import Category, Priority, Status, TriagedBy
from app.domain.limits import (
    CONTACT_MAX,
    LOCATION_MAX,
    LOCATION_MIN,
    NOTE_MAX,
    SUMMARY_MAX,
    TEXT_MAX,
    TEXT_MIN,
)

_EMAIL_ISH = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_E164_ISH = re.compile(r"^\+?[0-9][0-9 \-]{6,18}[0-9]$")

SortKey = Literal["created_at", "-created_at", "priority", "-priority"]


class ComplaintCreate(BaseModel):
    # extra="forbid": an unknown field (e.g. a "catagory" typo) is a 400, not a silent drop.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=TEXT_MIN, max_length=TEXT_MAX)
    location: str = Field(min_length=LOCATION_MIN, max_length=LOCATION_MAX)
    reporter_contact: str | None = Field(default=None, max_length=CONTACT_MAX)

    @field_validator("reporter_contact")
    @classmethod
    def _contact_is_email_or_phone(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None  # an empty form field means "no contact", not a malformed one
        if _EMAIL_ISH.match(v) or _E164_ISH.match(v):
            return v
        raise ValueError("must be an email address or a phone number")


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    text: str
    location: str
    reporter_contact: str | None
    category: Category
    priority: Priority
    status: Status
    ai_summary: str | None = Field(max_length=SUMMARY_MAX)
    triaged_by: TriagedBy
    triage_latency_ms: int
    triage_confidence: float | None  # contradiction A5 superset
    created_at: datetime
    updated_at: datetime


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    note: str | None = Field(default=None, max_length=NOTE_MAX)  # not persisted in v1


class ComplaintPage(BaseModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int
    pages: int
    filters_applied: dict[str, list[str]]
