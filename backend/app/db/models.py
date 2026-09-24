"""ORM model — `05-DATA-LAYER.md §2`. Bounds shared with Pydantic via `domain/limits.py` so the
app-layer validation and the DB CHECK constraints cannot drift apart."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, Integer, Numeric, String, Text
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import Category, Priority, Status, TriagedBy
from app.domain.limits import (
    CONTACT_MAX,
    LOCATION_MAX,
    LOCATION_MIN,
    SUMMARY_MAX,
    TEXT_MAX,
    TEXT_MIN,
)


# create_type=False: the migration owns type creation. The ORM must never issue DDL on first
# insert — that is startup DDL in spirit, which `00-SPEC.md §2.3` forbids.
#
# values_callable is required: without it, PGEnum serialises a Python Enum member by its
# `.name` ("STREETLIGHTS"), not its `.value` ("streetlights") — but migration 0001's
# `CREATE TYPE` statements only define the lowercase wire-format values. Every INSERT/UPDATE
# would raise `InvalidTextRepresentation` without this. Caught by CI's data-layer job
# (D6/D9 integration tests), not by any static check — nothing type-level flags it.
def _enum_values(enum_cls: type[Category | Priority | Status | TriagedBy]) -> list[str]:
    return [member.value for member in enum_cls]


category_enum = PGEnum(
    Category,
    name="category_enum",
    create_type=False,
    native_enum=True,
    values_callable=_enum_values,
)
priority_enum = PGEnum(
    Priority,
    name="priority_enum",
    create_type=False,
    native_enum=True,
    values_callable=_enum_values,
)
status_enum = PGEnum(
    Status,
    name="status_enum",
    create_type=False,
    native_enum=True,
    values_callable=_enum_values,
)
triaged_by_enum = PGEnum(
    TriagedBy,
    name="triaged_by_enum",
    create_type=False,
    native_enum=True,
    values_callable=_enum_values,
)


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=sql_text("gen_random_uuid()")
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(LOCATION_MAX), nullable=False)
    reporter_contact: Mapped[str | None] = mapped_column(String(CONTACT_MAX))
    category: Mapped[Category] = mapped_column(category_enum, nullable=False)
    priority: Mapped[Priority] = mapped_column(priority_enum, nullable=False)
    status: Mapped[Status] = mapped_column(
        status_enum, nullable=False, server_default=sql_text("'open'::status_enum")
    )
    ai_summary: Mapped[str | None] = mapped_column(String(SUMMARY_MAX))
    triaged_by: Mapped[TriagedBy] = mapped_column(triaged_by_enum, nullable=False)
    triage_latency_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sql_text("0")
    )
    triage_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))  # contradiction A5
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=sql_text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=sql_text("now()")
    )

    __table_args__ = (
        CheckConstraint(f"char_length(text) BETWEEN {TEXT_MIN} AND {TEXT_MAX}", name="text_len"),
        CheckConstraint(
            f"char_length(location) BETWEEN {LOCATION_MIN} AND {LOCATION_MAX}", name="location_len"
        ),
        CheckConstraint(
            "reporter_contact IS NULL OR char_length(reporter_contact) "
            f"BETWEEN 3 AND {CONTACT_MAX}",
            name="contact_len",
        ),
        CheckConstraint(
            f"ai_summary IS NULL OR char_length(ai_summary) <= {SUMMARY_MAX}", name="summary_len"
        ),
        CheckConstraint("triage_latency_ms >= 0", name="latency_nonneg"),
        CheckConstraint(
            "triage_confidence IS NULL OR (triage_confidence >= 0 AND triage_confidence <= 1)",
            name="confidence_range",
        ),
        Index("ix_complaints_status_priority", "status", "priority"),
        Index("ix_complaints_created_at", sql_text("created_at DESC")),
    )
