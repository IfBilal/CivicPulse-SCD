import itertools

import pytest

from app.domain.enums import Status
from app.domain.transitions import TERMINAL, TRANSITIONS, is_allowed

pytestmark = pytest.mark.unit

# The 16-cell matrix from 04-CONTRACTS.md §3, written out independently of TRANSITIONS so a
# wrong table edit goes red here instead of being tautologically "tested" against itself.
ALLOWED = {
    (Status.OPEN, Status.IN_PROGRESS),
    (Status.OPEN, Status.REJECTED),
    (Status.IN_PROGRESS, Status.RESOLVED),
    (Status.IN_PROGRESS, Status.REJECTED),
}


@pytest.mark.parametrize(("src", "dst"), list(itertools.product(Status, Status)))
def test_transition_matrix_cell(src: Status, dst: Status) -> None:
    assert is_allowed(src, dst) is ((src, dst) in ALLOWED)


def test_every_status_has_a_row() -> None:
    assert set(TRANSITIONS) == set(Status)


def test_terminal_states() -> None:
    assert frozenset({Status.RESOLVED, Status.REJECTED}) == TERMINAL


def test_self_transition_is_rejected() -> None:
    assert not any(is_allowed(s, s) for s in Status)
