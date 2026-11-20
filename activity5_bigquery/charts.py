"""Activity 5 - charts from the BigQuery result CSVs (results/*.csv) + architecture diagram."""
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import chartstyle as cs  # noqa: E402

HERE = Path(__file__).parent
RES, OUT = HERE / "results", HERE / "charts"
OUT.mkdir(exist_ok=True)
cs.apply()
NOTE = "Synthetic logs (seed 55). BigQuery Sandbox, project bigdatasla, run 2026-11-03 - source: {}"
SPIKE = "#f6c9c9"
rd = lambda n, **k: pd.read_csv(RES / f"{n}.csv", **k)

# 1. hourly volume and 5xx (two panels, one measure each) ------------------------------------------
h = rd("q05_hourly_volume", parse_dates=["hour_ist"])
sp = rd("q11_failure_spikes", parse_dates=["spike_start_ist", "spike_end_ist"])
pk = rd("q08_peak_5min_windows", parse_dates=["window_start_ist"])
fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 5.2), sharex=True, gridspec_kw={"height_ratios": [2, 1.2]})
a1.plot(h.hour_ist, h.requests, color=cs.BLUE, lw=1.6)
top = pk.iloc[0]
a1.annotate(f"busiest 5 min: {top.window_start_ist:%a %d %H:%M} ({top.requests:,} req, {top.requests_per_second} req/s)",
            (top.window_start_ist, h.requests.max()), xytext=(-330, -8), textcoords="offset points", fontsize=8.5,
            arrowprops=dict(arrowstyle="-", color=cs.MUTED))
a1.set_ylabel("requests / hour"); a1.set_title("Request volume over time (IST)", fontsize=11)
for r in sp.itertuples():
    a2.axvspan(r.spike_start_ist, r.spike_end_ist, color=SPIKE, lw=0)
a2.bar(h.hour_ist, h.errors_5xx, width=0.035, color=cs.CRITICAL)
a2.set_ylabel("5xx / hour"); a2.set_title("Server errors per hour (shaded: spikes detected by Q11)", fontsize=10)
a2.xaxis.set_major_locator(mdates.DayLocator()); a2.xaxis.set_major_formatter(mdates.DateFormatter("%a %d %b"))
for ax in (a1, a2):
    ax.grid(axis="x", visible=False)
cs.save(fig, OUT / "a5_hourly_volume.png", NOTE.format("q05_hourly_volume, q08_peak_5min_windows, q11_failure_spikes"))

# 2. status codes ----------------------------------------------------------------------------------------
s = rd("q02_status_codes").sort_values("requests")
cls_col = {"2xx": cs.BLUE, "3xx": cs.AQUA, "4xx": cs.YELLOW, "5xx": cs.CRITICAL}
fig, ax = plt.subplots(figsize=(8.5, 4.2))
ax.barh(s.status.astype(str), s.requests, color=[cls_col[c] for c in s.status_class], height=0.6)
for i, (n, p) in enumerate(zip(s.requests, s.pct_of_all)):
    ax.text(n * 1.08, i, f"{n:,}  ({p:.3g} %)", va="center", fontsize=8.5)
ax.set_xscale("log"); ax.set_xlim(1, s.requests.max() * 30); ax.set_xlabel("requests (log scale)")
ax.legend(handles=[Patch(color=v, label=k) for k, v in cls_col.items()], loc="lower right", fontsize=8.5)
ax.set_title("HTTP status code distribution"); ax.grid(axis="y", visible=False)
cs.save(fig, OUT / "a5_status_codes.png", NOTE.format("q02_status_codes"))

# 3. top endpoints ---------------------------------------------------------------------------------------
e = rd("q03_top_endpoints").head(15).iloc[::-1]
fig, ax = plt.subplots(figsize=(9, 5))
ax.barh(e.endpoint, e.requests, color=cs.BLUE, height=0.6)
for i, r in enumerate(e.itertuples()):
    ax.text(r.requests, i, f"  {r.requests:,}  p95 {r.p95_ms} ms", va="center", fontsize=8)
ax.set_xlim(0, e.requests.max() * 1.4); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", labelsize=8.5)
ax.set_xlabel("requests (7 days)"); ax.set_title("Most frequently accessed endpoints (top 15)")
cs.save(fig, OUT / "a5_top_endpoints.png", NOTE.format("q03_top_endpoints"))

# 4. weekday x hour heatmap ------------------------------------------------------------------------------
p = rd("q07_hour_of_day_profile").pivot(index="weekday", columns="hour_of_day", values="requests")
cmap = LinearSegmentedColormap.from_list("seq", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
fig, ax = plt.subplots(figsize=(11, 3.6))
im = ax.imshow(p.values, aspect="auto", cmap=cmap)
ax.set_yticks(range(len(p)), [w[2:] for w in p.index]); ax.set_xticks(range(24), [f"{x:02d}" for x in range(24)], fontsize=8)
for i in range(p.shape[0]):
    for j in range(p.shape[1]):
        v = p.values[i, j]; ax.text(j, i, f"{v / 1000:.1f}k", ha="center", va="center", fontsize=6.5,
                                    color="white" if v > p.values.max() * 0.55 else cs.TEXT)
ax.grid(False); ax.set_xlabel("hour of day (IST)")
cb = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01); cb.set_label("requests")
ax.set_title("Peak usage periods: requests per weekday and hour")
cs.save(fig, OUT / "a5_weekday_hour_heatmap.png", NOTE.format("q07_hour_of_day_profile (Fri 20-22 h = sale campaign; Thu 02 h = credential stuffing; Sat = scraper)"))

# 5. 5-minute failures with detected spikes ---------------------------------------------------------------
f = rd("q10_5min_failures_series", parse_dates=["bucket_ist"])
fig, ax = plt.subplots(figsize=(11, 3.6))
for r in sp.itertuples():
    ax.axvspan(r.spike_start_ist, r.spike_end_ist, color=SPIKE, lw=0)
    ax.text(r.spike_start_ist, f.failures.max() * (0.98 - 0.09 * (r.incident_no % 2 == 0)), f" #{r.incident_no}", fontsize=8, va="top")
ax.plot(f.bucket_ist, f.failures, color=cs.TEXT2, lw=0.7)
ax.set_ylabel("5xx per 5 minutes"); ax.grid(axis="x", visible=False)
ax.xaxis.set_major_locator(mdates.DayLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d %b"))
ax.set_title("Failed requests per 5 minutes; shaded = spikes flagged by Q11 (#2 is a false positive)")
cs.save(fig, OUT / "a5_failure_spikes.png", NOTE.format("q10_5min_failures_series, q11_failure_spikes"))

# 6. top IPs, suspicious highlighted ---------------------------------------------------------------------------
ips = rd("q09_top_ips").iloc[::-1]
sus = set(rd("q12_suspicious_bruteforce").client_ip) | set(rd("q13_suspicious_scanners").client_ip) | set(rd("q14_suspicious_high_rate").client_ip)
fig, ax = plt.subplots(figsize=(9, 5.4))
ax.barh(ips.client_ip, ips.requests, color=[cs.ORANGE if i in sus else cs.BLUE for i in ips.client_ip], height=0.65)
for k, r in enumerate(ips.itertuples()):
    ax.text(r.requests, k, f"  {r.requests:,}  {r.ua_class}, max {r.max_requests_per_minute}/min", va="center", fontsize=7.5)
ax.set_xscale("log"); ax.set_xlim(100, ips.requests.max() * 40); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", labelsize=8)
ax.legend(handles=[Patch(color=cs.ORANGE, label="flagged by Q12/Q13/Q14"), Patch(color=cs.BLUE, label="not flagged")],
          loc="lower right", fontsize=8.5)
ax.set_xlabel("requests (log scale)"); ax.set_title("IP-wise request patterns: 20 most active clients")
cs.save(fig, OUT / "a5_top_ips.png", NOTE.format("q09_top_ips, q12-q14"))

# 7. suspicious findings summary -------------------------------------------------------------------------------
b, sc, hr = rd("q12_suspicious_bruteforce"), rd("q13_suspicious_scanners"), rd("q14_suspicious_high_rate")
scr = hr[~hr.client_ip.isin(b.client_ip)]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.4))
a1.bar(b.client_ip, b.failed_logins, color=cs.ORANGE, width=0.5, label="401 failed")
a1.bar(b.client_ip, b.successful_logins, bottom=b.failed_logins, color=cs.CRITICAL, width=0.5, label="200 succeeded")
for x, (fl, ok) in enumerate(zip(b.failed_logins, b.successful_logins)):
    a1.text(x, fl + ok, f"{ok} succeeded", ha="center", va="bottom", fontsize=8)
a1.set_title("Q12 credential stuffing: POST /login in one hour", fontsize=10); a1.legend(fontsize=8, loc="lower right")
a1.tick_params(axis="x", labelsize=8)
lab = [f"{r.client_ip}\n(scraper)" for r in scr.itertuples()] + [f"{r.client_ip}\n(scanner)" for r in sc.itertuples()]
ok_ = list(scr.requests - scr.rate_limited_429) + list(sc.probe_requests * (1 - sc.pct_4xx_5xx / 100))
blk = list(scr.rate_limited_429) + list(sc.probe_requests * sc.pct_4xx_5xx / 100)
a2.bar(lab, ok_, color=cs.BLUE, width=0.45, label="served (2xx/3xx/404 on products)")
a2.bar(lab, blk, bottom=ok_, color=cs.YELLOW, width=0.45, label="blocked / failed (429, 4xx)")
for x, (o, k) in enumerate(zip(ok_, blk)):
    a2.text(x, o + k, f"{int(o + k):,}", ha="center", va="bottom", fontsize=8.5)
a2.set_title("Q13/Q14 scanner and scraper", fontsize=10); a2.legend(fontsize=7.5, loc="upper right"); a2.set_ylim(0, max(o + k for o, k in zip(ok_, blk)) * 1.25)
for ax in (a1, a2):
    ax.grid(axis="x", visible=False)
cs.save(fig, OUT / "a5_suspicious_traffic.png", NOTE.format("q12_suspicious_bruteforce, q13_suspicious_scanners, q14_suspicious_high_rate"))

# 8. partition pruning / bytes billed --------------------------------------------------------------------------
pr = rd("pruning_comparison").iloc[::-1]
short = {"p1_full_table_1col": "P1 full table, 1 column", "p2_one_utc_day": "P2 one UTC day",
         "p3_one_ist_day": "P3 one IST day", "p4_full_table_wide_col": "P4 + user_agent column",
         "p5_ist_day_plus_cluster": "P5 IST day + endpoint"}
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.barh([short[q] for q in pr["query"]], pr.bytes_processed / 2**20, color=cs.BLUE, height=0.55)
ax.axvline(10, color=cs.CRITICAL, ls="--", lw=1)
ax.text(10.5, -0.75, "10 MiB minimum billed", fontsize=8, color=cs.TEXT)
for i, r in enumerate(pr.itertuples()):
    why = {"p1_full_table_1col": "status column, all 7 partitions", "p2_one_utc_day": "1 partition",
           "p3_one_ist_day": "IST day spans 2 UTC partitions", "p4_full_table_wide_col": "columnar: long column read",
           "p5_ist_day_plus_cluster": "endpoint column also read"}[r.query]
    ax.text(r.bytes_processed / 2**20 * 1.08, i, f"{r.bytes_processed / 2**20:.2f} MiB  ({why})", va="center", fontsize=7.5)
ax.set_xscale("log"); ax.set_xlim(1, 3000); ax.set_ylim(-1, len(pr) - 0.4)
ax.set_xlabel("MiB processed (log scale)"); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", labelsize=8.5)
ax.set_title("Bytes scanned (= billed above 10 MiB): partitions, columns, clustering")
cs.save(fig, OUT / "a5_pruning_bytes.png", NOTE.format("pruning_comparison.csv (job statistics)"))

# 9. hypothetical production cost --------------------------------------------------------------------------------
c = rd("cost_estimate_production")
c = c[c.usd_per_month > 0].sort_values("usd_per_month")
fig, ax = plt.subplots(figsize=(9, 3.2))
ax.barh(c["item"], c.usd_per_month, color=cs.MUTED, height=0.55)
for i, r in enumerate(c.itertuples()):
    ax.text(r.usd_per_month, i, f"  USD {r.usd_per_month:,.2f}  ({r.quantity})", va="center", fontsize=8.5)
ax.set_xlim(0, c.usd_per_month.max() * 1.45); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", labelsize=8.5)
ax.set_xlabel("USD per month")
ax.set_title(f"HYPOTHETICAL estimate, 20 GiB logs/day: ~USD {c.usd_per_month.sum():,.0f}/month (not deployed)")
cs.save(fig, OUT / "a5_cost_hypothetical.png", "Prices: Cloud Billing Catalog API (asia-south1), retrieved 2026-11-03. Assumptions: results/cost_assumptions.csv")

# 10. architecture: used vs proposed ---------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 5.4)); ax.set_xlim(0, 12); ax.set_ylim(0, 6); ax.axis("off")


def box(x, y, w, h, text, used):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.08",
                                fc="#e8f1fc" if used else "#f4f4f2", ec=cs.BLUE if used else cs.MUTED,
                                lw=1.6 if used else 1.2, ls="-" if used else "--"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.5, color=cs.TEXT, wrap=True)


def arrow(x1, y1, x2, y2, used):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12, lw=1.3,
                                 color=cs.BLUE if used else cs.MUTED, ls="-" if used else "--"))


ax.text(0.1, 5.7, "USED in this prototype (solid)", fontsize=10, fontweight="bold", color=cs.BLUE)
box(0.1, 4.2, 1.9, 1.0, "generate_logs.py\nsynthetic Apache logs\n(local, 7 days)", True)
box(2.4, 4.2, 1.9, 1.0, "parse_logs.py\nregex ETL -> typed\nCSV.gz (local)", True)
box(4.7, 4.2, 2.1, 1.0, "bq load\nbatch load job\n(local file upload)", True)
box(7.2, 4.2, 2.2, 1.0, "BigQuery table\nweblogs.access_logs\npartitioned DAY(ts),\nclustered endpoint,status", True)
box(9.8, 4.2, 2.1, 1.0, "SQL analytics (15)\nPython client ->\nCSV + charts (local)", True)
for x1, x2 in ((2.0, 2.4), (4.3, 4.7), (6.8, 7.2), (9.4, 9.8)):
    arrow(x1, 4.7, x2, 4.7, True)
ax.text(0.1, 3.3, "PROPOSED production architecture (dashed, not deployed: needs billing)", fontsize=10, fontweight="bold", color=cs.TEXT2)
box(0.1, 1.6, 1.9, 1.1, "Web servers\n+ Ops Agent /\nCloud Logging", False)
box(2.4, 1.6, 1.9, 1.1, "Cloud Storage\nbucket (raw .gz,\nlifecycle 365 d)", False)
box(4.7, 1.6, 2.1, 1.1, "BigQuery load job\nper hour (scheduled /\nData Transfer Service)", False)
box(7.2, 1.6, 2.2, 1.1, "BigQuery\n(same table design)\n+ scheduled summary\ntables", False)
box(9.8, 2.25, 2.1, 0.9, "Looker Studio\ndashboard", False)
box(9.8, 0.95, 2.1, 0.9, "Cloud Monitoring\nalerts (spike /\nsuspicious IP)", False)
for x1, x2 in ((2.0, 2.4), (4.3, 4.7), (6.8, 7.2)):
    arrow(x1, 2.15, x2, 2.15, False)
arrow(9.4, 2.3, 9.8, 2.6, False); arrow(9.4, 2.0, 9.8, 1.5, False)
ax.text(0.1, 0.35, "Sandbox limits verified in this project: DML and streaming inserts refused, 60-day table/partition expiry; batch load + SELECT/DDL allowed. "
        "Cloud Storage deliberately not used (not tested).", fontsize=8, color=cs.TEXT2)
ax.set_title("Activity 5 architecture: what was actually used vs. proposed production design", loc="left")
fig.savefig(OUT / "a5_architecture.png", dpi=200, bbox_inches="tight"); plt.close(fig); print("saved a5_architecture.png")
