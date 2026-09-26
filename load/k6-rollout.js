// `14-LOAD-AUTOSCALING.md §6` — zero-downtime rolling-update proof (bonus +4). Requires a real
// cluster; not runnable from this sandbox. `http_req_failed: rate==0` is deliberately ZERO, not
// a tolerance — the bonus is pass/fail, not eyeballed.
import http from "k6/http";
import { check } from "k6";

export const options = {
  scenarios: {
    steady: {
      executor: "constant-arrival-rate",
      rate: 40,
      timeUnit: "1s",
      duration: "3m",
      preAllocatedVUs: 60,
      maxVUs: 200,
    },
  },
  thresholds: {
    http_req_failed: ["rate==0"],
    "http_req_duration{expected_response:true}": ["p(99)<5000"],
  },
};

export default function () {
  const r = http.get(`${__ENV.BASE_URL}/api/stats`);
  check(r, { "200": (x) => x.status === 200 });
}
