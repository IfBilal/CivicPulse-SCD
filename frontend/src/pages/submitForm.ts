import { LIMITS } from "../api/schemaMeta";
import type { ComplaintCreate } from "../api/types";

export type Field = "text" | "location" | "reporter_contact";
export type Stage = "idle" | "submitting" | "classifying" | "slow";

// Timings are part of the UX contract (11-FRONTEND.md §3.1): AI calls take seconds, say so.
export const CLASSIFYING_AFTER_MS = 1500;
export const SLOW_AFTER_MS = 6000;

export const STAGE_COPY: Record<Exclude<Stage, "idle">, string> = {
  submitting: "Sending your report…",
  classifying: "Classifying with AI…",
  slow: "The model is slow — we'll fall back to keyword rules if needed.",
};

/** Client-side mirror of the server's bounds. The numbers come from the generated schema. */
export function validate(v: ComplaintCreate): Partial<Record<Field, string>> {
  const e: Partial<Record<Field, string>> = {};
  const text = v.text.trim();
  const loc = v.location.trim();
  if (text.length < LIMITS.text.min) e.text = `Must be at least ${LIMITS.text.min} characters.`;
  else if (text.length > LIMITS.text.max) e.text = `Must be at most ${LIMITS.text.max} characters.`;
  if (loc.length < LIMITS.location.min) e.location = `Must be at least ${LIMITS.location.min} characters.`;
  else if (loc.length > LIMITS.location.max) e.location = `Must be at most ${LIMITS.location.max} characters.`;
  if ((v.reporter_contact ?? "").length > LIMITS.contact.max) e.reporter_contact = `Must be at most ${LIMITS.contact.max} characters.`;
  return e;
}
