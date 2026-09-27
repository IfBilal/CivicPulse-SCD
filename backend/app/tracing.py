"""OpenTelemetry setup — `10-OBSERVABILITY.md §6` bonus (+2). Off by default
(`settings.otel_exporter_otlp_endpoint == ""`): every test/CI/dev run that doesn't set the env
var gets a no-op tracer, so this module can never be the reason an unrelated test fails.

Span tree this wires up, matching the doc's required chain exactly:
    HTTP POST /api/complaints            [server span, auto — FastAPIInstrumentor]
    ├── triage.cache.get                 [internal, manual — see triage_service.py]
    ├── triage.llm.call                  [internal, manual — attrs: provider, attempt, outcome]
    │   └── HTTP POST api.groq.com/...   [client span, auto — HTTPXClientInstrumentor]
    ├── triage.fallback.rules            [internal, manual, only on the fallback path]
    └── db.insert complaints             [client span, auto — SQLAlchemyInstrumentor]

Attribute hygiene (non-negotiable, same boundary as CLAUDE.md HARD rule 13 for the observability
ring): never put complaint text, `reporter_contact`, or the API key on a span. Every manual span
in `triage_service.py` only ever sets `provider`/`attempt`/`outcome`-shaped attributes — the same
allowed set the ring buffer already uses, not a new, wider surface.
"""

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF, ALWAYS_ON

from app.settings import Settings

log = logging.getLogger("app.tracing")


def configure_tracing(settings: Settings) -> None:
    """Call once, in the lifespan, before `FastAPIInstrumentor.instrument_app`. A blank endpoint
    means tracing is disabled for this run — the SDK is still installed (imports must not fail
    either way) but every span is dropped by `ALWAYS_OFF`, which costs one sampling-decision
    branch per span, not a real per-span cost."""
    sampler = ALWAYS_ON if settings.otel_exporter_otlp_endpoint else ALWAYS_OFF
    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: settings.otel_service_name}),
        sampler=sampler,
    )
    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        log.info(
            "tracing.enabled",
            extra={"extra_fields": {"endpoint": settings.otel_exporter_otlp_endpoint}},
        )
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()

    # `SQLAlchemyInstrumentor().instrument()` with no `engine=` hooks the *next* engine SQLAlchemy
    # creates — a no-op here, since `app/db/session.py`'s module-level `engine` is already
    # constructed by the time this runs (confirmed live: zero `db.insert`/`SELECT` spans appeared
    # in a real trace against a real seeded Postgres until this was passed explicitly). Passing
    # the real engine's sync counterpart (`AsyncEngine.sync_engine` — this instrumentor hooks
    # SQLAlchemy Core events, which fire on the sync engine underlying every async one) is what
    # actually wires it to spans this app's session factory produces.
    from app.db.session import engine as _app_engine

    SQLAlchemyInstrumentor().instrument(engine=_app_engine.sync_engine)


def instrument_app(app: object) -> None:
    """Separate from `configure_tracing` because `FastAPIInstrumentor.instrument_app` needs the
    `FastAPI` instance, which doesn't exist yet at the point `configure_tracing` runs inside the
    lifespan (the lifespan is attached to the app, not the other way around)."""
    FastAPIInstrumentor.instrument_app(app)


tracer = trace.get_tracer("civicpulse.backend")
