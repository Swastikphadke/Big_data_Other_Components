"""
Activity 2 - report charts, built only from files produced by the pipeline run:
  results/ingested_readings.csv  (what the archiver consumer received from Kafka)
  results/alerts.csv             (what the detector published)
  results/evaluation_*.csv       (evaluate.py)
  data/ground_truth.csv          (noise-free model state, for validation only)
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import chartstyle as cs  # noqa: E402

HERE = Path(__file__).parent
RES, DATA, OUT = HERE / "results", HERE / "data", HERE / "charts"
OUT.mkdir(exist_ok=True)
cs.apply()
NOTE = "Source: Kafka run 2026-11-03 - {} (synthetic sensor data, seed 7)"
ALERT_FILL = "#f6c9c9"      # pale tint of status 'critical' for alert intervals
TRUTH = "#52514e"

ing = pd.read_csv(RES / "ingested_readings.csv", parse_dates=["event_time"])
alerts = pd.read_csv(RES / "alerts.csv", parse_dates=["event_time", "opened_at_event_time"])
truth = pd.read_csv(DATA / "ground_truth.csv", parse_dates=["event_time"])
names = ing.drop_duplicates("junction_id").set_index("junction_id").junction_name.sort_index()

opens = alerts[alerts.event == "OPEN"].set_index("alert_id")
clears = alerts[alerts.event == "CLEAR"].set_index("alert_id")
iv = pd.DataFrame({"jid": opens.junction_id, "type": opens.alert_type,
                   "open": opens.event_time, "clear": clears.event_time.reindex(opens.index)})
hfmt = mdates.DateFormatter("%H")

# 1. Small multiples: speed per junction with alert intervals + ground truth ----------
fig, axes = plt.subplots(3, 4, figsize=(12, 7.2), sharex=True, sharey=True)
for ax, (jid, name) in zip(axes.flat, names.items()):
    d = ing[ing.junction_id == jid].sort_values("event_time")
    for r in iv[iv.jid == jid].itertuples():
        ax.axvspan(r.open, r.clear, color=ALERT_FILL, lw=0)
    ax.plot(d.event_time, d.avg_speed_kmph.rolling(5).mean(), color=cs.BLUE, lw=1.4)
    t = truth[(truth.junction_id == jid) & (truth.true_state != "FREE_FLOW")]
    ax.scatter(t.event_time, [1.5] * len(t), marker="|", s=18, color=TRUTH, lw=0.8)
    ax.axhline(20, color=cs.MUTED, lw=0.8, ls="--")
    ax.set_title(f"{jid} {name}", fontsize=9.5, loc="left")
    ax.set_ylim(0, 58); ax.grid(axis="x", visible=False)
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[6, 10, 14, 18, 22])); ax.xaxis.set_major_formatter(hfmt)
for ax in axes[:, 0]:
    ax.set_ylabel("km/h")
for ax in axes[-1, :]:
    ax.set_xlabel("hour (simulated)")
fig.legend(handles=[Line2D([], [], color=cs.BLUE, lw=1.6, label="5-reading rolling avg speed (consumed from Kafka)"),
                    Patch(color=ALERT_FILL, label="alert open (detector output)"),
                    Line2D([], [], color=TRUTH, marker="|", ls="", label="ground-truth congested minute"),
                    Line2D([], [], color=cs.MUTED, ls="--", label="20 km/h threshold")],
           loc="upper center", ncol=4, fontsize=8.5, bbox_to_anchor=(0.5, 0.955))
fig.suptitle("Junction speeds, generated alerts and ground truth (06:00-22:00)", x=0.01, ha="left",
             fontweight="bold", fontsize=12)
fig.tight_layout(rect=(0, 0.03, 1, 0.93))
fig.text(0.01, 0.005, NOTE.format("ingested_readings.csv, alerts.csv, ground_truth.csv"), fontsize=7.5, color=cs.MUTED)
fig.savefig(OUT / "a2_junction_speeds_alerts.png", dpi=200); plt.close(fig); print("saved a2_junction_speeds_alerts.png")

# 2. Heatmap: average speed by junction x hour (sequential, darker = slower) ---------
ing["hour"] = ing.event_time.dt.hour
hm = ing.pivot_table(index="junction_id", columns="hour", values="avg_speed_kmph", aggfunc="mean")
cmap = LinearSegmentedColormap.from_list("slow", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"][::-1])
fig, ax = plt.subplots(figsize=(10, 4.6))
im = ax.imshow(hm.values, aspect="auto", cmap=cmap, vmin=5, vmax=50)
ax.set_yticks(range(len(hm)), [f"{j} {names[j]}" for j in hm.index], fontsize=8.5)
ax.set_xticks(range(len(hm.columns)), [f"{h:02d}" for h in hm.columns], fontsize=8.5)
for i in range(hm.shape[0]):
    for j in range(hm.shape[1]):
        v = hm.values[i, j]
        ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7, color="white" if v < 22 else cs.TEXT)
ax.grid(False); ax.set_xlabel("hour of day (simulated)")
cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01); cb.set_label("avg speed km/h (darker = slower)")
ax.set_title("Average speed by junction and hour - congestion-prone roads stand out")
cs.save(fig, OUT / "a2_speed_heatmap.png", NOTE.format("ingested_readings.csv"))

# 3. Minutes alerted vs truly congested per junction ---------------------------------
ev = pd.read_csv(RES / "evaluation_by_junction.csv").iloc[::-1]
lab = ev.junction_id + " " + ev.junction_name
fig, ax = plt.subplots(figsize=(8.5, 4.8))
y = range(len(ev)); h = 0.38
ax.barh([i + h / 2 for i in y], ev.true_congested_min, height=h, color=cs.BLUE, label="ground-truth congested minutes")
ax.barh([i - h / 2 for i in y], ev.alerted_min, height=h, color=cs.ORANGE, label="minutes with alert open")
for i, (t, a_) in enumerate(zip(ev.true_congested_min, ev.alerted_min)):
    if t or a_:
        ax.text(max(t, a_) + 3, i, f"{a_} / {t}", va="center", fontsize=8, color=cs.TEXT2)
ax.set_yticks(list(y), lab, fontsize=8.5); ax.grid(axis="y", visible=False)
ax.set_xlabel("minutes (06:00-22:00)"); ax.legend(loc="lower right", fontsize=8.5)
ax.set_title("Alerted vs truly congested minutes per junction")
cs.save(fig, OUT / "a2_alert_vs_truth.png", NOTE.format("evaluation_by_junction.csv"))

# 4. Zoom: incident at J04 and sensor glitch at J07 (speed / count in separate panels) ---
fig, axes = plt.subplots(2, 2, figsize=(10, 5.2), sharex="col")
for col, (jid, lo, hi, title) in enumerate([("J04", "13:30", "15:20", "J04 Marathahalli - planted INCIDENT 14:00-14:44"),
                                             ("J07", "11:45", "12:35", "J07 Richmond Circle - planted SENSOR GLITCH 12:10")]):
    d = ing[(ing.junction_id == jid)].sort_values("event_time")
    d = d[(d.event_time >= f"2025-11-03 {lo}") & (d.event_time < f"2025-11-03 {hi}")]
    s_ax, c_ax = axes[0, col], axes[1, col]
    for r in iv[iv.jid == jid].itertuples():
        for ax in (s_ax, c_ax):
            ax.axvspan(r.open, r.clear, color=ALERT_FILL, lw=0)
    s_ax.plot(d.event_time, d.avg_speed_kmph, color=cs.MUTED, lw=1, marker="o", markersize=2.5, label="raw reading")
    s_ax.plot(d.event_time, d.avg_speed_kmph.rolling(5).mean(), color=cs.BLUE, lw=2, label="5-reading avg")
    s_ax.axhline(20, color=cs.MUTED, ls="--", lw=0.8); s_ax.axhline(15, color=cs.MUTED, ls=":", lw=0.8)
    c_ax.plot(d.event_time, d.vehicle_count, color=cs.MUTED, lw=1, marker="o", markersize=2.5)
    c_ax.plot(d.event_time, d.vehicle_count.rolling(5).mean(), color=cs.BLUE, lw=2)
    c_ax.axhline(30, color=cs.MUTED, ls=":", lw=0.8)
    s_ax.set_title(title, fontsize=10); s_ax.set_ylim(0, 50); c_ax.set_ylim(0, 100)
    c_ax.set_xlim(pd.Timestamp(f"2025-11-03 {lo}"), pd.Timestamp(f"2025-11-03 {hi}"))
    c_ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 15, 30, 45] if col == 0 else [0, 10, 20, 30, 40, 50]))
    c_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    for ax in (s_ax, c_ax):
        ax.grid(axis="x", visible=False)
axes[0, 0].set_ylabel("speed km/h"); axes[1, 0].set_ylabel("vehicles / min")
axes[0, 0].legend(fontsize=8, loc="center left", bbox_to_anchor=(0.0, 0.62))
axes[0, 1].annotate("single faulty sample: 3 km/h\nrolling avg stays > 20 -> no alert",
                    xy=(pd.Timestamp("2025-11-03 12:10"), 3), xytext=(pd.Timestamp("2025-11-03 12:14"), 6),
                    fontsize=8, color=cs.TEXT, arrowprops=dict(arrowstyle="-", color=cs.MUTED))
cs.save(fig, OUT / "a2_incident_glitch_zoom.png", NOTE.format("ingested_readings.csv, alerts.csv"))

# 5. End-to-end latency distribution ------------------------------------------------------
lat = ing.latency_ms
fig, ax = plt.subplots(figsize=(8, 3.4))
ax.hist(lat.clip(upper=320), bins=64, color=cs.BLUE, edgecolor="white", linewidth=0.4)
for q, lbl, ha in [(0.5, "p50", "right"), (0.95, "p95", "left"), (0.99, "p99", "left")]:
    v = lat.quantile(q); ax.axvline(v, color=cs.TEXT2, lw=0.9, ls="--")
    ax.text(v, ax.get_ylim()[1] * 0.92, f" {lbl} {v:.0f} ms " , fontsize=8.5, color=cs.TEXT, ha=ha)
ax.text(0.99, 0.6, f"max {lat.max()} ms" + chr(10) + f"mean {lat.mean():.0f} ms", transform=ax.transAxes, ha="right", fontsize=8.5, color=cs.TEXT2)
ax.set_xlabel("latency (ms): producer create time -> archiver consumer receive time")
ax.set_ylabel("messages"); ax.grid(axis="x", visible=False)
ax.set_title(f"End-to-end ingestion latency, {len(lat):,} messages")
cs.save(fig, OUT / "a2_latency_hist.png", NOTE.format("ingested_readings.csv (Kafka CreateTime)"))

# 6. Messages per partition (key-hash distribution) ------------------------------------
pp = ing.groupby("partition").agg(msgs=("offset", "size"), j=("junction_id", lambda s: ", ".join(sorted(s.unique()))))
fig, ax = plt.subplots(figsize=(8, 2.8))
ax.barh([f"partition {p}" for p in pp.index][::-1], pp.msgs[::-1], color=cs.BLUE, height=0.55)
for i, (m, j) in enumerate(zip(pp.msgs[::-1], pp.j[::-1])):
    ax.text(m, i, f"  {m:,}  ({j})", va="center", fontsize=8.5, color=cs.TEXT2)
ax.set_xlim(0, pp.msgs.max() * 1.9); ax.grid(axis="y", visible=False); ax.set_xlabel("messages")
ax.set_title("Messages per partition of traffic-readings (key = junction_id)")
cs.save(fig, OUT / "a2_partition_distribution.png", NOTE.format("ingested_readings.csv"))
