"""`OllamaTriage` — `08-AI-TRIAGE.md §3.4`. The zero-dependency, offline path.

Same interface as `LLMTriage`, different transport: `POST {OLLAMA_BASE_URL}/api/chat` via
`httpx.AsyncClient`, `format: "json"`, `stream: false`.

Unit tests (this module's own test file) use `httpx.MockTransport` to fake the HTTP layer,
never a real socket — CLAUDE.md HARD rule 15, no real network in a test. A real, one-off
buy-vs-host benchmark WAS run against a real local Ollama daemon (2026-09-26, `llama3.2:1b`,
outside any test/CI path — see `docs/TRIAGE.md` §4/§5 for the numbers and `docs/AI-USAGE.md`
for how): this module's own tests still never touch a real socket, that benchmark used this
same code path manually from a scratch script.
"""

from typing import Protocol

import httpx
from pydantic import ValidationError

from app.providers.triage.prompt import SYSTEM_PROMPT, build_user_prompt
from app.schemas.triage import TriageResult


class OllamaValidationError(Exception):
    """Raised when Ollama's response is not valid JSON, or valid JSON that fails `TriageResult`
    validation. `TriageService.NON_RETRYABLE` recognises this type — no retry."""


class Settings(Protocol):
    # `object`, not `str`: the real `app.settings.Settings.ollama_base_url` is `AnyHttpUrl` (a
    # pydantic `Url`), and this module only ever does `str(settings.ollama_base_url)` — never a
    # string-only method — so `object` is the honest bound. Same reasoning as `llm.py`'s
    # `Settings.llm_base_url`. Read-only `@property` getters, not plain attributes: the real
    # `Settings` is `frozen=True`, and a plain Protocol attribute is implicitly read-write.
    @property
    def ollama_base_url(self) -> object: ...
    @property
    def ollama_model(self) -> str: ...
    @property
    def triage_timeout_s(self) -> float: ...


class OllamaTriage:
    name = "llm:ollama"

    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=str(settings.ollama_base_url),
            timeout=httpx.Timeout(settings.triage_timeout_s, connect=2.0),
        )

    async def triage(self, *, text: str, location: str) -> TriageResult:
        user_prompt = build_user_prompt(text=text, location=location)
        payload = {
            "model": self._settings.ollama_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "options": {"temperature": 0, "num_predict": 200},
            "stream": False,
        }

        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429 or 500 <= status < 600:
                raise  # RETRYABLE — TriageService recognises httpx.HTTPStatusError shapes
            raise OllamaValidationError(f"ollama returned {status}") from exc

        try:
            body = response.json()
            content = body["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaValidationError(f"unexpected ollama response shape: {exc!r}") from exc

        if not isinstance(content, str) or not content.strip():
            raise OllamaValidationError("empty or non-string content from ollama")

        try:
            return TriageResult.model_validate_json(content)
        except ValidationError as exc:
            raise OllamaValidationError(f"schema validation failed: {exc}") from exc
        except ValueError as exc:
            raise OllamaValidationError(f"invalid JSON from ollama: {exc}") from exc

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
