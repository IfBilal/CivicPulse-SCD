"""`SimulatedTriage` — determinism and each `FailureMode` branch. `08-AI-TRIAGE.md §3.2`."""

import asyncio

import pytest

from app.domain.enums import Category, Priority
from app.providers.triage.simulated import (
    FailureMode,
    SimulatedMalformedResponseError,
    SimulatedRateLimitError,
    SimulatedServerError,
    SimulatedTriage,
    SimulatedValidationError,
)

pytestmark = pytest.mark.unit


def test_deterministic_same_input_same_output() -> None:
    a = SimulatedTriage(seed=42)
    b = SimulatedTriage(seed=42)
    r1 = asyncio.run(a.triage(text="water leak on street 5", location="x"))
    r2 = asyncio.run(b.triage(text="water leak on street 5", location="x"))
    assert r1 == r2


def test_different_text_different_output_likely() -> None:
    provider = SimulatedTriage(seed=42)
    r1 = asyncio.run(provider.triage(text="water leak", location="x"))
    r2 = asyncio.run(provider.triage(text="totally different complaint text here", location="x"))
    assert (r1.category, r1.priority, r1.summary) != (r2.category, r2.priority, r2.summary)


def test_different_seed_different_output_likely() -> None:
    a = SimulatedTriage(seed=1)
    b = SimulatedTriage(seed=2)
    r1 = asyncio.run(a.triage(text="water leak on street 5", location="x"))
    r2 = asyncio.run(b.triage(text="water leak on street 5", location="x"))
    assert (r1.category, r1.priority, r1.summary, r1.confidence) != (
        r2.category,
        r2.priority,
        r2.summary,
        r2.confidence,
    )


def test_name_is_simulated() -> None:
    assert SimulatedTriage().name == "simulated"


async def _drain_timeout(provider: SimulatedTriage) -> None:
    async with asyncio.timeout(0.05):
        await provider.triage(text="x", location="x")


def test_raise_mode_raises() -> None:
    provider = SimulatedTriage(failure_mode=FailureMode.RAISE)
    with pytest.raises(RuntimeError):
        asyncio.run(provider.triage(text="x", location="x"))


def test_timeout_mode_is_cancellable_by_caller() -> None:
    provider = SimulatedTriage(failure_mode=FailureMode.TIMEOUT)
    with pytest.raises(TimeoutError):
        asyncio.run(_drain_timeout(provider))


def test_rate_limit_mode_raises_rate_limit_error() -> None:
    provider = SimulatedTriage(failure_mode=FailureMode.RATE_LIMIT)
    with pytest.raises(SimulatedRateLimitError):
        asyncio.run(provider.triage(text="x", location="x"))


def test_server_error_mode_raises_server_error() -> None:
    provider = SimulatedTriage(failure_mode=FailureMode.SERVER_ERROR)
    with pytest.raises(SimulatedServerError):
        asyncio.run(provider.triage(text="x", location="x"))


def test_malformed_mode_raises_malformed_error() -> None:
    provider = SimulatedTriage(failure_mode=FailureMode.MALFORMED)
    with pytest.raises(SimulatedMalformedResponseError):
        asyncio.run(provider.triage(text="x", location="x"))


def test_bad_enum_mode_raises_validation_error() -> None:
    provider = SimulatedTriage(failure_mode=FailureMode.BAD_ENUM)
    with pytest.raises(SimulatedValidationError):
        asyncio.run(provider.triage(text="x", location="x"))


def test_overlong_summary_mode_raises_validation_error() -> None:
    provider = SimulatedTriage(failure_mode=FailureMode.OVERLONG_SUMMARY)
    with pytest.raises(SimulatedValidationError):
        asyncio.run(provider.triage(text="x", location="x"))


def test_injection_obey_mode_raises_validation_error() -> None:
    provider = SimulatedTriage(failure_mode=FailureMode.INJECTION_OBEY)
    with pytest.raises(SimulatedValidationError):
        asyncio.run(provider.triage(text="x", location="x"))


def test_low_confidence_mode_returns_result_below_threshold() -> None:
    provider = SimulatedTriage(failure_mode=FailureMode.LOW_CONFIDENCE)
    result = asyncio.run(provider.triage(text="x", location="x"))
    assert result.confidence < 0.35
    assert result.category in Category
    assert result.priority in Priority


def test_none_mode_returns_valid_result() -> None:
    provider = SimulatedTriage(failure_mode=FailureMode.NONE)
    result = asyncio.run(provider.triage(text="water main burst", location="x"))
    assert result.category in Category
    assert result.priority in Priority
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.summary) <= 140


def test_all_nine_failure_modes_exist() -> None:
    assert {m.value for m in FailureMode} == {
        "none",
        "raise",
        "timeout",
        "malformed",
        "rate_limit",
        "server_error",
        "bad_enum",
        "overlong_summary",
        "low_confidence",
        "injection_obey",
    }
