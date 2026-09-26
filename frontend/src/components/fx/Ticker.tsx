import { useEffect, useState } from "react";

import { api } from "../../api/client";
import type { Complaint } from "../../api/types";
import { CATEGORY_META, relativeTime } from "../../lib/format";

/** "Live city feed" marquee of the latest reports. Pure CSS motion; pauses on hover/focus. */
export function Ticker() {
  const [items, setItems] = useState<Complaint[]>([]);
  useEffect(() => {
    let alive = true;
    api
      .listComplaints({ page_size: 12, sort: "-created_at" })
      .then((p) => alive && setItems(p.items))
      .catch(() => {}); // decorative: a failed feed just doesn't render
    return () => {
      alive = false;
    };
  }, []);
  if (!items.length) return null;
  const row = items.map((c) => (
    <span key={c.id} className="tick" style={{ ["--c" as string]: CATEGORY_META[c.category].color }}>
      <span className="dot" aria-hidden />
      <b>{CATEGORY_META[c.category].label}</b>
      {c.ai_summary ?? c.text}
      <em>
        {c.location} · {relativeTime(c.created_at)}
      </em>
    </span>
  ));
  return (
    <div className="ticker" aria-label="Latest reports across the city" data-reveal>
      <span className="ticker-live">
        <span className="live-dot" aria-hidden /> LIVE
      </span>
      <div className="ticker-viewport">
        <div className="ticker-track">
          {row}
          <span aria-hidden className="ticker-dup">
            {row}
          </span>
        </div>
      </div>
    </div>
  );
}
