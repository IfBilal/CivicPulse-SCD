"""App factory. Importable without env, DB, or Redis so `make openapi` needs no server."""

from typing import Any

from fastapi import FastAPI

from app.errors import register_error_handlers
from app.routes import complaints, meta, ops, stats

_REQUEST_ID_HEADER = {
    "description": "Echoed from the request, or generated (UUIDv4) if absent/invalid",
    "schema": {"type": "string", "format": "uuid"},
}


def create_app() -> FastAPI:
    app = FastAPI(
        title="CivicPulse API",
        version="1.0.0",
        # Relative, never absolute — an absolute URL smuggles an environment into the schema
        # and breaks build-once-deploy-many (ADR-0002, 04-CONTRACTS.md §6.10).
        servers=[{"url": "/"}],
    )
    for module in (complaints, stats, meta, ops):
        app.include_router(module.router)
    register_error_handlers(app)
    app.openapi = lambda: _contract_openapi(app)  # type: ignore[method-assign]
    return app


def _contract_openapi(app: FastAPI) -> dict[str, Any]:
    """FastAPI's schema, minus its phantom 422s, plus X-Request-ID on every response."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = FastAPI.openapi(app)
    for path_item in schema["paths"].values():
        for op in path_item.values():
            op["responses"].pop("422", None)
            for resp in op["responses"].values():
                resp.setdefault("headers", {})["X-Request-ID"] = _REQUEST_ID_HEADER
    for name in ("HTTPValidationError", "ValidationError"):
        schema.get("components", {}).get("schemas", {}).pop(name, None)
    app.openapi_schema = schema
    return schema


app = create_app()
