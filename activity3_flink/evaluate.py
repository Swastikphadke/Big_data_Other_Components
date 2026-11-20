"""
Activity 3 - evaluate the Flink run against ground truth and an independent
reference implementation. (SYNTHETIC DATA - educational thresholds only.)

  1. Counts & reading alerts : every abnormal reading alerted exactly once?
  2. Event time / late data  : simulate the watermark from the actual Kafka delivery
                               order and predict which readings Flink must drop as late
  3. Window summaries        : Flink counts vs reference counts (with / without drops)
  4. Episodes                : onset/resolution vs planted events and vs a pandas
                               re-implementation of the same 9-of-12 / 3-of-12 rule
  5. Latency                 : Kafka-in -> Flink-out, per output type
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

HERE = Path(__file__).parent
RES, DATA = HERE / "results", HERE / "data"
T = json.loads((HERE / "thresholds.json").read_text())
WM = pd.Timedelta(seconds=T["watermark_max_out_of_orderness_s"])
VITAL_FLAG = {"heart_rate": "hr_abnormal", "spo2": "spo2_abnormal", "temperature": "temp_abnormal"}


def ts_ms(s):
    return pd.to_datetime(s, utc=True, format="ISO8601").dt.as_unit("ms").astype("int64")  # explicit unit (pandas 3 infers resolution)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    print(T["DISCLAIMER"])
    rd = pd.read_csv(DATA / "vitals_readings.csv", parse_dates=["event_time", "arrival_time"])
    planted = pd.read_csv(DATA / "planted_events.csv", parse_dates=["true_start", "true_end"])
    sent = pd.read_csv(RES / "sent_log.csv")
    ra = pd.read_csv(RES / "reading_alerts.csv")
    ea = pd.read_csv(RES / "episode_alerts.csv")
    ps = pd.read_csv(RES / "patient_summaries.csv", parse_dates=["window_start", "window_end"])
    ws = pd.read_csv(RES / "ward_summaries.csv", parse_dates=["window_start", "window_end"])
    rd = rd.merge(sent, on=["patient_id", "seq"], how="left")
    rd["any_abnormal"] = rd.hr_abnormal | rd.spo2_abnormal | rd.temp_abnormal

    # ------------------------------------------------------------ 1. counts + reading alerts
    print("\n=== 1. INGESTION AND READING-LEVEL ALERTS")
    print(f"readings generated={len(rd):,}  delivered to Kafka={rd.partition.notna().sum():,}  "
          f"per partition={rd.partition.value_counts().sort_index().to_dict()}")
    exp = set(zip(rd[rd.any_abnormal].patient_id, rd[rd.any_abnormal].seq))
    got = list(zip(ra.patient_id, ra.seq))
    print(f"abnormal readings expected={len(exp)}  reading alerts emitted={len(got)}  "
          f"matched={len(exp & set(got))}  missing={len(exp - set(got))}  extra={len(set(got) - exp)}  "
          f"duplicates={len(got) - len(set(got))}")
    late_abn = rd[rd.any_abnormal & (rd.delay_class == "VERY_LATE")]
    print(f"very-late abnormal readings: {len(late_abn)}, of which alerted: "
          f"{sum((p, s) in set(got) for p, s in zip(late_abn.patient_id, late_abn.seq))} "
          f"(stateless filter needs no watermark, so late data is still alerted)")
    print("reading alerts by planted label:",
          ra.merge(rd[["patient_id", "seq", "label"]], on=["patient_id", "seq"]).label.value_counts().to_dict())

    # ------------------------------------------------------------ 2. watermark simulation
    # Each source subtask reads one partition: wm_p = max event_time seen on p - 30 s.
    # Downstream operators use min over partitions. A record is late if, when it arrives,
    # its timestamp (row ops) or its window end (window ops) is <= current watermark.
    order = rd.sort_values(["kafka_ts_ms", "partition", "offset"])
    maxev = {0: pd.Timestamp.min, 1: pd.Timestamp.min}
    win5 = pd.Timedelta(minutes=T["patient_summary_window_min"])
    win15 = pd.Timedelta(minutes=T["ward_summary_window_min"])
    late_row, late_w5, late_w15 = [], [], []
    for r in order.itertuples():
        wm = min(maxev.values())
        wm = wm - WM if wm != pd.Timestamp.min else pd.Timestamp.min
        late_row.append(r.event_time <= wm)
        late_w5.append(r.event_time.floor(win5) + win5 <= wm)
        late_w15.append(r.event_time.floor(win15) + win15 <= wm)
        maxev[int(r.partition)] = max(maxev[int(r.partition)], r.event_time)
    order = order.assign(late_row=late_row, late_w5=late_w5, late_w15=late_w15)
    rd = rd.drop(columns=[c for c in ("late_row", "late_w5", "late_w15") if c in rd]).merge(
        order[["patient_id", "seq", "late_row", "late_w5", "late_w15"]], on=["patient_id", "seq"])
    print("\n=== 2. EVENT TIME AND LATE DATA (watermark = max event time - 30 s, min over 2 partitions)")
    print("delivery classes:", rd.delay_class.value_counts().to_dict())
    print(f"predicted late for row-ordered ops (OVER/MATCH_RECOGNIZE): {int(rd.late_row.sum())}   "
          f"for 5-min windows: {int(rd.late_w5.sum())}   for 15-min windows: {int(rd.late_w15.sum())}")
    print("predicted late by delivery class:",
          rd.groupby("delay_class")[["late_row", "late_w5", "late_w15"]].sum().astype(int).to_dict("index"))

    # ------------------------------------------------------------ 3. window summaries
    print("\n=== 3. WINDOW SUMMARIES")
    rd["w5"] = rd.event_time.dt.floor(win5)
    ref_all = rd.groupby(["patient_id", "w5"]).agg(n_all=("seq", "size"), abn_all=("any_abnormal", "sum"))
    ref_on = rd[~rd.late_w5].groupby(["patient_id", "w5"]).agg(n_pred=("seq", "size"), abn_pred=("any_abnormal", "sum"))
    cmp = ps.set_index(["patient_id", "window_start"])[["readings", "abnormal_readings", "window_status"]]
    cmp.index.names = ["patient_id", "w5"]
    cmp = cmp.join(ref_all, how="outer").join(ref_on, how="outer").fillna(0)
    print(f"patient windows: flink={len(ps)}  expected={len(ref_all)}  (10 patients x 24 windows)")
    print(f"readings counted by flink windows={int(cmp.readings.sum()):,}  all readings={int(cmp.n_all.sum()):,}  "
          f"=> dropped as late={int(cmp.n_all.sum() - cmp.readings.sum())}  (predicted {int(rd.late_w5.sum())})")
    print(f"windows whose count == count-without-predicted-late: {int((cmp.readings == cmp.n_pred).sum())}/{len(cmp)}  "
          f"windows == all readings: {int((cmp.readings == cmp.n_all).sum())}/{len(cmp)}")
    print("window_status distribution:", ps.window_status.value_counts().to_dict())
    cmp.reset_index().to_csv(RES / "evaluation_windows.csv", index=False)
    rd["w15"] = rd.event_time.dt.floor(win15)
    w15 = rd.groupby("w15").agg(n_all=("seq", "size")).join(
        ws.set_index("window_start")[["readings", "abnormal_readings", "patients_with_abnormal", "pct_abnormal"]])
    print(f"ward windows: flink={len(ws)}  counted={int(ws.readings.sum()):,}  all={len(rd):,}  "
          f"dropped={len(rd) - int(ws.readings.sum())}  (predicted {int(rd.late_w15.sum())})")

    # ------------------------------------------------------------ 4. episodes
    print("\n=== 4. EPISODE DETECTION (score = abnormal readings in last 12; onset >= 9, resolved <= 3)")
    ref_rows = []
    kept = rd[~rd.late_row].sort_values("event_time")
    for (pid, vital), flag in [((p, v), f) for p in rd.patient_id.unique() for v, f in VITAL_FLAG.items()]:
        g = kept[kept.patient_id == pid]
        score = g[flag].astype(int).rolling(T["episode_score_window_readings"], min_periods=1).sum().to_numpy()
        state, onset = "LOW", None
        for ts, s in zip(g.event_time, score):
            if state == "LOW" and s >= T["episode_onset_min_abnormal"]:
                state, onset = "HIGH", ts
                ref_rows.append(("EPISODE_ONSET", pid, vital, ts))
            elif state == "HIGH" and s <= T["episode_resolve_max_abnormal"]:
                state = "LOW"; ref_rows.append(("EPISODE_RESOLVED", pid, vital, ts))
    ref = pd.DataFrame(ref_rows, columns=["event_type", "patient_id", "vital", "ts"])
    ea["ts"] = pd.to_datetime(np.where(ea.event_type == "EPISODE_ONSET", ea.confirmed_at, ea.resolved_at))
    k = lambda d: set(zip(d.event_type, d.patient_id, d.vital, d.ts))
    print(f"flink episode events={len(ea)} (onsets={int((ea.event_type == 'EPISODE_ONSET').sum())}, "
          f"resolved={int((ea.event_type == 'EPISODE_RESOLVED').sum())})   reference={len(ref)}   "
          f"identical (type, patient, vital, timestamp): {len(k(ea) & k(ref))}/{len(ref)}  "
          f"flink-only={len(k(ea) - k(ref))}  reference-only={len(k(ref) - k(ea))}")
    rows = []
    for ev in planted.itertuples():
        on = ea[(ea.event_type == "EPISODE_ONSET") & (ea.patient_id == ev.patient_id) & (ea.vital == ev.vital)
                & (ea.ts >= ev.true_start) & (ea.ts <= ev.true_end + pd.Timedelta(minutes=1))]
        rs = ea[(ea.event_type == "EPISODE_RESOLVED") & (ea.patient_id == ev.patient_id) & (ea.vital == ev.vital)
                & (ea.ts >= ev.true_start)]
        rows.append({"kind": ev.kind, "patient_id": ev.patient_id, "vital": ev.vital,
                     "true_start": ev.true_start, "true_end": ev.true_end, "onset_alert": len(on) > 0,
                     "onset_at": on.ts.min() if len(on) else pd.NaT,
                     "onset_delay_s": (on.ts.min() - ev.true_start).total_seconds() if len(on) else np.nan,
                     "resolved_at": rs.ts.min() if len(on) and len(rs) else pd.NaT,
                     "resolve_delay_s": (rs.ts.min() - ev.true_end).total_seconds() if len(on) and len(rs) else np.nan})
    pe = pd.DataFrame(rows)
    pe.to_csv(RES / "evaluation_episodes.csv", index=False)
    print(pe.to_string(index=False))
    sus = pe[pe.kind == "SUSTAINED"]
    print(f"SUSTAINED detected {int(sus.onset_alert.sum())}/{len(sus)}  mean onset delay {sus.onset_delay_s.mean():.0f} s  "
          f"mean resolve delay {sus.resolve_delay_s.mean():.0f} s (event time)")
    print(f"TRANSIENT with episode alert: {int(pe[pe.kind == 'TRANSIENT'].onset_alert.sum())}/2   "
          f"ISOLATED with episode alert: {int(pe[pe.kind == 'ISOLATED'].onset_alert.sum())}/{int((pe.kind == 'ISOLATED').sum())}")
    matched = set()
    for ev in planted[planted.kind == "SUSTAINED"].itertuples():
        matched |= set(ea[(ea.event_type == "EPISODE_ONSET") & (ea.patient_id == ev.patient_id) & (ea.vital == ev.vital)
                          & (ea.ts >= ev.true_start) & (ea.ts <= ev.true_end)].index)
    print(f"false episode onsets (not inside a planted sustained episode): "
          f"{int((ea.event_type == 'EPISODE_ONSET').sum()) - len(matched)}")

    # ------------------------------------------------------------ 5. latency
    print("\n=== 5. LATENCY (wall clock, Kafka timestamp in -> Kafka timestamp of Flink output), ms")
    lat = {"reading alert (stateless)": ra.out_kafka_ts_ms - ts_ms(ra.source_kafka_ts),
           "episode alert (OVER + CEP, waits for watermark)": ea.out_kafka_ts_ms - ts_ms(ea.trigger_kafka_ts),
           "5-min patient summary (from last input)": ps.out_kafka_ts_ms - ts_ms(ps.last_input_kafka_ts)}
    rows = []
    for name, v in lat.items():
        rows.append({"output": name, "n": len(v), "p50_ms": v.median(), "p95_ms": v.quantile(.95), "max_ms": v.max()})
        print(f"{name:<50} n={len(v):>5}  p50={v.median():>7.0f}  p95={v.quantile(.95):>7.0f}  max={v.max():>7.0f}")
    pd.DataFrame(rows).to_csv(RES / "evaluation_latency.csv", index=False)
    print(f"(1 s of wall time = {30} s of simulated event time at --speed 30; watermark bound 30 s event time = 1 s wall)")


if __name__ == "__main__":
    main()
