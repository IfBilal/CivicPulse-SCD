import gsap from "gsap";
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { LIMITS } from "../api/schemaMeta";
import type { Complaint, ComplaintCreate } from "../api/types";
import { CategoryChip, PriorityTag, ProviderBadge } from "../components/Badges";
import { DecodeText } from "../components/DecodeText";
import { Glass } from "../components/Glass";
import { prefersReducedMotion, useReveal } from "../hooks/motion";
import { CATEGORY_HEX, shortId } from "../lib/format";
import { emitPulse } from "../lib/pulse";
import { CLASSIFYING_AFTER_MS, SLOW_AFTER_MS, STAGE_COPY, validate, type Field, type Stage } from "./submitForm";

const PIPELINE = [
  { key: "validate", label: "Validate", sub: "bounds from the live contract" },
  { key: "triage", label: "AI triage", sub: "category · priority · summary" },
  { key: "guard", label: "Fallback guard", sub: "keyword rules if the model stalls" },
  { key: "persist", label: "Filed", sub: "on the operator dashboard" },
] as const;

function stageIndex(stage: Stage, done: boolean): number {
  if (done) return 4;
  return { idle: -1, submitting: 0, classifying: 1, slow: 2 }[stage];
}

export default function Submit() {
  const [values, setValues] = useState<ComplaintCreate>({ text: "", location: "", reporter_contact: "" });
  const [touched, setTouched] = useState<Partial<Record<Field, boolean>>>({});
  const [serverErrors, setServerErrors] = useState<Partial<Record<Field, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [result, setResult] = useState<Complaint | null>(null);
  const timers = useRef<number[]>([]);
  const resultRef = useRef<HTMLDivElement>(null);
  const scope = useReveal<HTMLDivElement>();

  const clientErrors = validate(values);
  const busy = stage !== "idle";
  const errorFor = (f: Field) => serverErrors[f] ?? (touched[f] ? clientErrors[f] : undefined);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  useLayoutEffect(() => {
    if (!result || !resultRef.current || prefersReducedMotion()) return;
    const ctx = gsap.context(() => {
      const tl = gsap.timeline();
      tl.from(resultRef.current, { opacity: 0, y: 30, scale: 0.97, duration: 0.6, ease: "expo.out" })
        .from(".scanline", { yPercent: -100, duration: 0.9, ease: "power2.inOut" }, 0)
        .from("[data-result-item]", { opacity: 0, x: -12, stagger: 0.08, duration: 0.45, ease: "power3.out" }, 0.2);
    }, resultRef);
    return () => ctx.revert();
  }, [result]);

  const set = (f: Field) => (e: { target: { value: string } }) => {
    setValues((v) => ({ ...v, [f]: e.target.value }));
    setServerErrors((s) => ({ ...s, [f]: undefined }));
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched({ text: true, location: true, reporter_contact: true });
    if (busy || Object.keys(clientErrors).length) return;
    setFormError(null);
    setServerErrors({});
    setResult(null);
    setStage("submitting");
    timers.current = [
      window.setTimeout(() => setStage("classifying"), CLASSIFYING_AFTER_MS),
      window.setTimeout(() => setStage("slow"), SLOW_AFTER_MS),
    ];
    try {
      const contact = values.reporter_contact?.trim();
      const created = await api.createComplaint({ text: values.text.trim(), location: values.location.trim(), reporter_contact: contact || null });
      setResult(created);
      emitPulse(CATEGORY_HEX[created.category]);
      setValues({ text: "", location: "", reporter_contact: "" });
      setTouched({});
    } catch (err) {
      if (err instanceof ApiError && err.body.error.fields?.length) {
        const mapped: Partial<Record<Field, string>> = {};
        for (const f of err.body.error.fields) mapped[f.field as Field] = f.message;
        setServerErrors(mapped);
      } else {
        setFormError(err instanceof ApiError ? err.body.error.message : "Something went wrong. Please try again.");
      }
    } finally {
      timers.current.forEach(clearTimeout);
      setStage("idle");
    }
  }

  const textLen = values.text.trim().length;
  const active = stageIndex(stage, !!result && !busy);

  return (
    <div ref={scope}>
      <header className="page-head" data-reveal>
        <p className="eyebrow">Citizen report</p>
        <h1 className="page-title">
          Tell the city what&apos;s <DecodeText className="grad" text="broken." />
        </h1>
        <p className="page-sub">
          Describe the problem in your own words — English, Urdu or both. Our AI reads it, sorts it and routes it to the right
          department in seconds. If the AI is down, you still get filed.
        </p>
      </header>

      <div className="grid-2">
        <Glass>
          <form onSubmit={onSubmit} noValidate aria-busy={busy}>
            {formError && (
              <div className="banner error" role="alert">
                <span aria-hidden>⚠</span>
                <span>{formError}</span>
              </div>
            )}

            <div className="field">
              <label htmlFor="text">
                What&apos;s the problem?
                <span className={`counter ${textLen > LIMITS.text.max ? "bad" : ""}`}>
                  {textLen}/{LIMITS.text.max}
                </span>
              </label>
              <textarea
                id="text"
                className="textarea"
                placeholder="e.g. Pani ka pipe burst ho gaya hai near the masjid, water on the road since fajr…"
                value={values.text}
                onChange={set("text")}
                onBlur={() => setTouched((t) => ({ ...t, text: true }))}
                aria-invalid={!!errorFor("text")}
                aria-describedby="text-error"
                disabled={busy}
              />
              <p id="text-error" className="field-error" aria-live="polite">
                {errorFor("text")}
              </p>
            </div>

            <div className="field">
              <label htmlFor="location">Where?</label>
              <input
                id="location"
                className="input"
                placeholder="Street 12, Sector G-9/1, Islamabad"
                value={values.location}
                onChange={set("location")}
                onBlur={() => setTouched((t) => ({ ...t, location: true }))}
                aria-invalid={!!errorFor("location")}
                aria-describedby="location-error"
                disabled={busy}
              />
              <p id="location-error" className="field-error" aria-live="polite">
                {errorFor("location")}
              </p>
            </div>

            <div className="field">
              <label htmlFor="contact">
                Contact <span className="opt">optional · phone or email</span>
              </label>
              <input
                id="contact"
                className="input"
                placeholder="+92 300 1234567"
                value={values.reporter_contact ?? ""}
                onChange={set("reporter_contact")}
                aria-invalid={!!errorFor("reporter_contact")}
                aria-describedby="contact-error"
                disabled={busy}
              />
              <p id="contact-error" className="field-error" aria-live="polite">
                {errorFor("reporter_contact")}
              </p>
            </div>

            <div className="row">
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? <span className="spinner" aria-hidden /> : <span aria-hidden>⟶</span>}
                {busy ? "Working…" : "Submit report"}
              </button>
              {busy && (
                <p role="status" className="stage-copy" data-stage={stage}>
                  {STAGE_COPY[stage as Exclude<Stage, "idle">]}
                </p>
              )}
            </div>
          </form>
        </Glass>

        <div className="stack">
          {result ? (
            <div ref={resultRef} className="glass result-card" aria-live="polite" data-testid="result">
              <div className="scanline" aria-hidden />
              <p className="eyebrow" style={{ color: "var(--ok)" }}>
                Filed · #{shortId(result.id)}
              </p>
              <h2 className="card-title" style={{ fontSize: 22, marginTop: 8 }} data-result-item>
                {result.ai_summary ?? result.text.slice(0, 120)}
              </h2>
              <div className="row" style={{ margin: "14px 0" }} data-result-item>
                <CategoryChip category={result.category} />
                <PriorityTag priority={result.priority} />
              </div>
              <dl className="kv" data-result-item>
                <dt>Classified by</dt>
                <dd>
                  <ProviderBadge provider={result.triaged_by} />
                </dd>
                <dt>Triage time</dt>
                <dd className="mono">{(result.triage_latency_ms / 1000).toFixed(2)} s</dd>
                {result.triage_confidence != null && (
                  <>
                    <dt>Confidence</dt>
                    <dd>
                      <span className="meter" style={{ ["--v" as string]: result.triage_confidence }} aria-hidden />
                      <span className="mono">{Math.round(result.triage_confidence * 100)}%</span>
                    </dd>
                  </>
                )}
                <dt>Where</dt>
                <dd>{result.location}</dd>
              </dl>
              <div className="row" style={{ marginTop: 18 }} data-result-item>
                <Link className="btn btn-sm" to="/dashboard">
                  Open dashboard →
                </Link>
                <button className="btn btn-sm btn-ghost" onClick={() => setResult(null)}>
                  Report another
                </button>
              </div>
            </div>
          ) : (
            <Glass as="aside" aria-label="How triage works">
              <h2 className="card-title">What happens when you press submit</h2>
              <p className="card-sub">Live pipeline — watch each stage light up.</p>
              <ol className="pipeline">
                {PIPELINE.map((p, i) => (
                  <li key={p.key} className={i < active ? "done" : i === active ? "active" : ""}>
                    <span className="node" aria-hidden />
                    <div>
                      <b>{p.label}</b>
                      <span>{p.sub}</span>
                    </div>
                  </li>
                ))}
              </ol>
              <p className="hint" style={{ marginTop: 14 }}>
                Text {LIMITS.text.min}–{LIMITS.text.max} characters · location {LIMITS.location.min}–{LIMITS.location.max}. These
                limits are read from the server&apos;s own contract.
              </p>
            </Glass>
          )}
        </div>
      </div>
    </div>
  );
}
