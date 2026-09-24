"""All SQL for `complaints` lives here — CLAUDE.md HARD rule 3, `05-DATA-LAYER.md §5`.

This layer knows nothing about HTTP outcomes or routes. `transition()` returning `None` on a
mismatch is a fact about the database, not a 404 or a 409 — the service layer (Phase 3) decides
which. That boundary is enforced mechanically by the `lint-layers` Makefile target.
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Complaint
from app.domain.enums import Category, Priority, Status, TriagedBy

_ORDERINGS: dict[str, ColumnElement[Any]] = {
    "created_at": Complaint.created_at.asc(),
    "-created_at": Complaint.created_at.desc(),
    "priority": Complaint.priority.asc(),
    "-priority": Complaint.priority.desc(),
}


class ComplaintRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(
        self,
        *,
        text: str,
        location: str,
        reporter_contact: str | None,
        category: Category,
        priority: Priority,
        ai_summary: str | None,
        triaged_by: TriagedBy,
        triage_latency_ms: int,
        triage_confidence: float | None,
    ) -> Complaint:
        row = Complaint(
            text=text,
            location=location,
            reporter_contact=reporter_contact,
            category=category,
            priority=priority,
            ai_summary=ai_summary,
            triaged_by=triaged_by,
            triage_latency_ms=triage_latency_ms,
            triage_confidence=triage_confidence,
        )
        self._s.add(row)
        await self._s.flush()
        return row

    async def get(self, cid: UUID) -> Complaint | None:
        return await self._s.get(Complaint, cid)

    async def list_page(
        self,
        *,
        categories: Sequence[Category] = (),
        priorities: Sequence[Priority] = (),
        statuses: Sequence[Status] = (),
        page: int,
        page_size: int,
        sort: str = "-created_at",
    ) -> tuple[Sequence[Complaint], int]:
        """One statement: a window `COUNT(*) OVER ()` avoids a second round trip for `total`."""
        total_col = func.count().over().label("total_count")
        stmt = select(Complaint, total_col)
        if statuses:
            stmt = stmt.where(Complaint.status.in_(statuses))
        if priorities:
            stmt = stmt.where(Complaint.priority.in_(priorities))
        if categories:
            stmt = stmt.where(Complaint.category.in_(categories))
        stmt = stmt.order_by(_ORDERINGS[sort]).limit(page_size).offset((page - 1) * page_size)
        rows = (await self._s.execute(stmt)).all()
        total = rows[0].total_count if rows else 0
        return [r[0] for r in rows], total

    async def transition(self, cid: UUID, expected: Status, new: Status) -> Complaint | None:
        """Conditional UPDATE — atomic. `None` means the row didn't match `expected` (either it
        doesn't exist, or someone else already moved it). The caller decides 404 vs 409."""
        stmt = (
            update(Complaint)
            .where(Complaint.id == cid, Complaint.status == expected)
            .values(status=new)
            .returning(Complaint)
        )
        result = await self._s.execute(stmt)
        row = result.one_or_none()
        return row[0] if row else None

    async def bulk_seed(self, rows: list[dict[str, Any]]) -> None:
        """Idempotent insert — `05-DATA-LAYER.md §6.1`. Callers pass a stable `id` (UUIDv5), and
        the existing PK unique index makes `ON CONFLICT (id) DO NOTHING` free."""
        if not rows:
            return
        stmt = pg_insert(Complaint).values(rows).on_conflict_do_nothing(index_elements=["id"])
        await self._s.execute(stmt)

    async def count(self) -> int:
        return (await self._s.execute(select(func.count()).select_from(Complaint))).scalar_one()
