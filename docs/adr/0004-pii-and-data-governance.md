# ADR-0004 — PII and data governance

- **Status:** Accepted · 2026-09-26 · cross-cutting, all phases
- **Deciders:** DEV-A (author — this touches `backend/app/` end to end), DEV-B (review)
- **Satisfies:** `00-SPEC.md §613` *"what leaves your machine, to whom, and why that is
  acceptable"* — 1 mark, part of the required 4-ADR set (§646)

## Context

CivicPulse handles one real category of personal data — `reporter_contact` (a citizen's phone
number or email, optional on submission) — plus free-text complaint bodies that could
incidentally contain a name, an address detail, or other identifying content a citizen chooses
to write. The system also sends complaint text to third-party LLM providers (Groq, optionally
Gemini/Ollama) for classification, and persists operational telemetry (logs, metrics, an
in-memory outcome ring) that must never become a second, uncontrolled copy of that data. This
ADR is the single place that states, for every category of data this system touches, what
leaves the machine, to whom, and why that's an acceptable design rather than an oversight.

## What data exists, and its sensitivity

| Field | Where | Sensitivity | Who/what sees it |
|---|---|---|---|
| `text` (complaint body) | `complaints.text`, request body | Potentially identifying (citizens sometimes name themselves/describe their exact address in free text) | Postgres, the active triage provider, the operator dashboard |
| `location` | `complaints.location` | Low — a street/sector, not a full address in practice, but still location data | Postgres, the active triage provider, the operator dashboard |
| `reporter_contact` | `complaints.reporter_contact`, nullable | **Real PII** — phone/email, citizen-supplied and optional | Postgres, the operator dashboard only |
| `ai_summary` | `complaints.ai_summary` | Derived from `text`, same sensitivity class | Postgres, the operator dashboard |
| Triage outcome ring | `app.state.ring`, in-memory, capped | None — structurally cannot hold PII (see below) | This process's own memory only, never persisted, never leaves the pod |
| Structured logs | stdout, `app/logging_config.py` | None, by design (see redaction below) | Whatever log shipper the deployment environment attaches (out of this system's control past stdout) |
| Prometheus metrics | `/metrics` | None — counters/histograms with bounded label cardinality (CLAUDE.md HARD rule 8: `path_template`, never a raw path/id) | Whatever scrapes `/metrics` |

## Decision 1 — what leaves the machine to a third-party LLM provider, and why that's acceptable

**`text` and `location` are sent to the configured triage provider** (`llm:groq`, and
optionally `llm:gemini`/`llm:ollama` if configured — `LLMTriage`/`OllamaTriage`,
`backend/app/providers/triage/`). **`reporter_contact` is never sent** — `TriageService`'s
`triage_with_fallback()` signature only ever takes `text`/`location`, never the contact field;
there is no code path from `ComplaintService.create()` to a provider call that passes contact
information.

**Why this is acceptable:** the complaint body is inherently the thing that needs classifying —
there is no way to triage a complaint without the provider seeing what the complaint says. The
contact field is never needed for classification and is deliberately excluded at the call-site
level (not merely "we don't currently pass it" — the function signature makes it structurally
impossible to pass by accident). `RuleBasedTriage`/`SimulatedTriage` never leave the process at
all — the default `TRIAGE_PROVIDER=simulated` (`.env.example`) means a fresh clone sends
nothing to any third party until a developer explicitly opts into `llm`/`ollama`.

**Ollama is the zero-egress option by design** (`08-AI-TRIAGE.md §3.4`) — self-hosted, `text`
and `location` never leave the cluster/host machine at all. This is documented as the
buy-vs-host tradeoff's privacy dimension, not just its latency/cost one (see `docs/TRIAGE.md
§5`'s real Ollama benchmark).

## Decision 2 — the observability ring structurally cannot hold PII

`app.state.ring` (`TriageService._record()`) stores exactly seven fields, enumerated in
CLAUDE.md HARD rule 13 and enforced by that rule's own binding text — `complaint_id`,
`provider`, `latency_ms`, `fallback`, `cached`, `error_class`, `at`. **No `text`, no `location`,
no `reporter_contact`, no raw prompt.** This is a structural guarantee, not a policy one: the
`_record()` method's own parameter list has no slot for complaint content, so a future change
that accidentally started logging complaint text into the ring would have to add a new
parameter and thread it through every call site — a visible diff, not a silent leak. Verified
by `tests/unit/test_meta_providers.py::test_meta_providers_leaks_no_complaint_text`, which
plants a secret substring nowhere the route can legitimately find it and asserts it's absent
from the full response body.

## Decision 3 — logging: redact defensively, never rely on discipline alone

`app/logging_config.py`'s `_SecretRedactingFilter` and `JsonFormatter._redact()` strip any
`gsk_...`/`AIza...`-shaped substring from every log line and stack trace, unconditionally,
regardless of which formatter is active — belt-and-braces on top of `SecretStr` already
stopping an accidental `repr()`/`model_dump()` leak of a configured API key
(`app/settings.py`). Complaint text is never intentionally logged at all (no `log.info(text)`
anywhere in `services/`/`providers/`), but the redaction filter exists specifically because
"nobody intentionally logs it" is not the same guarantee as "it structurally cannot appear in a
log line" — a future exception message that happens to interpolate a raw request body would
still be caught by this filter for the key-shaped case, though it would not catch complaint
text itself (a genuine, disclosed limit of this specific defence — see "what this ADR does not
claim" below).

## Decision 4 — the operator dashboard is the one place full PII is legitimately visible

`reporter_contact` is returned by the complaint detail/list endpoints and rendered on the
operator dashboard (`frontend/src/pages/Dashboard.tsx`) — this is the one intended, in-scope
place a citizen's contact information is meant to be visible, to the municipal operator who
needs it to follow up on a complaint. This is the entire reason the field exists. No other
consumer (metrics, logs, the ring, the triage provider) ever sees it — access is bounded to
exactly the one system component whose job requires it.

## What this ADR does NOT claim

- **No authentication/authorization layer exists yet** on the operator dashboard or the API —
  anyone who can reach `/api/complaints` can read every `reporter_contact` in the system. This
  is a real, disclosed scope boundary of the assignment (no auth phase was in scope for Phases
  0-6), not a governance decision this ADR is claiming is acceptable in a real deployment. A
  production system handling real citizen PII would need this before launch; noted here rather
  than silently assumed out of scope.
- **The redaction filter is key-shaped, not content-aware.** It stops a credential from leaking
  into a log line; it does not and cannot detect "this log line happens to contain a citizen's
  name because an exception message echoed part of the request body." No such code path exists
  today (verified: no `services/`/`providers/` code logs `text`/`location`/`reporter_contact`
  directly), but this ADR does not claim the redaction filter would catch it if one were
  introduced later — that would need a code-review discipline, not a regex.
- **Seed data (`backend/app/db/seed_data.py`) contains no real PII** — invented names, invented
  phone numbers in a documented test range (`05-DATA-LAYER.md §6.2`'s own stated constraint) —
  this ADR's third-party-provider analysis above is about live traffic, not the seeded demo
  data, which never reaches any LLM provider during seeding (`triaged_by=rules`, `seed.py`
  never calls `TriageService`).

## Rejected alternatives

- **Send `reporter_contact` to the triage provider too, in case it helps classification
  accuracy.** Rejected outright — no classification signal plausibly comes from a phone number
  or email address, and sending it would mean a citizen's contact information leaves the
  machine for zero benefit. Not a real tradeoff, included here only because "did the team
  actually consider this" is worth stating explicitly rather than assuming the exclusion was
  obviously correct.
- **Hash or truncate `text` before sending it to the provider, as a privacy mitigation.**
  Rejected — a hash is useless to a classifier (it needs the actual words), and truncation risks
  losing the escalation language the classifier depends on (`08-AI-TRIAGE.md §3.1`'s
  urgency-term matching). The real mitigation available here is provider choice
  (`TRIAGE_PROVIDER=ollama` for zero egress), not mangling the input.
- **Add a content-scanning redaction pass before logging, to catch complaint text that leaks
  into an exception message.** Rejected as out of scope for this phase — no such leak path
  currently exists (verified above), and building a general PII-detection pass is a
  disproportionate amount of new surface area to defend against a hypothetical future bug rather
  than fixing the actual bug if one is ever introduced. Noted as a real limitation above rather
  than quietly built and over-claimed as complete.
