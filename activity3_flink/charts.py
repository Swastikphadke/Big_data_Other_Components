"""
Activity 3 - report charts. Inputs:
  data/vitals_readings.csv, data/planted_events.csv   (generated input + ground truth)
  results/*.csv                                        (Flink outputs collected from Kafka)
  results/evaluation_*.csv                             (evaluate.py)
SYNTHETIC DATA - EDUCATIONAL THRESHOLDS - NOT A CLINICAL TOOL.
"""
import json
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import chartstyle as cs  # noqa: E402

HERE = Path(__file__).parent
RES, DATA, OUT = HERE / "results", HERE / "data", HERE / "charts"
OUT.mkdir(exist_ok=True)
cs.apply()
T = json.loads((HERE / "thresholds.json").read_text())
NOTE = "Synthetic data, educational thresholds - not a clinical tool. Source: Flink run 2026-11-03 (job 44b55d69) - {}"
EPI_FILL = "#f6c9c9"

rd = pd.read_csv(DATA / "vitals_readings.csv", parse_dates=["event_time"])
ra = pd.read_csv(RES / "reading_alerts.csv", parse_dates=["event_time"])
ea = pd.read_csv(RES / "episode_alerts.csv")
ps = pd.read_csv(RES / "patient_summaries.csv", parse_dates=["window_start"])
ws = pd.read_csv(RES / "ward_summaries.csv", parse_dates=["window_start", "window_end"])
for c in ("confirmed_at", "resolved_at"):
    ea[c] = pd.to_datetime(ea[c])
UNIT = {"heart_rate": "bpm", "spo2": "%", "temperature": "deg C"}
LIMITS = {"heart_rate": [T["heart_rate_high_bpm"], T["heart_rate_low_bpm"]], "spo2": [T["spo2_low_pct"]],
          "temperature": [T["temperature_high_c"]]}
ABN = {"heart_rate": "HR_", "spo2": "SPO2", "temperature": "TEMP"}

# 1. sustained vs transient: one panel per planted event ------------------------------------
cases = [("P02", "heart_rate", "10:05", "10:45", "Sustained tachycardia"),
         ("P04", "spo2", "10:35", "11:05", "Sustained desaturation"),
         ("P06", "temperature", "10:20", "12:00", "Sustained fever (gradual)"),
         ("P09", "heart_rate", "10:50", "11:15", "Sustained bradycardia (noisy)"),
         ("P08", "heart_rate", "11:05", "11:40", "Multi-vital: HR"),
         ("P08", "spo2", "11:05", "11:40", "Multi-vital: SpO2"),
         ("P01", "heart_rate", "10:05", "10:16", "Transient burst (6 readings)"),
         ("P05", "spo2", "11:15", "11:26", "Transient burst (8 readings)")]
fig, axes = plt.subplots(2, 4, figsize=(13, 6.4))
for ax, (pid, vital, lo, hi, title) in zip(axes.flat, cases):
    lo, hi = pd.Timestamp(f"2025-11-03 {lo}"), pd.Timestamp(f"2025-11-03 {hi}")
    d = rd[(rd.patient_id == pid) & rd.event_time.between(lo, hi)].sort_values("event_time")
    for r in ea[(ea.patient_id == pid) & (ea.vital == vital) & (ea.event_type == "EPISODE_RESOLVED")].itertuples():
        ax.axvspan(r.confirmed_at, r.resolved_at, color=EPI_FILL, lw=0)
    ax.plot(d.event_time, d[vital], color=cs.MUTED, lw=0.9)
    a = ra[(ra.patient_id == pid) & ra.abnormal_vitals.str.contains(ABN[vital]) & ra.event_time.between(lo, hi)]
    ax.scatter(a.event_time, a[vital], s=9, color=cs.CRITICAL, zorder=3, lw=0)
    for lim in LIMITS[vital]:
        ax.axhline(lim, color=cs.TEXT2, ls="--", lw=0.8)
    ax.set_title(f"{pid} {title}", fontsize=9.5)
    ax.set_ylabel(f"{vital.replace('_', ' ')} ({UNIT[vital]})", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=5)); ax.tick_params(labelsize=8); ax.grid(axis="x", visible=False)
fig.legend(handles=[Line2D([], [], color=cs.MUTED, lw=1, label="reading (event time)"),
                    Line2D([], [], color=cs.CRITICAL, marker="o", ls="", ms=4, label="reading alert (Flink Q1)"),
                    Patch(color=EPI_FILL, label="episode: onset confirmed -> resolved (Flink Q2/Q3)"),
                    Line2D([], [], color=cs.TEXT2, ls="--", label="educational threshold")],
           loc="upper center", ncol=4, fontsize=8.5, bbox_to_anchor=(0.5, 0.955))
fig.suptitle("Sustained episodes raise episode alerts; transient bursts only raise reading alerts", x=0.01,
             ha="left", fontweight="bold", fontsize=12)
fig.tight_layout(rect=(0, 0.03, 1, 0.92))
fig.text(0.01, 0.005, NOTE.format("reading_alerts.csv, episode_alerts.csv"), fontsize=7, color=cs.MUTED)
fig.savefig(OUT / "a3_episodes_vs_transients.png", dpi=200); plt.close(fig); print("saved a3_episodes_vs_transients.png")

# 2. score + hysteresis for the noisy bradycardia (P09) ------------------------------------
lo, hi = pd.Timestamp("2025-11-03 10:55"), pd.Timestamp("2025-11-03 11:14")
d = rd[(rd.patient_id == "P09")].sort_values("event_time")
d = d.assign(score=d.hr_abnormal.astype(int).rolling(12, min_periods=1).sum())
d = d[d.event_time.between(lo, hi)]
on = ea[(ea.patient_id == "P09") & (ea.event_type == "EPISODE_ONSET")].confirmed_at.iloc[0]
off = ea[(ea.patient_id == "P09") & (ea.event_type == "EPISODE_RESOLVED")].resolved_at.iloc[0]
fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
for ax in (a1, a2):
    ax.axvspan(on, off, color=EPI_FILL, lw=0); ax.grid(axis="x", visible=False)
a1.plot(d.event_time, d.heart_rate, color=cs.MUTED, lw=1, marker="o", ms=2.5)
a1.axhline(T["heart_rate_low_bpm"], color=cs.TEXT2, ls="--", lw=0.8)
a1.set_ylabel("heart rate (bpm)"); a1.set_title("P09 bradycardia: raw readings cross the 50 bpm line many times", fontsize=10)
a2.step(d.event_time, d.score, where="post", color=cs.BLUE, lw=2)
a2.axhline(T["episode_onset_min_abnormal"], color=cs.TEXT2, ls="--", lw=0.8)
a2.axhline(T["episode_resolve_max_abnormal"], color=cs.TEXT2, ls=":", lw=0.8)
a2.text(lo, 9.3, " onset >= 9 of 12", fontsize=8, color=cs.TEXT); a2.text(lo, 3.3, " resolved <= 3 of 12", fontsize=8, color=cs.TEXT)
a2.annotate(f"ONSET {on:%H:%M:%S}", (on, 9), xytext=(-110, 22), textcoords="offset points", fontsize=8.5,
            arrowprops=dict(arrowstyle="-", color=cs.MUTED))
a2.annotate(f"RESOLVED {off:%H:%M:%S}", (off, 3), xytext=(8, 20), textcoords="offset points", fontsize=8.5,
            arrowprops=dict(arrowstyle="-", color=cs.MUTED))
a2.set_ylim(0, 12.8); a2.set_ylabel("score (abnormal of last 12)")
a2.set_title("Sliding score (Flink OVER window) with hysteresis gives exactly one episode", fontsize=10)
a2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
cs.save(fig, OUT / "a3_score_hysteresis_P09.png",
        "Synthetic data, educational thresholds. Score recomputed from vitals_readings.csv (illustrates the Flink OVER score); ONSET/RESOLVED times are Flink output (episode_alerts.csv)")

# 3. heatmap: abnormal readings per patient per 5-min window (Flink Q4) ------------------
hm = ps.pivot_table(index="patient_id", columns="window_start", values="abnormal_readings", aggfunc="sum")
cmap = LinearSegmentedColormap.from_list("abn", ["#f4f6fa", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
fig, ax = plt.subplots(figsize=(11, 4))
im = ax.imshow(hm.values, aspect="auto", cmap=cmap, vmin=0, vmax=60)
ax.set_yticks(range(len(hm)), hm.index, fontsize=8.5)
ax.set_xticks(range(len(hm.columns)), [c.strftime("%H:%M") for c in hm.columns], rotation=90, fontsize=7.5)
for i in range(hm.shape[0]):
    for j in range(hm.shape[1]):
        v = hm.values[i, j]
        if v:
            ax.text(j, i, int(v), ha="center", va="center", fontsize=6.5, color="white" if v > 25 else cs.TEXT)
ax.grid(False); ax.set_xlabel("5-minute event-time window start")
cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01); cb.set_label("abnormal readings (of 60)")
ax.set_title("Per-patient 5-minute window summaries: abnormal readings per window (Flink TUMBLE)")
cs.save(fig, OUT / "a3_patient_window_heatmap.png", NOTE.format("patient_summaries.csv (240 windows)"))

# 4. ward 15-minute summaries -------------------------------------------------------------
lab = ws.window_start.dt.strftime("%H:%M")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.3))
a1.bar(lab, ws.pct_abnormal, color=cs.BLUE, width=0.6)
for x, v in enumerate(ws.pct_abnormal):
    a1.text(x, v, f"{v:.1f}", ha="center", va="bottom", fontsize=8)
a1.set_ylabel("% of readings abnormal"); a1.set_title("Ward: abnormal readings per 15 min", fontsize=10)
a2.bar(lab, ws.patients_with_abnormal, color=cs.BLUE, width=0.6)
a2.set_ylabel("patients"); a2.set_title("Ward: patients with any abnormal reading", fontsize=10)
for ax in (a1, a2):
    ax.tick_params(axis="x", labelsize=8, rotation=45); ax.grid(axis="x", visible=False)
cs.save(fig, OUT / "a3_ward_summaries.png", NOTE.format("ward_summaries.csv (8 windows)"))

# 5. reading alerts vs episode alerts by planted category ------------------------------------
lbl = ra.merge(rd[["patient_id", "seq", "label"]], on=["patient_id", "seq"]).label.replace({"NORMAL": "NOISE"})
pe = pd.read_csv(RES / "evaluation_episodes.csv")
cats = ["ISOLATED", "NOISE", "TRANSIENT", "SUSTAINED"]
ra_n = [int((lbl == c).sum()) for c in cats]
ep_n = [int(pe[pe.kind == c].onset_alert.sum()) if c in set(pe.kind) else 0 for c in cats]
ev_n = [int((pe.kind == c).sum()) if c in set(pe.kind) else 2 for c in cats]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.4))
a1.bar(cats, ra_n, color=cs.BLUE, width=0.55); a1.set_yscale("log")
for x, v in enumerate(ra_n):
    a1.text(x, v, f"{v:,}", ha="center", va="bottom", fontsize=9)
a1.set_title("Reading alerts (every abnormal reading)", fontsize=10); a1.set_ylabel("alerts (log scale)")
a2.bar(cats, ev_n, color="#d9d8d3", width=0.55, label="planted events")
a2.bar(cats, ep_n, color=cs.BLUE, width=0.3, label="events with an episode alert")
for x, (e, n) in enumerate(zip(ep_n, ev_n)):
    a2.text(x, n, f"{e}/{n}", ha="center", va="bottom", fontsize=9)
a2.set_title("Episode alerts (9-of-12 rule)", fontsize=10); a2.legend(fontsize=8); a2.set_ylim(0, 12.5)
for ax in (a1, a2):
    ax.grid(axis="x", visible=False)
cs.save(fig, OUT / "a3_alert_types_by_category.png",
        "Synthetic data, educational thresholds. Source: reading_alerts.csv, evaluation_episodes.csv. NOISE = 2 natural outliers (P09 HR 48, 49)")

# 6. latency by output type -----------------------------------------------------------------
lat = pd.read_csv(RES / "evaluation_latency.csv")
NL = chr(10)
short = [f"reading alert{NL}(stateless filter)", f"episode alert{NL}(OVER + MATCH_RECOGNIZE)",
         f"5-min patient summary{NL}(TUMBLE window)"]
fig, ax = plt.subplots(figsize=(9, 3.2))
y = np.arange(len(lat))[::-1]
ax.barh(y, lat.p50_ms, color=cs.BLUE, height=0.5)
ax.scatter(lat.p95_ms, y, color=cs.TEXT, marker="|", s=250, zorder=3)
for yy, p50, p95 in zip(y, lat.p50_ms, lat.p95_ms):
    ax.text(p95 * 1.15, yy, f"p50 {p50:,.0f} ms  |  p95 {p95:,.0f} ms", va="center", fontsize=8.5)
ax.set_yticks(y, short, fontsize=8.5); ax.set_xscale("log"); ax.set_xlim(10, 60000)
ax.set_xlabel("wall-clock latency, ms (log): Kafka in -> Flink output in Kafka.  Bar = p50, tick = p95")
ax.grid(axis="y", visible=False)
ax.set_title("Latency: stateless alerts vs event-time operators")
cs.save(fig, OUT / "a3_latency.png", "Synthetic data. Source: evaluation_latency.csv (Flink run 2026-11-03). At 30x speed the 30 s watermark bound = 1 s wall clock.")

# 7. delivery delays vs watermark bound ---------------------------------------------------
fig, ax = plt.subplots(figsize=(8.5, 3.2))
bins = np.concatenate([np.arange(0, 30, 1), np.arange(30, 155, 5)])
ax.hist(rd.delay_s, bins=bins, color=cs.BLUE, edgecolor="white", linewidth=0.3); ax.set_yscale("log")
ax.axvline(T["watermark_max_out_of_orderness_s"], color=cs.CRITICAL, lw=1.2, ls="--")
cnt = rd.delay_class.value_counts()
ax.text(0.47, 0.93, f" watermark bound 30 s\n very late: {cnt['VERY_LATE']} readings\n"
        f" -> dropped by OVER/CEP: 66, by 5-min windows: 12\n -> still alerted by stateless Q1",
        fontsize=8.5, color=cs.TEXT, transform=ax.transAxes, va="top")
ax.set_xlabel("delivery delay (s of event time)"); ax.set_ylabel("readings (log scale)")
ax.set_title(f"Delivery delays: {cnt['OUT_OF_ORDER']:,} out of order within the bound, {cnt['VERY_LATE']} beyond it")
ax.grid(axis="x", visible=False)
cs.save(fig, OUT / "a3_delivery_delay.png", "Synthetic data. Delays: vitals_readings.csv; drop counts: 07_final_flink_metrics.log, 09_evaluation.log")
