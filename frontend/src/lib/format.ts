// Presentation-only lookups: labels, colours, icons. No rule about what is *allowed* lives here.
import type { Category, Priority, Status, TriagedBy } from "../api/types";

export const CATEGORY_META: Record<Category, { label: string; color: string; icon: string }> = {
  water: { label: "Water", color: "var(--cat-water)", icon: "💧" },
  electricity: { label: "Electricity", color: "var(--cat-electricity)", icon: "⚡" },
  sanitation: { label: "Sanitation", color: "var(--cat-sanitation)", icon: "♻" },
  roads: { label: "Roads", color: "var(--cat-roads)", icon: "🛣" },
  streetlights: { label: "Streetlights", color: "var(--cat-streetlights)", icon: "💡" },
  other: { label: "Other", color: "var(--cat-other)", icon: "◆" },
};

export const PRIORITY_META: Record<Priority, { label: string; color: string; icon: string }> = {
  high: { label: "High", color: "var(--danger)", icon: "▲▲" },
  normal: { label: "Normal", color: "var(--pulse)", icon: "▲" },
  low: { label: "Low", color: "var(--muted)", icon: "▽" },
};

export const STATUS_META: Record<Status, { label: string; color: string; icon: string }> = {
  open: { label: "Open", color: "var(--info)", icon: "○" },
  in_progress: { label: "In progress", color: "var(--warn)", icon: "◐" },
  resolved: { label: "Resolved", color: "var(--ok)", icon: "✓" },
  rejected: { label: "Rejected", color: "var(--danger)", icon: "✕" },
};

export function providerLabel(p: TriagedBy): string {
  return p === "rules:fallback" ? "Keyword rules (fallback)" : p === "rules" ? "Keyword rules" : p === "simulated" ? "Simulated" : `AI · ${p.split(":")[1]}`;
}

export function relativeTime(iso: string, now = Date.now()): string {
  const s = Math.round((now - Date.parse(iso)) / 1000);
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  return `${Math.round(h / 24)} d ago`;
}

export const shortId = (id: string) => id.slice(0, 8);

/** Hex twins of the category CSS variables, for the WebGL pulse (CSS vars don't reach the GPU). */
export const CATEGORY_HEX: Record<Category, string> = {
  water: "#168dd9",
  electricity: "#b68b16",
  sanitation: "#0da26b",
  roads: "#d16022",
  streetlights: "#9163d5",
  other: "#c5547c",
};
