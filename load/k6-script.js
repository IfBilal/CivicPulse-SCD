// `14-LOAD-AUTOSCALING.md §4.1` — the scale-out driver. Requires a real cluster (see
// docs/ENGINEERING-NOTES.md's "Gate 7 runbook" for the full sequence) — cannot be executed from
// this sandbox (no Docker/k3d access), written and verified for syntax only.
import http from "k6/http";
import { check } from "k6";
import { Counter } from "k6/metrics";

const created = new Counter("complaints_created");
const BASE = __ENV.BASE_URL || "http://civicpulse.localhost";

export const options = {
  scenarios: {
    rampup: {
      executor: "ramping-arrival-rate", // ARRIVAL rate, not VUs — see module docstring below
      startRate: 5,
      timeUnit: "1s",
      preAllocatedVUs: 50,
      maxVUs: 400,
      stages: [
        { target: 5, duration: "1m" }, // baseline — proves 2 replicas is enough at rest
        { target: 120, duration: "2m" }, // ramp — the interval the chart is about
        { target: 120, duration: "4m" }, // plateau — let the HPA converge and settle
        { target: 5, duration: "1m" }, // drop — proves the 300s scaleDown window
        { target: 5, duration: "6m" }, // hold — watch it NOT flap, then scale in
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<3000"],
  },
};

// `ramping-arrival-rate`, not `ramping-vus`: with VUs, a slowing system reduces offered load
// (each VU waits for its response), so the load generator quietly backs off exactly when you
// want pressure, and the replicas-vs-load chart becomes a chart of closed-loop feedback rather
// than of the HPA. Arrival-rate holds requests-per-second constant regardless of response time.

const CORPUS = JSON.parse(open("./corpus.json")); // 20 real complaints from backend/app/db/seed_data.py

export default function () {
  // Math.random() ** 2 skews toward the front of the array — a Zipf-ish repeat distribution,
  // matching "a burst main gets reported by nine neighbours" (08-AI-TRIAGE.md §2.5) and making
  // the triage-cache hit rate in §6 a realistic number rather than a uniform-random artefact.
  const body = CORPUS[Math.floor(Math.random() ** 2 * CORPUS.length)];
  const r = http.post(`${BASE}/api/complaints`, JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
  check(r, { created: (x) => x.status === 201 });
  if (r.status === 201) created.add(1);
  http.get(`${BASE}/api/stats`);
}
