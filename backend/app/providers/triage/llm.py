"""`LLMTriage` — `08-AI-TRIAGE.md §3.3`. The production path (Groq, OpenAI-compatible).

**CODE + UNIT TESTS ONLY.** This class is never exercised against a live endpoint in this
session — see `docs/AI-USAGE.md`'s 2026-09-25 security-incident entry. Tests inject a fake
client object shaped like `AsyncOpenAI` (same `.chat.completions.create(...)` surface) that
returns canned JSON strings, including malformed ones.

`max_retries=0` is NOT optional: the OpenAI SDK retries twice by default with its own backoff,
which would silently multiply `TriageService`'s carefully-budgeted single-retry policy — a
"single jittered retry" would become up to six attempts and the 10s cap would become 30s+.
`TriageService` owns retry policy, not the SDK.

Regardless of what JSON mode "guarantees," the response is always run through
`TriageResult.model_validate_json` — `08-AI-TRIAGE.md §2.5` item 1: *"validate the response
against your Pydantic model anyway."*
"""

from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from app.providers.triage.prompt import SYSTEM_PROMPT, build_user_prompt
from app.schemas.triage import TriageResult


class LLMValidationError(Exception):
    """Raised when the model's response is not valid JSON, or is valid JSON that fails
    `TriageResult` validation (bad enum, overlong summary, missing field, ...).
    `TriageService.NON_RETRYABLE` recognises this type — a schema failure is deterministic
    under retry, so it goes straight to fallback with zero retries."""


class _ChatCompletionsLike(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class _ChatLike(Protocol):
    completions: _ChatCompletionsLike


class _AsyncOpenAILike(Protocol):
    """The minimal slice of `AsyncOpenAI`'s interface this module depends on — lets tests inject
    a fake client without importing the real SDK's concrete types."""

    chat: _ChatLike

    async def close(self) -> None: ...


class _SecretLike(Protocol):
    def get_secret_value(self) -> str: ...


class Settings(Protocol):
    """The minimal slice of `app.settings.Settings` this module needs — declared narrowly so
    this file doesn't import the whole app settings module, and so tests can pass a minimal
    stand-in.

    `llm_api_key` is `SecretStr`-shaped, not `str` — matches the real `app.settings.Settings`
    field (`06-BACKEND-CORE.md §1`: `SecretStr` so `repr()`/`.model_dump()` never leak it).
    Passing the wrapper itself to `AsyncOpenAI(api_key=...)` would hand the SDK a `SecretStr`
    object instead of the key, which either errors or — worse — silently sends the masked
    `**********` string if something calls `str()` on it upstream; `.get_secret_value()` must
    be unwrapped explicitly, once, right before it leaves this module.

    `llm_base_url` is typed `object`, not `str`: the real `app.settings.Settings` field is
    `AnyHttpUrl` (a pydantic `Url`), and this module only ever does `str(settings.llm_base_url)`
    at the point of use (below) — never a string-only method — so `object` is the honest bound
    rather than a `str` annotation the real settings class doesn't actually satisfy.

    Declared as read-only `@property` getters, not plain attributes: `app.settings.Settings`
    is `frozen=True` (`06-BACKEND-CORE.md §1`), so its fields are read-only from the outside —
    a plain `Protocol` attribute is implicitly read-write, which a frozen model structurally
    fails to satisfy even though every value it actually needs is readable."""

    @property
    def llm_base_url(self) -> object: ...
    @property
    def llm_api_key(self) -> _SecretLike: ...
    @property
    def llm_model(self) -> str: ...
    @property
    def triage_timeout_s(self) -> float: ...


def _build_default_client(settings: Settings) -> _AsyncOpenAILike:
    from openai import AsyncOpenAI  # local import: keep the SDK out of modules that don't need it

    # The real AsyncOpenAI client's `.chat.completions.create` structurally satisfies
    # `_AsyncOpenAILike` at runtime; mypy can't see that because `AsyncChat` isn't declared
    # against our narrow Protocol. Cast rather than widen the Protocol to the SDK's full shape.
    client: _AsyncOpenAILike = AsyncOpenAI(  # type: ignore[assignment]
        base_url=str(settings.llm_base_url),
        api_key=settings.llm_api_key.get_secret_value(),
        timeout=httpx.Timeout(settings.triage_timeout_s, connect=2.0),
        max_retries=0,  # WE own retry policy — see module docstring
    )
    return client


class LLMTriage:
    """Groq (OpenAI-compatible). `name` is configurable so a Gemini-via-OpenAI-shim deployment
    can still report `llm:gemini` in `triaged_by` without a second class."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: _AsyncOpenAILike | None = None,
        name: str = "llm:groq",
    ) -> None:
        self._settings = settings
        self._client = client if client is not None else _build_default_client(settings)
        self.name = name

    async def triage(self, *, text: str, location: str) -> TriageResult:
        user_prompt = build_user_prompt(text=text, location=location)
        response = await self._client.chat.completions.create(
            model=self._settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=200,
            top_p=1,
            seed=42,
            stream=False,
        )
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, KeyError) as exc:
            raise LLMValidationError(f"unexpected response shape: {exc!r}") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMValidationError("empty or non-string content from provider")

        cleaned = _strip_code_fence(content)

        try:
            # Never trust JSON mode's own guarantee — validate against the Pydantic model
            # regardless of what the provider claims about its output shape.
            return TriageResult.model_validate_json(cleaned)
        except ValidationError as exc:
            raise LLMValidationError(f"schema validation failed: {exc}") from exc
        except ValueError as exc:  # includes json.JSONDecodeError, a ValueError subclass
            raise LLMValidationError(f"invalid JSON from provider: {exc}") from exc

    async def aclose(self) -> None:
        await self._client.close()


def _strip_code_fence(content: str) -> str:
    """The model will eventually return a ```json ... ``` fence despite JSON mode. Strip it
    defensively; validation still runs on the result either way."""
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped
