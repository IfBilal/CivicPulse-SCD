"""`14-LOAD-AUTOSCALING.md §4.3` — the replicas-vs-load chart (Rubric H). Reads
docs/evidence/hpa-samples.txt (produced by the T2 sampler loop in that doc's §4.2) and the k6
summary, and renders one shared-time-axis chart with the lag annotated.

Requires real evidence files from an actual load-test run against a live cluster — cannot be
executed from this sandbox (no Docker/k3d access). Written and ready to run once those files
exist; not run here.
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

t0 = None
ts: list[int] = []
reps: list[int] = []
util: list[int] = []
for line in open("docs/evidence/hpa-samples.txt"):
    # The sampler's jsonpath queries can both return empty in the ~5-10s window right after a
    # rollout, before readyReplicas/currentMetrics populate (the same `<unknown>/60%` transition
    # HPA itself shows) — skip those rather than crash the whole chart over a startup artifact.
    fields = line.split()
    if len(fields) != 3:
        continue
    s, r, u = fields
    if not r or not u:
        continue
    t0 = t0 or int(s)
    ts.append(int(s) - t0)
    reps.append(int(r))
    util.append(int(u))

with open("docs/evidence/k6-summary.json") as f:
    k6_summary = json.load(f)

# Offered load (req/s) derived from the k6 script's own stage schedule (14-LOAD-AUTOSCALING.md
# §4.1's rampup scenario) rather than parsed from the summary, which doesn't carry a timeline —
# only aggregate metrics. This mirrors the stage boundaries exactly; if the script's stages
# change, update this list to match.
_STAGE_RATES = [(0, 5), (60, 5), (180, 120), (420, 120), (480, 5), (540, 5)]
offered = []
for t in ts:
    rate = _STAGE_RATES[0][1]
    for stage_t, stage_rate in _STAGE_RATES:
        if t >= stage_t:
            rate = stage_rate
    offered.append(rate)

fig, ax1 = plt.subplots(figsize=(11, 5))
ax1.plot(ts, offered, label="offered load (req/s)", linewidth=2, color="tab:blue")
ax1.set_xlabel("seconds since start")
ax1.set_ylabel("offered load (req/s)")

# `reps` (2-10) and `util` (observed up to ~500%, since it's averaged CPU-over-request across
# all pods, not capped at 100%) are different orders of magnitude — sharing one right axis with
# util makes the replica line invisible (confirmed: first real render of this chart, Gate 7
# capture 2026-09-27, replicas plotted flat at ~0 against a 0-500 axis). Replicas get their own
# axis; utilisation is annotated as text at its peaks instead of a third overlapping scale.
ax2 = ax1.twinx()
ax2.step(ts, reps, where="post", label="ready replicas", linewidth=2.5, linestyle="--", color="tab:red")
ax2.set_ylabel("ready replicas")
ax2.set_ylim(0, max(reps) + 1)

for i in range(1, len(util)):
    if util[i] >= 60 > util[i - 1] or (i in (0,) and util[i] >= 60):
        ax2.annotate(
            f"{util[i]}% CPU",
            xy=(ts[i], reps[i]),
            xytext=(ts[i], reps[i] + 1),
            fontsize=8,
            color="tab:orange",
            arrowprops=dict(arrowstyle="->", color="tab:orange", lw=1),
        )

fig.legend(loc="upper left", bbox_to_anchor=(0.1, 0.95))
plt.title("CivicPulse backend: offered load vs HPA replica count")
plt.tight_layout()
plt.savefig("docs/evidence/hpa-replicas-vs-load.png", dpi=150)
