"""Orchestration for the complaints resource — `07-BACKEND-API.md §2.2`, `§4`.

Layer rule (CLAUDE.md §3): this module imports `repositories`, `providers`, `domain` only. It
never chooses an HTTP status — only the registered exception handlers in `app/errors.py` do
that (`06-BACKEND-CORE.md §7`).
"""

from uuid import UUID, uuid4

from app.db.models import Complaint
from app.domain.enums import Category, Priority, Status, TriagedBy
from app.domain.errors import InvalidTransition, NotFound
from app.domain.transitions import is_allowed
from app.repositories.complaint_repo import ComplaintRepository
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService


class ComplaintService:
    def __init__(
        self,
        repo: ComplaintRepository,
        triage: TriageService,
        stats: StatsService | None = None,
    ) -> None:
        self._repo = repo
        self._triage = triage
        self._stats = stats

    async def create(self, *, text: str, location: str, contact: str | None) -> Complaint:
        """Triage BEFORE persist (07-BACKEND-API.md §2.2) — the response returns a fully
        triaged row. The triage call happens before `repo.create()` is ever invoked, so it
        never holds an open DB transaction (a slow HTTP call must not pin a pool connection)."""
        # The DB row (and its real id, assigned by Postgres's gen_random_uuid() default) does
        # not exist until AFTER triage returns, but the fallback WARNING and ring entry need
        # SOME complaint_id to correlate against at the moment triage runs. This generates a
        # throwaway id for that purpose only — it is NOT the persisted row's id, and nothing
        # currently reconciles the two. That means an operator correlating a `triage.fallback`
        # log line or a `/api/meta/providers` ring entry back to the actual complaint by id
        # cannot do so from this id alone. Accepted as a Phase 3 gap, not fixed here: closing
        # it requires either (a) `repo.create()` accepting a caller-supplied id (removing the
        # DB's gen_random_uuid() default), or (b) persist-then-triage (changes the §2.2
        # ordering contract). Flagged for Phase 4 rather than silently left implied-correct.
        provisional_id = uuid4()
        outcome = await self._triage.triage_with_fallback(
            complaint_id=provisional_id, text=text, location=location
        )
        return await self._repo.create(
            text=text,
            location=location,
            reporter_contact=contact,
            category=outcome.result.category,
            priority=outcome.result.priority,
            ai_summary=outcome.result.summary,
            # TriageOutcome.triaged_by is `str` (it's built from a provider's plain-string
            # `.name`, which the TriageProvider Protocol deliberately keeps un-typed to a
            # closed enum — see 08-AI-TRIAGE.md §1's Protocol-over-inheritance point). Every
            # real value is already a valid TriagedBy member; this wrap makes that explicit at
            # the one boundary where it needs to be an enum (the DB column), rather than
            # asking the whole triage layer to import app.domain.enums.
            triaged_by=TriagedBy(outcome.triaged_by),
            triage_latency_ms=outcome.latency_ms,
            triage_confidence=outcome.result.confidence,
        )

    async def get(self, cid: UUID) -> Complaint:
        row = await self._repo.get(cid)
        if row is None:
            raise NotFound(cid)
        return row

    async def list(
        self,
        *,
        categories: tuple[Category, ...] = (),
        priorities: tuple[Priority, ...] = (),
        statuses: tuple[Status, ...] = (),
        page: int,
        page_size: int,
        sort: str,
    ) -> tuple[list[Complaint], int]:
        rows, total = await self._repo.list_page(
            categories=categories,
            priorities=priorities,
            statuses=statuses,
            page=page,
            page_size=page_size,
            sort=sort,
        )
        return list(rows), total

    async def change_status(self, cid: UUID, new: Status) -> Complaint:
        """Table lookup, conditional UPDATE, race-safe 409 — `07-BACKEND-API.md §4` verbatim."""
        current = await self._repo.get(cid)
        if current is None:
            raise NotFound(cid)
        if not is_allowed(current.status, new):
            raise InvalidTransition(current.status, new)
        updated = await self._repo.transition(cid, expected=current.status, new=new)
        if updated is None:  # lost the race
            fresh = await self._repo.get(cid)
            assert fresh is not None  # it existed a moment ago; can't have been hard-deleted
            raise InvalidTransition(fresh.status, new)
        if self._stats is not None:
            await self._stats.invalidate()
        return updated
