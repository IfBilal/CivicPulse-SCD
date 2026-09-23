import gsap from "gsap";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { CATEGORIES, LIMITS, PRIORITIES, STATUSES } from "../api/schemaMeta";
import type { Category, Complaint, ComplaintPage, ListQuery, Priority, Status } from "../api/types";
import { CategoryChip, PriorityTag, ProviderBadge, StatusPill } from "../components/Badges";
import { CountUp } from "../components/CountUp";
import { DecodeText } from "../components/DecodeText";
import { Glass } from "../components/Glass";
import { prefersReducedMotion, useReveal } from "../hooks/motion";
import { CATEGORY_META, PRIORITY_META, relativeTime, shortId, STATUS_META } from "../lib/format";

const PAGE_SIZES = [10, 20, 50, 100].filter((n) => n <= LIMITS.pageSizeMax);
const SORTS = [
  { value: "-created_at", label: "Newest first" },
  { value: "created_at", label: "Oldest first" },
  { value: "-priority", label: "Highest priority" },
  { value: "priority", label: "Lowest priority" },
] as const;

type Banner = { kind: "conflict" | "error" | "success"; text: string } | null;

function readQuery(sp: URLSearchParams): ListQuery {
  const q: ListQuery = {
    page: Math.max(1, Number(sp.get("page")) || 1),
    page_size: Math.min(LIMITS.pageSizeMax, Number(sp.get("page_size")) || 20),
    sort: (sp.get("sort") as ListQuery["sort"]) ?? "-created_at",
  };
  const cat = sp.getAll("category") as Category[];
  const pri = sp.getAll("priority") as Priority[];
  const st = sp.getAll("status") as Status[];
  if (cat.length) q.category = cat;
  if (pri.length) q.priority = pri;
  if (st.length) q.status = st;
  return q;
}

export default function Dashboard() {
  const [sp, setSp] = useSearchParams();
  const query = readQuery(sp);
  const key = sp.toString();
  const [page, setPage] = useState<ComplaintPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [banner, setBanner] = useState<Banner>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  // Learned from the server's own 409 (`details.terminal`) — never assumed locally.
  const [terminal, setTerminal] = useState<Record<string, string>>({});
  const listRef = useRef<HTMLUListElement>(null);
  const scope = useReveal<HTMLDivElement>();

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setPage(await api.listComplaints(readQuery(new URLSearchParams(key))));
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.body.error.message : "Could not load complaints.");
    } finally {
      setLoading(false);
    }
  }, [key]);

  useEffect(() => {
    void load();
  }, [load]);

  useLayoutEffect(() => {
    if (!page || !listRef.current || prefersReducedMotion()) return;
    const ctx = gsap.context(() => {
      gsap.from("li.complaint", { opacity: 0, y: 18, duration: 0.5, ease: "power3.out", stagger: 0.035 });
    }, listRef);
    return () => ctx.revert();
  }, [page]);

  function update(mutator: (next: URLSearchParams) => void, resetPage = true) {
    const next = new URLSearchParams(sp);
    mutator(next);
    if (resetPage) next.delete("page");
    setSp(next);
  }

  function toggle(name: "category" | "priority" | "status", value: string) {
    update((next) => {
      const cur = next.getAll(name);
      next.delete(name);
      (cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value]).forEach((v) => next.append(name, v));
    });
  }

  async function transition(c: Complaint, to: Status) {
    setPending(`${c.id}:${to}`);
    setBanner(null);
    try {
      const updated = await api.updateStatus(c.id, { status: to });
      setPage((p) => p && { ...p, items: p.items.map((i) => (i.id === updated.id ? updated : i)) });
      setBanner({ kind: "success", text: `#${shortId(c.id)} is now ${STATUS_META[updated.status].label.toLowerCase()}.` });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setBanner({ kind: "conflict", text: e.body.error.message }); // ← verbatim, never a mapped string
        const d = e.body.error.details as { terminal?: boolean; from?: Status } | undefined;
        if (d?.terminal) setTerminal((t) => ({ ...t, [c.id]: e.body.error.message }));
        if (d?.from && d.from !== c.status) {
          setPage((p) => p && { ...p, items: p.items.map((i) => (i.id === c.id ? { ...i, status: d.from! } : i)) });
        }
      } else {
        setBanner({ kind: "error", text: e instanceof ApiError ? e.body.error.message : "Update failed." });
      }
    } finally {
      setPending(null);
    }
  }

  const activeFilters = (query.category?.length ?? 0) + (query.priority?.length ?? 0) + (query.status?.length ?? 0);
  const from = page && page.total ? (page.page - 1) * page.page_size + 1 : 0;
  const to = page ? Math.min(page.total, page.page * page.page_size) : 0;

  return (
    <div ref={scope}>
      <header className="page-head" data-reveal>
        <p className="eyebrow">Operator console</p>
        <h1 className="page-title">
          <DecodeText className="grad" text="Dashboard" />
        </h1>
        <p className="page-sub">Every report, triaged. Filter, sort and move complaints through their lifecycle — the server decides what&apos;s allowed.</p>
      </header>

      <Glass className="filters" aria-label="Filters">
        <div className="filter-group">
          <span className="filter-label">Category</span>
          <div className="row">
            {CATEGORIES.map((c) => (
              <button key={c} type="button" className="chip chip-toggle" style={{ ["--c" as string]: CATEGORY_META[c].color }} aria-pressed={!!query.category?.includes(c)} onClick={() => toggle("category", c)}>
                <span className="dot" aria-hidden />
                {CATEGORY_META[c].label}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-group">
          <span className="filter-label">Priority</span>
          <div className="row">
            {PRIORITIES.map((p) => (
              <button key={p} type="button" className="chip chip-toggle" style={{ ["--c" as string]: PRIORITY_META[p].color }} aria-pressed={!!query.priority?.includes(p)} onClick={() => toggle("priority", p)}>
                {PRIORITY_META[p].label}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-group">
          <span className="filter-label">Status</span>
          <div className="row">
            {STATUSES.map((s) => (
              <button key={s} type="button" className="chip chip-toggle" style={{ ["--c" as string]: STATUS_META[s].color }} aria-pressed={!!query.status?.includes(s)} onClick={() => toggle("status", s)}>
                <span aria-hidden>{STATUS_META[s].icon}</span>
                {STATUS_META[s].label}
              </button>
            ))}
          </div>
        </div>
        <div className="row filter-foot">
          <label className="inline-select">
            Sort
            <select className="select" value={query.sort} onChange={(e) => update((n) => n.set("sort", e.target.value))}>
              {SORTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <label className="inline-select">
            Per page
            <select className="select" value={query.page_size} onChange={(e) => update((n) => n.set("page_size", e.target.value))}>
              {PAGE_SIZES.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <span className="spacer" />
          {activeFilters > 0 && (
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setSp(new URLSearchParams())}>
              Clear {activeFilters} filter{activeFilters > 1 ? "s" : ""} ✕
            </button>
          )}
          <span className="total-pill" aria-live="polite">
            {page ? <CountUp value={page.total} /> : "—"} matching
          </span>
        </div>
      </Glass>

      <div style={{ height: 18 }} />

      {banner && (
        <div className={`banner ${banner.kind}`} role={banner.kind === "success" ? "status" : "alert"}>
          <span aria-hidden>{banner.kind === "success" ? "✓" : banner.kind === "conflict" ? "⛔" : "⚠"}</span>
          <span>{banner.text}</span>
          <button className="x" aria-label="Dismiss" onClick={() => setBanner(null)}>
            ×
          </button>
        </div>
      )}

      {loadError ? (
        <div className="banner error" role="alert">
          <span aria-hidden>⚠</span>
          <span>{loadError}</span>
          <button className="btn btn-sm" style={{ marginLeft: "auto" }} onClick={() => void load()}>
            Retry
          </button>
        </div>
      ) : loading && !page ? (
        <ul className="complaints" aria-busy="true" aria-label="Loading complaints">
          {Array.from({ length: 6 }, (_, i) => (
            <li key={i} className="skeleton" style={{ height: 96 }} />
          ))}
        </ul>
      ) : page && page.items.length === 0 ? (
        <Glass className="empty">
          <p className="eyebrow">No signal</p>
          <h2 className="card-title">No complaints match these filters.</h2>
          <button className="btn btn-sm" onClick={() => setSp(new URLSearchParams())}>
            Clear filters
          </button>
        </Glass>
      ) : (
        page && (
          <ul className={`complaints ${loading ? "is-loading" : ""}`} ref={listRef} aria-busy={loading}>
            {page.items.map((c) => {
              const open = expanded === c.id;
              const lockedMsg = terminal[c.id];
              return (
                <li key={c.id} className={`complaint glass ${open ? "open" : ""}`} style={{ ["--c" as string]: CATEGORY_META[c.category].color }}>
                  <button className="complaint-head" aria-expanded={open} aria-controls={`c-${c.id}`} onClick={() => setExpanded(open ? null : c.id)}>
                    <span className="cat-rail" aria-hidden />
                    <span className="complaint-main">
                      <span className="complaint-title">{c.ai_summary ?? c.text}</span>
                      <span className="complaint-meta">
                        <span className="mono">#{shortId(c.id)}</span> · {c.location} · {relativeTime(c.created_at)}
                      </span>
                    </span>
                    <span className="complaint-tags">
                      <CategoryChip category={c.category} />
                      <PriorityTag priority={c.priority} />
                      <StatusPill status={c.status} />
                    </span>
                    <span className="chev" aria-hidden>
                      ⌄
                    </span>
                  </button>
                  {open && (
                    <div className="complaint-body" id={`c-${c.id}`}>
                      <blockquote>{c.text}</blockquote>
                      <div className="row" style={{ marginBottom: 14 }}>
                        <ProviderBadge provider={c.triaged_by} />
                        <span className="hint mono">{c.triage_latency_ms} ms</span>
                        {c.reporter_contact && <span className="hint">contact on file</span>}
                      </div>
                      <div className="row transitions" role="group" aria-label="Move to status">
                        {STATUSES.filter((s) => s !== c.status).map((s) => (
                          <button
                            key={s}
                            className="btn btn-sm"
                            style={{ ["--b" as string]: STATUS_META[s].color }}
                            disabled={!!lockedMsg || pending !== null}
                            aria-disabled={!!lockedMsg || pending !== null}
                            title={lockedMsg ?? `Move to ${STATUS_META[s].label}`}
                            onClick={() => void transition(c, s)}
                          >
                            {pending === `${c.id}:${s}` ? <span className="spinner" aria-hidden /> : <span aria-hidden>{STATUS_META[s].icon}</span>}
                            {STATUS_META[s].label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )
      )}

      {page && page.total > 0 && (
        <nav className="pager" aria-label="Pagination">
          <span className="hint">
            Showing {from}–{to} of {page.total}
          </span>
          <span className="spacer" />
          <button className="btn btn-sm" disabled={page.page <= 1} onClick={() => update((n) => n.set("page", String(page.page - 1)), false)}>
            ← Prev
          </button>
          {Array.from({ length: page.pages }, (_, i) => i + 1)
            .filter((n) => n === 1 || n === page.pages || Math.abs(n - page.page) <= 1)
            .map((n, i, arr) => (
              <span key={n} className="row" style={{ gap: 6 }}>
                {i > 0 && n - arr[i - 1]! > 1 && <span className="hint">…</span>}
                <button className={`btn btn-sm ${n === page.page ? "current" : ""}`} aria-current={n === page.page ? "page" : undefined} onClick={() => update((q) => q.set("page", String(n)), false)}>
                  {n}
                </button>
              </span>
            ))}
          <button className="btn btn-sm" disabled={page.page >= page.pages} onClick={() => update((n) => n.set("page", String(page.page + 1)), false)}>
            Next →
          </button>
        </nav>
      )}
    </div>
  );
}
