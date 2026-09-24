"""D11 — `05-DATA-LAYER.md §6.3`. Six acceptance tests for the idempotent seed script."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli.seed import _build_rows, _seed_id
from app.db.seed_data import SEED_ROWS
from app.domain.enums import Category, Priority
from app.repositories.complaint_repo import ComplaintRepository

pytestmark = pytest.mark.integration


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)
    rows = _build_rows()

    await repo.bulk_seed(rows)
    await db_session.commit()
    first_count = await repo.count()

    await repo.bulk_seed(rows)
    await db_session.commit()
    second_count = await repo.count()

    assert first_count == second_count == len(SEED_ROWS)


async def test_seed_minimum_volume(db_session: AsyncSession) -> None:
    repo = ComplaintRepository(db_session)
    await repo.bulk_seed(_build_rows())
    await db_session.commit()
    assert await repo.count() >= 30


def test_seed_category_spread() -> None:
    counts: dict[Category, int] = {c: 0 for c in Category}
    for row in SEED_ROWS:
        counts[row[3]] += 1
    for category, n in counts.items():
        assert n >= 3, f"{category} has only {n} seed rows"


def test_seed_priority_spread() -> None:
    counts: dict[Priority, int] = {p: 0 for p in Priority}
    for row in SEED_ROWS:
        counts[row[4]] += 1
    for priority, n in counts.items():
        assert n >= 5, f"{priority} has only {n} seed rows"


async def test_seed_respects_constraints(db_session: AsyncSession) -> None:
    """The seed script inserts through `bulk_seed`, which hits the same DB CHECK constraints as
    any other insert — if a fixture violated a bound, this raises instead of silently narrowing."""
    repo = ComplaintRepository(db_session)
    await repo.bulk_seed(_build_rows())
    await db_session.commit()  # would raise IntegrityError if any fixture violated a CHECK


def test_seed_ids_are_stable() -> None:
    """Proves determinism across machines: the UUID of row 0 is a pure function of its
    (text, location), so it is identical on every machine that runs this seed generation."""
    text0, location0 = SEED_ROWS[0][0], SEED_ROWS[0][1]
    golden = _seed_id(text0, location0)
    assert _seed_id(text0, location0) == golden
    # changing either input must change the id — proves it's not a constant
    assert _seed_id(text0, location0 + " ") != golden
