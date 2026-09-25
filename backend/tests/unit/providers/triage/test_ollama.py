"""`OllamaTriage` — `08-AI-TRIAGE.md §3.4`. Every test uses `httpx.MockTransport` — **no real
socket, no real Ollama daemon** (none exists in this sandbox; no Docker, confirmed this
session). Never a live network call.
"""

import asyncio
import json

import httpx
import pytest

from app.domain.enums import Category
from app.providers.triage.ollama import OllamaTriage, OllamaValidationError
from app.settings import Settings

pytestmark = pytest.mark.unit


def _client_with(handler: object) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return httpx.AsyncClient(base_url="http://ollama:11434", transport=transport)


def _settings() -> Settings:
    return Settings()


def test_valid_response_parses() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps(
            {"category": "electricity", "priority": "high", "summary": "outage", "confidence": 0.8}
        )
        return httpx.Response(200, json={"message": {"content": content}})

    provider = OllamaTriage(_settings(), client=_client_with(handler))
    result = asyncio.run(provider.triage(text="power outage", location="x"))
    assert result.category == Category.ELECTRICITY


def test_request_hits_api_chat_with_json_format() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        content = json.dumps(
            {"category": "other", "priority": "normal", "summary": "x", "confidence": 0.5}
        )
        return httpx.Response(200, json={"message": {"content": content}})

    provider = OllamaTriage(_settings(), client=_client_with(handler))
    asyncio.run(provider.triage(text="x", location="y"))
    assert captured["path"] == "/api/chat"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["format"] == "json"
    assert body["stream"] is False
    assert body["options"] == {"temperature": 0, "num_predict": 200}


def test_malformed_json_raises_ollama_validation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "not json at all"}})

    provider = OllamaTriage(_settings(), client=_client_with(handler))
    with pytest.raises(OllamaValidationError):
        asyncio.run(provider.triage(text="x", location="y"))


def test_bad_enum_raises_ollama_validation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps(
            {"category": "vip", "priority": "low", "summary": "x", "confidence": 0.5}
        )
        return httpx.Response(200, json={"message": {"content": content}})

    provider = OllamaTriage(_settings(), client=_client_with(handler))
    with pytest.raises(OllamaValidationError):
        asyncio.run(provider.triage(text="x", location="y"))


def test_unexpected_response_shape_raises_ollama_validation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"totally": "unexpected"})

    provider = OllamaTriage(_settings(), client=_client_with(handler))
    with pytest.raises(OllamaValidationError):
        asyncio.run(provider.triage(text="x", location="y"))


def test_429_propagates_as_retryable_http_status_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    provider = OllamaTriage(_settings(), client=_client_with(handler))
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        asyncio.run(provider.triage(text="x", location="y"))
    assert excinfo.value.response.status_code == 429


def test_503_propagates_as_retryable_http_status_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    provider = OllamaTriage(_settings(), client=_client_with(handler))
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        asyncio.run(provider.triage(text="x", location="y"))
    assert excinfo.value.response.status_code == 503


def test_400_raises_ollama_validation_error_not_http_status_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad request"})

    provider = OllamaTriage(_settings(), client=_client_with(handler))
    with pytest.raises(OllamaValidationError):
        asyncio.run(provider.triage(text="x", location="y"))


def test_name_is_llm_ollama() -> None:
    provider = OllamaTriage(_settings(), client=_client_with(lambda r: httpx.Response(200)))
    assert provider.name == "llm:ollama"


def test_aclose_closes_owned_client() -> None:
    provider = OllamaTriage(_settings())  # no injected client -> owns its own
    asyncio.run(provider.aclose())
    assert provider._client.is_closed


def test_aclose_does_not_close_injected_client() -> None:
    client = _client_with(lambda r: httpx.Response(200))
    provider = OllamaTriage(_settings(), client=client)
    asyncio.run(provider.aclose())
    assert not client.is_closed
    asyncio.run(client.aclose())
