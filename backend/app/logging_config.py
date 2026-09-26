"""Structured JSON logging — `06-BACKEND-CORE.md §3.2`. stdout only, never a file handler
(container filesystems are ephemeral; the log shipper reads stdout)."""

import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

import orjson

from app.middleware.request_id import request_id_var
from app.settings import Settings

# Belt-and-braces redaction: SecretStr already stops accidental `repr()`/`model_dump()` leaks
# (settings.py), this catches a key that somehow reaches a formatted log message another way.
_SECRET_PATTERNS = (
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[\w-]{35}"),
)


def _redact(msg: str) -> str:
    for pattern in _SECRET_PATTERNS:
        msg = pattern.sub("***REDACTED***", msg)
    return msg


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service: str, version: str) -> None:
        super().__init__()
        self._service = service
        self._version = version

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": _redact(record.getMessage()),
            "request_id": request_id_var.get(),
            "service": self._service,
            "version": self._version,
        }
        extra_fields = getattr(record, "extra_fields", None)
        if extra_fields:
            payload.update(extra_fields)
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_class"] = record.exc_info[0].__name__
            payload["stack"] = _redact(self.formatException(record.exc_info))
        return orjson.dumps(payload).decode()


class _SecretRedactingFilter(logging.Filter):
    """Belt-and-braces: even if a formatter other than JsonFormatter is ever used, a raw
    message containing a key pattern never reaches stdout unredacted."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(str(record.msg))
        return True


# The one handler this module has installed on the root logger, if any — tracked so a second
# `configure_logging()` call (e.g. a test constructing `create_app()` more than once in the same
# process) removes only *this* handler, never anything else already on the root logger. Wiping
# every existing handler unconditionally used to also strip pytest's own `caplog` handler,
# silently breaking any test asserting on `caplog.records` that ran after the first app-factory
# call in the same process (found via a real CI run — see docs/ENGINEERING-NOTES.md).
_our_handler: logging.Handler | None = None


def configure_logging(settings: Settings) -> None:
    global _our_handler
    root = logging.getLogger()
    root.setLevel(settings.log_level)

    # Remove only the handler *we* previously installed, not every handler on the root logger —
    # a caller (pytest's caplog, an embedding host, ...) may have its own for good reason.
    # Removing unrelated handlers here used to silently break `caplog`-based assertions in any
    # test running after one that boots the real app via `TestClient`/`lifespan` (found via a
    # CI-only failure, 2026-09-25 — see docs/AI-USAGE.md).
    if _our_handler is not None and _our_handler in root.handlers:
        root.removeHandler(_our_handler)

    # Never a FileHandler / RotatingFileHandler — stdout only.
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_SecretRedactingFilter())
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter(service="backend", version=settings.version))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    _our_handler = handler

    # Hijack uvicorn's own loggers so everything goes through one JSON formatter — otherwise
    # uvicorn.access emits its own plain-text lines and the "JSON to stdout" claim is false.
    for uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(uvicorn_logger_name)
        uv_logger.handlers = []
        uv_logger.propagate = True

    # Defensive: re-enable every logger that already exists. Found via a real full-suite CI run
    # (not assumed): app.services.triage_service's "app.triage" logger has `.disabled == True`
    # by the time later tests run, silently dropping every record regardless of level/handlers/
    # propagation (Logger.disabled short-circuits isEnabledFor entirely). Nothing in this
    # codebase's own source sets it, and the one place in pytest's own logging plugin that does
    # (`_pytest/logging.py::_disable_loggers`) is gated behind the unused `--logger-disable`
    # option in this repo — so whatever's doing it, this neutralizes it unconditionally rather
    # than chasing the exact trigger across every test/plugin interaction. Idempotent, and there
    # is no scenario where this app wants one of its own loggers left disabled.
    for logger_name in list(logging.root.manager.loggerDict):
        logging.getLogger(logger_name).disabled = False
