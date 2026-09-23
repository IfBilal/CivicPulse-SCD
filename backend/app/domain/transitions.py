"""Status state machine as a table — `04-CONTRACTS.md §3`, CLAUDE.md HARD rule 4.

Adding a status is a dict edit here, never a new `if` branch anywhere else.
"""

from app.domain.enums import Status

TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.OPEN: frozenset({Status.IN_PROGRESS, Status.REJECTED}),
    Status.IN_PROGRESS: frozenset({Status.RESOLVED, Status.REJECTED}),
    Status.RESOLVED: frozenset(),  # terminal
    Status.REJECTED: frozenset(),  # terminal
}
TERMINAL: frozenset[Status] = frozenset(s for s, targets in TRANSITIONS.items() if not targets)


def is_allowed(src: Status, dst: Status) -> bool:
    """Self-transitions are NOT allowed (open → open is 409) — see 04-CONTRACTS.md §3."""
    return dst in TRANSITIONS[src]
