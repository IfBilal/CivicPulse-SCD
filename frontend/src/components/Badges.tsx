import type { CacheState, Category, Priority, Status, TriagedBy } from "../api/types";
import { CATEGORY_META, PRIORITY_META, providerLabel, STATUS_META } from "../lib/format";

export function CategoryChip({ category }: { category: Category }) {
  const m = CATEGORY_META[category];
  return (
    <span className="chip" style={{ ["--c" as string]: m.color }}>
      <span className="dot" aria-hidden />
      {m.label}
    </span>
  );
}

export function PriorityTag({ priority }: { priority: Priority }) {
  const m = PRIORITY_META[priority];
  return (
    <span className="chip" style={{ ["--c" as string]: m.color }} title={`${m.label} priority`}>
      <span aria-hidden style={{ color: m.color, fontSize: 9, letterSpacing: -2 }}>{m.icon}</span>
      {m.label}
    </span>
  );
}

export function StatusPill({ status }: { status: Status }) {
  const m = STATUS_META[status];
  return (
    <span className="chip" style={{ ["--c" as string]: m.color, borderColor: m.color }}>
      <span aria-hidden style={{ color: m.color }}>{m.icon}</span>
      {m.label}
    </span>
  );
}

const FALLBACK_TIP = "AI provider unavailable; classified by keyword rules";

/** Solid = classified by an AI model; outlined + tooltip = degraded to keyword rules. The
 *  degradation is shown to the citizen on purpose (11-FRONTEND.md §3.1). */
export function ProviderBadge({ provider }: { provider: TriagedBy }) {
  const degraded = provider === "rules:fallback";
  return (
    <span
      className={`badge-provider ${degraded ? "outline" : "solid"}`}
      title={degraded ? FALLBACK_TIP : `Classified by ${provider}`}
      data-provider={provider}
    >
      <span aria-hidden>{degraded ? "⚠" : "✦"}</span>
      {providerLabel(provider)}
      {degraded && <span className="sr-only">. {FALLBACK_TIP}</span>}
    </span>
  );
}

export function CacheBadge({ cache, ageSeconds }: { cache: CacheState; ageSeconds: number | null | undefined }) {
  const hit = cache === "HIT";
  return (
    <span className={`badge-cache ${hit ? "hit" : "miss"}`} role="status" data-cache={cache}>
      <span aria-hidden>{hit ? "⚡" : "⟳"}</span>
      <b>{cache}</b>
      <span>{hit ? `cached ${ageSeconds ?? 0} s ago` : "computed just now"}</span>
    </span>
  );
}
