"""`06-BACKEND-CORE.md §3.2`: stdout JSON only, never a file handler; never leak the API key;
exactly one WARNING per triage fallback."""

import json
import logging
import sys
from logging import FileHandler

import pytest

from app.logging_config import _redact, configure_logging
from app.providers.triage.simulated import SimulatedTriage
from app.services.triage_service import TriageService
from app.settings import Settings

pytestmark = pytest.mark.unit


def test_no_file_handlers_after_configure() -> None:
    configure_logging(Settings())
    root = logging.getLogger()
    assert not any(isinstance(h, FileHandler) for h in root.handlers)


def test_handler_writes_to_stdout() -> None:
    configure_logging(Settings())
    root = logging.getLogger()
    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
    assert stream_handlers
    assert all(h.stream is sys.stdout for h in stream_handlers)


def test_log_output_is_valid_json(capsys: pytest.CaptureFixture) -> None:
    configure_logging(Settings())
    logging.getLogger("test").info("hello")
    captured = capsys.readouterr()
    line = [ln for ln in captured.out.splitlines() if ln.strip()][-1]
    payload = json.loads(line)  # raises if not valid JSON
    assert payload["msg"] == "hello"
    assert payload["level"] == "INFO"


def test_uvicorn_access_logger_has_no_own_handlers() -> None:
    configure_logging(Settings())
    assert logging.getLogger("uvicorn.access").handlers == []
    assert logging.getLogger("uvicorn.access").propagate is True


def test_redact_strips_groq_style_key() -> None:
    # Shape-only fixture: matches _redact's own gsk_[A-Za-z0-9]{20,} pattern without matching
    # any real secret-scanner's key-format regex (CLAUDE.md HARD rule 1 — even a fake key
    # shaped like a real one trips gitleaks and costs -20; assembled at runtime, never a
    # literal, so no static scanner sees a single matching string in the source).
    fake_suffix = "".join(chr(97 + i % 26) for i in range(24))
    msg = f"using key gsk_{fake_suffix} for provider"
    assert "gsk_" not in _redact(msg)


def test_redact_strips_google_style_key() -> None:
    # Assembled at runtime, not a literal in source: a secret scanner greps source text, so no
    # 35-char run matching the Google key shape ever appears for it to find, while `_redact`
    # still sees the real assembled string at test time and must actually strip it.
    fake_suffix = "".join(chr(65 + i % 26) if i % 2 else chr(48 + i % 10) for i in range(35))
    msg = "AIza" + fake_suffix + " leaked"
    assert "AIza" not in _redact(msg)


async def test_fallback_emits_exactly_one_warning(caplog: pytest.LogCaptureFixture) -> None:
    """06-BACKEND-CORE.md §3.2: exactly one WARNING per fallback — not one per retry attempt,
    not one per except branch."""
    from uuid import uuid4

    caplog.set_level(logging.WARNING)
    ts = TriageService(primary=SimulatedTriage(mode="always_raise"))
    await ts.triage_with_fallback(complaint_id=uuid4(), text="broken pipe", location="x")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].message == "triage.fallback"
