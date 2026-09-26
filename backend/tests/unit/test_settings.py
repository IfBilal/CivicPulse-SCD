"""06-BACKEND-CORE.md §1: SecretStr must never leak the LLM key via repr or model_dump."""

import json

import pytest

from app.settings import Settings

pytestmark = pytest.mark.unit


def test_settings_repr_redacts_key() -> None:
    s = Settings(llm_api_key="gsk_live_super_secret_value")  # type: ignore[call-arg]
    assert "gsk_" not in repr(s)
    assert "gsk_" not in str(s)
    assert "gsk_" not in json.dumps(s.model_dump(mode="json"))


def test_unknown_env_var_is_a_startup_crash() -> None:
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError, extra="forbid"
        Settings(this_field_does_not_exist="x")  # type: ignore[call-arg]


def test_llm_provider_requires_key() -> None:
    with pytest.raises(Exception):  # noqa: B017
        Settings(triage_provider="llm", llm_api_key="")  # type: ignore[call-arg]


def test_default_provider_is_simulated() -> None:
    assert Settings().triage_provider == "simulated"


def test_settings_are_frozen() -> None:
    s = Settings()
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError, frozen=True
        s.app_env = "prod"  # type: ignore[misc]
