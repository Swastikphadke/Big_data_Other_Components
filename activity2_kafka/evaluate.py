"""
Activity 2 - evaluate the pipeline run.

1. Data integrity : every generated reading was ingested exactly once, per-junction order preserved.
2. Latency        : producer create-time -> archiver receive-time (Kafka metadata).
3. Detection      : alert intervals (OPEN..CLEAR) vs noise-free ground truth, minute by minute
                    and episode by episode (detection delay, clear delay, false alarms).
Writes results/evaluation_*.csv and prints a summary (log it with --log).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

HERE = Path(__file__).parent
RES, DATA = HERE / "results", HERE / "data"


def episodes(minutes):
    """Group a sorted list of minute timestamps into contiguous (start, end_exclusive) runs."""
    out, start, prev = [], None, None
    for t in minutes:
        if start is None:
            start = prev = t
        elif t - prev == pd.Timedelta(minutes=1):
            prev = t
        else:
            out.append((start, prev + pd.Timedelta(minutes=1))); start = prev = t
    if start is not None:
        out.append((start, prev + pd.Timedelta(minutes=1)))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    gen = pd.read_csv(DATA / "traffic_readings.csv")
    ing = pd.read_csv(RES / "ingested_readings.csv")
    truth = pd.read_csv(DATA / "ground_truth.csv", parse_dates=["event_time"])
    alerts = pd.read_csv(RES / "alerts.csv", parse_dates=["event_time", "opened_at_event_time"])

    # ---------------------------------------------------------------- 1. integrity
    key = ["junction_id", "event_time", "vehicle_count", "avg_speed_kmph"]
    merged = gen[key].merge(ing[key], how="outer", indicator=True)
    dupes = ing.duplicated(["junction_id", "event_time"]).sum()
    order_ok = all(g.sort_values("offset").event_time.is_monotonic_increasing
                   for _, g in ing.groupby("junction_id"))
    one_partition = ing.groupby("junction_id").partition.nunique().max() == 1
    print("=== 1. DATA INTEGRITY")
    print(f"generated={len(gen):,}  ingested={len(ing):,}  matched={int((merged._merge == 'both').sum()):,}  "
          f"missing={int((merged._merge == 'left_only').sum())}  unexpected={int((merged._merge == 'right_only').sum())}  "
          f"duplicates={dupes}")
    print(f"each junction on exactly one partition: {one_partition};  per-junction order preserved: {order_ok}")
    print("junctions per partition:", ing.groupby("partition").junction_id.unique().map(sorted).to_dict())

    # ---------------------------------------------------------------- 2. latency
    lat = ing.latency_ms
    print("\n=== 2. END-TO-END LATENCY (producer create -> archiver receive), ms")
    print(f"min={lat.min()}  p50={lat.median():.0f}  p95={lat.quantile(.95):.0f}  p99={lat.quantile(.99):.0f}  max={lat.max()}")
    pd.DataFrame({"stat": ["min", "p50", "p95", "p99", "max", "mean"],
                  "latency_ms": [lat.min(), lat.median(), lat.quantile(.95), lat.quantile(.99), lat.max(),
                                 round(lat.mean(), 1)]}).to_csv(RES / "evaluation_latency.csv", index=False)

    # ---------------------------------------------------------------- 3. detection
    opens = alerts[alerts.event == "OPEN"].set_index("alert_id")
    clears = alerts[alerts.event == "CLEAR"].set_index("alert_id")
    intervals = pd.DataFrame({
        "junction_id": opens.junction_id, "junction_name": opens.junction_name,
        "alert_type": opens.alert_type, "open": opens.event_time,
        "clear": clears.event_time.reindex(opens.index)}).reset_index()
    intervals["clear"] = intervals["clear"].fillna(truth.event_time.max() + pd.Timedelta(minutes=1))

    pred = set()
    for r in intervals.itertuples():
        for t in pd.date_range(r.open, r.clear, freq="min", inclusive="left"):
            pred.add((r.junction_id, t))
    truth["actual"] = truth.true_state != "FREE_FLOW"
    truth["alerted"] = [(j, t) in pred for j, t in zip(truth.junction_id, truth.event_time)]

    rows = []
    for (jid, name, cls), g in truth.groupby(["junction_id", "junction_name", "class"]):
        tp = int((g.actual & g.alerted).sum()); fp = int((~g.actual & g.alerted).sum())
        fn = int((g.actual & ~g.alerted).sum())
        rows.append({"junction_id": jid, "junction_name": name, "class": cls,
                     "true_congested_min": int(g.actual.sum()), "alerted_min": int(g.alerted.sum()),
                     "tp_min": tp, "fp_min": fp, "fn_min": fn,
                     "alerts_opened": int((intervals.junction_id == jid).sum())})
    by_j = pd.DataFrame(rows)
    by_j.to_csv(RES / "evaluation_by_junction.csv", index=False)
    TP, FP, FN = by_j.tp_min.sum(), by_j.fp_min.sum(), by_j.fn_min.sum()
    print("\n=== 3a. MINUTE-LEVEL DETECTION (alert open vs ground-truth congested/incident)")
    print(by_j.to_string(index=False))
    print(f"TOTAL  TP={TP}  FP={FP}  FN={FN}  precision={TP / (TP + FP):.3f}  recall={TP / (TP + FN):.3f}")

    # episode level
    ep_rows = []
    for jid, g in truth[truth.actual].groupby("junction_id"):
        for s, e in episodes(sorted(g.event_time)):
            state = truth[(truth.junction_id == jid) & (truth.event_time == s)].true_state.iloc[0]
            hit = intervals[(intervals.junction_id == jid) & (intervals.open < e) & (intervals.clear > s)]
            ep_rows.append({"junction_id": jid, "true_state": state, "true_start": s, "true_end": e,
                            "true_minutes": int((e - s) / pd.Timedelta(minutes=1)),
                            "detected": len(hit) > 0,
                            "alert_open": hit.open.min() if len(hit) else pd.NaT,
                            "alert_clear": hit.clear.max() if len(hit) else pd.NaT})
    ep = pd.DataFrame(ep_rows)
    ep["detect_delay_min"] = (ep.alert_open - ep.true_start) / pd.Timedelta(minutes=1)
    ep["clear_delay_min"] = (ep.alert_clear - ep.true_end) / pd.Timedelta(minutes=1)
    ep.to_csv(RES / "evaluation_episodes.csv", index=False)
    false_alarms = intervals[[not ((truth.junction_id == r.junction_id) & truth.actual &
                                   (truth.event_time >= r.open) & (truth.event_time < r.clear)).any()
                              for r in intervals.itertuples()]]
    print("\n=== 3b. EPISODE-LEVEL")
    print(ep[["junction_id", "true_state", "true_start", "true_end", "detected",
              "detect_delay_min", "clear_delay_min"]].to_string(index=False))
    print(f"episodes={len(ep)}  detected={int(ep.detected.sum())}  "
          f"mean detect delay={ep.detect_delay_min.mean():.1f} min  mean clear delay={ep.clear_delay_min.mean():.1f} min")
    print(f"false-alarm alerts (no true congestion during alert): {len(false_alarms)}")
    if len(false_alarms):
        print(false_alarms[["alert_id", "junction_id", "junction_name", "open", "clear"]].to_string(index=False))
        fa = truth[truth.junction_id.isin(false_alarms.junction_id)]
        print("min noise-free speed at those junctions:", fa.groupby("junction_id").true_speed.min().to_dict())
    glitch = alerts[(alerts.junction_id == "J07")]
    print(f"sensor glitch J07 12:10 -> alerts raised at J07: {len(glitch)}")


if __name__ == "__main__":
    main()
