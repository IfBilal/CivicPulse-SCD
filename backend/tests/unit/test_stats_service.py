"""`07-BACKEND-API.md §5`: every enum member appears as a key, even at 0 — a chart whose axis
disappears when a bucket empties is a bug."""

import pytest

from app.domain.enums import Category, Priority, Status
from app.services.stats_service import StatsService

pytestmark = pytest.mark.unit


class _FakeStatsRepo:
    def __init__(self, total: int, by_category: dict, by_priority: dict, by_status: dict) -> None:
        self._data = (total, by_category, by_priority, by_status)

    async def stats_counts(self):
        return self._data


async def test_empty_repo_zero_fills_every_category() -> None:
    repo = _FakeStatsRepo(0, {}, {}, {})
    svc = StatsService(repo)
    payload, _, _ = await svc.get()
    assert set(payload.by_category.keys()) == set(Category)
    assert all(v == 0 for v in payload.by_category.values())


async def test_empty_repo_zero_fills_every_priority_and_status() -> None:
    repo = _FakeStatsRepo(0, {}, {}, {})
    svc = StatsService(repo)
    payload, _, _ = await svc.get()
    assert set(payload.by_priority.keys()) == set(Priority)
    assert set(payload.by_status.keys()) == set(Status)


async def test_partial_data_still_reports_every_member() -> None:
    """Only WATER has rows; every other category must still appear as 0, not be missing."""
    repo = _FakeStatsRepo(5, {Category.WATER: 5}, {Priority.HIGH: 5}, {Status.OPEN: 5})
    svc = StatsService(repo)
    payload, _, _ = await svc.get()
    assert payload.by_category[Category.WATER] == 5
    assert payload.by_category[Category.ROADS] == 0
    assert payload.total == 5
