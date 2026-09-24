// An in-memory stand-in for the backend. It implements a *simplified* copy of the server's rules
// so the UI can be exercised with zero network — it deliberately lives OUTSIDE `frontend/src`,
// because the app itself must never hold a business rule (CLAUDE.md HARD rule 9). The real rules
// are `backend/app/domain/transitions.py`; if they disagree, the backend wins.
import type {
  Category,
  Complaint,
  ComplaintCreate,
  ComplaintPage,
  Priority,
  Providers,
  Stats,
  Status,
  TriageOutcome,
  TriagedBy,
} from "../src/api/types";
import { buildDataset } from "./data";

const NEXT: Record<Status, Status[]> = {
  open: ["in_progress", "rejected"],
  in_progress: ["resolved", "rejected"],
  resolved: [],
  rejected: [],
};
const KEYWORDS: [Category, RegExp][] = [
  ["water", /pani|water|pipe|tanker|nal/i],
  ["electricity", /bijli|electric|transformer|voltage|meter|wire|taar/i],
  ["sanitation", /kachra|garbage|gutter|sewer|nala|drain|toilet/i],
  ["roads", /road|sarak|pothole|gadha|footpath|underpass/i],
  ["streetlights", /light|signal|andhera/i],
];

export class FakeServer {
  rows: Complaint[] = buildDataset();
  private ring: TriageOutcome[] = [];
  private statsCache: { at: number; data: Stats } | null = null;
  private submissions = 0;
  hits = 58;
  misses = 79;

  reset(): void {
    this.rows = buildDataset();
    this.ring = [];
    this.statsCache = null;
    this.submissions = 0;
  }

  create(body: ComplaintCreate, now = Date.now()): { row: Complaint; latencyMs: number } {
    this.submissions += 1;
    const slow = /\bslow\b/i.test(body.text) || this.submissions % 4 === 0; // every 4th: provider "times out"
    const category = KEYWORDS.find(([, re]) => re.test(body.text))?.[0] ?? "other";
    const priority: Priority = /khatar|danger|urgent|fire|shock|jhatka|flood/i.test(body.text) ? "high" : "normal";
    const triaged_by: TriagedBy = slow ? "rules:fallback" : "llm:groq";
    const latencyMs = slow ? 7000 : 2200;
    const ts = new Date(now).toISOString();
    const row: Complaint = {
      id: crypto.randomUUID(),
      text: body.text,
      location: body.location,
      reporter_contact: body.reporter_contact ?? null,
      category,
      priority,
      status: "open",
      ai_summary: slow ? null : body.text.slice(0, 120),
      triaged_by,
      triage_latency_ms: slow ? 10_031 : 842,
      triage_confidence: slow ? null : 0.88,
      created_at: ts,
      updated_at: ts,
    };
    this.rows.unshift(row);
    this.ring.unshift({
      complaint_id: row.id, provider: triaged_by, latency_ms: row.triage_latency_ms, fallback: slow,
      cached: false, error_class: slow ? "httpx.ReadTimeout" : null, at: ts,
    });
    this.ring = this.ring.slice(0, 20);
    this.statsCache = null; // write-invalidation
    return { row, latencyMs };
  }

  list(sp: URLSearchParams): ComplaintPage {
    const cats = sp.getAll("category"), pris = sp.getAll("priority"), sts = sp.getAll("status");
    const page = Math.max(1, Number(sp.get("page") ?? 1));
    const pageSize = Number(sp.get("page_size") ?? 20);
    const sort = sp.get("sort") ?? "-created_at";
    const rank: Record<Priority, number> = { high: 0, normal: 1, low: 2 };
    const filtered = this.rows
      .filter((r) => (!cats.length || cats.includes(r.category)) && (!pris.length || pris.includes(r.priority)) && (!sts.length || sts.includes(r.status)))
      .sort((a, b) => {
        const key = sort.replace("-", "");
        const d = key === "priority" ? rank[b.priority] - rank[a.priority] : a.created_at.localeCompare(b.created_at);
        return sort.startsWith("-") ? -d : d;
      });
    const filters_applied: Record<string, string[]> = {};
    if (cats.length) filters_applied.category = cats;
    if (pris.length) filters_applied.priority = pris;
    if (sts.length) filters_applied.status = sts;
    return {
      items: filtered.slice((page - 1) * pageSize, page * pageSize),
      total: filtered.length,
      page,
      page_size: pageSize,
      pages: Math.max(1, Math.ceil(filtered.length / pageSize)),
      filters_applied,
    };
  }

  get(id: string): Complaint | undefined {
    return this.rows.find((r) => r.id === id);
  }

  transition(id: string, to: Status): { ok: Complaint } | { conflict: { from: Status; allowed: Status[] } } | null {
    const row = this.get(id);
    if (!row) return null;
    const allowed = NEXT[row.status];
    if (!allowed.includes(to)) return { conflict: { from: row.status, allowed } };
    row.status = to;
    row.updated_at = new Date().toISOString();
    this.statsCache = null;
    return { ok: row };
  }

  stats(now = Date.now()): { data: Stats; cache: "HIT" | "MISS" } {
    if (this.statsCache && now - this.statsCache.at < 30_000) {
      this.hits += 1;
      return { data: { ...this.statsCache.data, cache_age_seconds: Math.floor((now - this.statsCache.at) / 1000) }, cache: "HIT" };
    }
    this.misses += 1;
    const count = <K extends string>(keys: K[], pick: (c: Complaint) => K) =>
      Object.fromEntries(keys.map((k) => [k, this.rows.filter((r) => pick(r) === k).length])) as Record<K, number>;
    const data: Stats = {
      total: this.rows.length,
      by_category: count<Category>(["water", "electricity", "sanitation", "roads", "streetlights", "other"], (c) => c.category),
      by_priority: count<Priority>(["high", "normal", "low"], (c) => c.priority),
      by_status: count<Status>(["open", "in_progress", "resolved", "rejected"], (c) => c.status),
      generated_at: new Date(now).toISOString(),
      cache_age_seconds: 0,
    };
    this.statsCache = { at: now, data };
    return { data, cache: "MISS" };
  }

  providers(): Providers {
    const recent = this.ring.length ? this.ring : this.rows.slice(0, 12).map<TriageOutcome>((r, i) => ({
      complaint_id: r.id, provider: r.triaged_by, latency_ms: r.triage_latency_ms,
      fallback: r.triaged_by === "rules:fallback", cached: i % 5 === 2,
      error_class: r.triaged_by === "rules:fallback" ? "httpx.ReadTimeout" : null, at: r.created_at,
    }));
    const total = this.hits + this.misses;
    return {
      active: "llm:groq", configured: "llm", available: ["llm", "ollama", "rules", "simulated"],
      cache: { hits: this.hits, misses: this.misses, hit_rate: total ? Math.round((this.hits / total) * 1000) / 1000 : 0 },
      recent,
    };
  }
}
