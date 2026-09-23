import gsap from "gsap";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { runtimeConfig } from "../api/config";
import { api, ApiError } from "../api/client";
import { CATEGORIES, PRIORITIES, STATUSES } from "../api/schemaMeta";
import type { CacheState, Providers, Stats as StatsT } from "../api/types";
import { CacheBadge, ProviderBadge } from "../components/Badges";
import { CountUp } from "../components/CountUp";
import { DecodeText } from "../components/DecodeText";
import { Glass } from "../components/Glass";
import { prefersReducedMotion, useReveal } from "../hooks/motion";
import { CATEGORY_META, PRIORITY_META, relativeTime, shortId, STATUS_META } from "../lib/format";

interface Row {
  key: string;
  label: string;
  icon: string;
  color: string;
  value: number;
}

/** Horizontal bars: one hue per entity (identity), direct-labelled with name + value, so colour
 *  is never the only channel. Hover/focus shows the share tooltip; a table view is one click away. */
function BarChart({ title, rows, total }: { title: string; rows: Row[]; total: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [asTable, setAsTable] = useState(false);
  const max = Math.max(1, ...rows.map((r) => r.value));

  useLayoutEffect(() => {
    if (!ref.current || asTable || prefersReducedMotion()) return;
    const ctx = gsap.context(() => {
      gsap.from(".bar-fill", { scaleX: 0, transformOrigin: "left center", duration: 1.1, ease: "expo.out", stagger: 0.07 });
    }, ref);
    return () => ctx.revert();
  }, [rows, asTable]);

  return (
    <Glass>
      <div className="row" style={{ marginBottom: 14 }}>
        <h2 className="card-title" style={{ margin: 0 }}>
          {title}
        </h2>
        <span className="spacer" />
        <button className="btn btn-sm btn-ghost" onClick={() => setAsTable((t) => !t)} aria-pressed={asTable}>
          {asTable ? "Chart" : "Table"}
        </button>
      </div>
      {asTable ? (
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{title.replace("By ", "")}</th>
              <th scope="col">Count</th>
              <th scope="col">Share</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <th scope="row">{r.label}</th>
                <td className="mono">{r.value}</td>
                <td className="mono">{total ? Math.round((r.value / total) * 100) : 0}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div ref={ref} className="bars" role="list">
          {rows.map((r) => {
            const share = total ? Math.round((r.value / total) * 100) : 0;
            return (
              <div key={r.key} className="bar-row" role="listitem" tabIndex={0} aria-label={`${r.label}: ${r.value} (${share}%)`}>
                <span className="bar-label">
                  <span aria-hidden className="bar-icon">
                    {r.icon}
                  </span>
                  {r.label}
                </span>
                <span className="bar-track">
                  <span className="bar-fill" style={{ width: `${(r.value / max) * 100}%`, ["--c" as string]: r.color }} />
                  <span className="bar-tip" role="tooltip">
                    {r.label} · {r.value} · {share}%
                  </span>
                </span>
                <span className="bar-value mono">{r.value}</span>
              </div>
            );
          })}
        </div>
      )}
    </Glass>
  );
}

export default function Stats() {
  const cfg = runtimeConfig();
  const [stats, setStats] = useState<StatsT | null>(null);
  const [cache, setCache] = useState<CacheState | null>(null);
  const [providers, setProviders] = useState<Providers | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [cycle, setCycle] = useState(0);
  const scope = useReveal<HTMLDivElement>([stats === null]);

  // Only setState AFTER an await, so the polling effect never renders synchronously.
  const refresh = useCallback(async () => {
    try {
      const [s, p] = await Promise.all([api.getStats(), api.getProviders().catch(() => null)]);
      setStats(s.data);
      setCache(s.cache);
      setProviders(p);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.body.error.message : "Could not load statistics.");
    } finally {
      setCycle((c) => c + 1);
    }
  }, []);

  const refreshNow = () => {
    setRefreshing(true);
    void refresh().finally(() => setRefreshing(false));
  };

  useEffect(() => {
    const first = window.setTimeout(() => void refresh(), 0);
    const id = window.setInterval(() => void refresh(), cfg.statsPollMs);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [refresh, cfg.statsPollMs]);

  if (error && !stats) {
    return (
      <div className="banner error" role="alert" style={{ marginTop: 40 }}>
        <span aria-hidden>⚠</span>
        <span>{error}</span>
        <button className="btn btn-sm" style={{ marginLeft: "auto" }} onClick={refreshNow}>
          Retry
        </button>
      </div>
    );
  }

  const total = stats?.total ?? 0;
  const cats: Row[] = CATEGORIES.map((c) => ({ key: c, ...CATEGORY_META[c], value: stats?.by_category[c] ?? 0 }));
  const pris: Row[] = PRIORITIES.map((p) => ({ key: p, ...PRIORITY_META[p], value: stats?.by_priority[p] ?? 0 }));
  const sts: Row[] = STATUSES.map((s) => ({ key: s, ...STATUS_META[s], value: stats?.by_status?.[s] ?? 0 }));
  const open = stats?.by_status?.open ?? 0;
  const resolved = stats?.by_status?.resolved ?? 0;
  const high = stats?.by_priority.high ?? 0;

  return (
    <div ref={scope}>
      <header className="page-head row" data-reveal style={{ alignItems: "flex-end" }}>
        <div>
          <p className="eyebrow">City pulse</p>
          <h1 className="page-title">
            <DecodeText className="grad" text="Live statistics" />
          </h1>
          <p className="page-sub">Aggregates from the server&apos;s 30-second cache. Refreshes every {Math.round(cfg.statsPollMs / 1000)} s.</p>
        </div>
        <span className="spacer" />
        <div className="row">
          {cfg.showCacheBadge && cache && <CacheBadge cache={cache} ageSeconds={stats?.cache_age_seconds} />}
          <button className="btn btn-sm" onClick={refreshNow} disabled={refreshing} aria-label="Refresh now">
            <span aria-hidden className={refreshing ? "spin" : ""}>
              ⟳
            </span>
            Refresh
          </button>
          <span key={cycle} className="poll-ring" style={{ ["--d" as string]: `${cfg.statsPollMs}ms` }} aria-hidden />
        </div>
      </header>

      {!stats ? (
        <div className="grid-3">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="skeleton" style={{ height: 130 }} />
          ))}
        </div>
      ) : (
        <>
          <div className="kpis">
            <Glass className="kpi hero">
              <span className="kpi-label">Total reports</span>
              <span className="kpi-value">
                <CountUp value={total} />
              </span>
              <span className="kpi-foot">generated {relativeTime(stats.generated_at)}</span>
            </Glass>
            <Glass className="kpi">
              <span className="kpi-label">Open now</span>
              <span className="kpi-value" style={{ color: "var(--info)" }}>
                <CountUp value={open} />
              </span>
              <span className="kpi-foot">awaiting action</span>
            </Glass>
            <Glass className="kpi">
              <span className="kpi-label">High priority</span>
              <span className="kpi-value" style={{ color: "var(--danger)" }}>
                <CountUp value={high} />
              </span>
              <span className="kpi-foot">{total ? Math.round((high / total) * 100) : 0}% of all reports</span>
            </Glass>
            <Glass className="kpi">
              <span className="kpi-label">Resolution rate</span>
              <span className="kpi-value" style={{ color: "var(--ok)" }}>
                <CountUp value={total ? (resolved / total) * 100 : 0} decimals={0} suffix="%" />
              </span>
              <span className="kpi-foot">{resolved} resolved</span>
            </Glass>
          </div>

          <div className="grid-2" style={{ marginTop: 22 }}>
            <BarChart title="By category" rows={cats} total={total} />
            <div className="stack">
              <BarChart title="By priority" rows={pris} total={total} />
              <BarChart title="By status" rows={sts} total={total} />
            </div>
          </div>

          {providers && (
            <Glass style={{ marginTop: 22 }} aria-label="Triage telemetry">
              <div className="row" style={{ marginBottom: 16 }}>
                <div>
                  <h2 className="card-title">Triage engine</h2>
                  <p className="card-sub" style={{ margin: 0 }}>
                    Last {providers.recent.length} classifications · the observability surface
                  </p>
                </div>
                <span className="spacer" />
                <ProviderBadge provider={providers.active} />
                <span className="chip">
                  cache hit rate <b className="mono" style={{ color: "var(--ok)" }}>{Math.round(providers.cache.hit_rate * 100)}%</b>
                </span>
              </div>
              <ul className="telemetry">
                {providers.recent.map((r) => {
                  const pct = Math.min(100, (r.latency_ms / 12000) * 100);
                  return (
                    <li key={`${r.complaint_id}-${r.at}`} className={r.fallback ? "fallback" : ""}>
                      <span className="mono">#{shortId(r.complaint_id)}</span>
                      <span className="mono tele-provider">{r.provider}</span>
                      <span className="tele-bar" aria-hidden>
                        <span style={{ width: `${pct}%` }} />
                      </span>
                      <span className="mono">{r.latency_ms} ms</span>
                      <span className="tele-flag">{r.fallback ? `⚠ fallback · ${r.error_class ?? "error"}` : r.cached ? "⚡ cached" : "✓ ok"}</span>
                    </li>
                  );
                })}
              </ul>
            </Glass>
          )}
        </>
      )}
    </div>
  );
}
