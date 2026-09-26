"""Shared, suite-wide fixtures. Kept minimal and infrastructural only — no app fixtures here;
those stay in each tier's own conftest.py (e.g. `tests/integration/conftest.py`)."""

import logging

import pytest


@pytest.fixture(autouse=True)
def _no_disabled_loggers() -> None:
    """Guards against `Logger.disabled` leaking across tests regardless of collection order.

    Found via a real full-suite run (not assumed): by the time some tests execute, the
    `app.triage` logger has `.disabled == True`, which silently drops every record before it
    ever reaches a handler — `app/logging_config.py::configure_logging()` now defensively
    re-enables every known logger each time it runs (see its own comment for what's been ruled
    out as the trigger), but that only helps *after* the app factory has run at least once in
    the process. A handful of unit tests exercise `TriageService` directly, without ever
    constructing the app, and can run before any `configure_logging()` call in the suite's
    actual collection order — this fixture makes the guarantee unconditional instead of order-
    dependent, which is the more honest fix for a test-isolation bug (CLAUDE.md HARD rule 15:
    a flaky, order-dependent test is a design bug wearing a disguise)."""
    for logger_name in list(logging.root.manager.loggerDict):
        logging.getLogger(logger_name).disabled = False
    yield
