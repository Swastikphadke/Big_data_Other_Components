"""
Activity 3 - collects the Flink job's output topics into CSV files and prints a
live 'clinical review' feed. (SYNTHETIC DATA - educational thresholds only.)

  vital-alerts       -> results/reading_alerts.csv
  episode-alerts     -> results/episode_alerts.csv
  patient-summaries  -> results/patient_summaries.csv
  ward-summaries     -> results/ward_summaries.csv
Each row also stores the Kafka timestamp of the OUTPUT message (when Flink wrote
it), used by evaluate.py for latency.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
from confluent_kafka import Consumer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "results"
TOPICS = {"vital-alerts": "reading_alerts", "episode-alerts": "episode_alerts",
          "patient-summaries": "patient_summaries", "ward-summaries": "ward_summaries"}
T = json.loads((HERE / "thresholds.json").read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idle-exit", type=float, default=45)
    ap.add_argument("--group", default="vitals-collector")
    ap.add_argument("--log")
    a = ap.parse_args()
    teelog.start(a.log)
    OUT.mkdir(exist_ok=True)
    c = Consumer({"bootstrap.servers": "localhost:9092", "group.id": a.group,
                  "auto.offset.reset": "earliest", "client.id": "clinical-review-feed"})
    c.subscribe(list(TOPICS))
    rows = {k: [] for k in TOPICS.values()}
    print("=" * 100)
    print(" CLINICAL REVIEW FEED (Flink output)  -  " + T["DISCLAIMER"][:58])
    print("=" * 100, flush=True)
    last, started = time.time(), False
    try:
        while True:
            m = c.poll(1.0)
            if m is None:
                if started and time.time() - last > a.idle_exit:
                    break
                continue
            if m.error():
                continue
            started, last = True, time.time()
            rec = json.loads(m.value())
            rec["out_kafka_ts_ms"] = m.timestamp()[1]
            rec["collected_ts_ms"] = int(time.time() * 1000)
            name = TOPICS[m.topic()]
            rows[name].append(rec)
            if name == "episode_alerts":
                tag = "EPISODE ONSET   " if rec["event_type"] == "EPISODE_ONSET" else "EPISODE RESOLVED"
                when = rec["confirmed_at"] if rec["event_type"] == "EPISODE_ONSET" else rec["resolved_at"]
                print(f"*** {tag} {rec['patient_id']} {rec['vital']:<11} at {when[11:19]}  "
                      f"score={rec['score']}/12  value={rec['trigger_value']}", flush=True)
            elif name == "reading_alerts":
                print(f"  ! reading  {rec['patient_id']} {rec['event_time'][11:19]}  {rec['abnormal_vitals']:<20} "
                      f"HR={rec['heart_rate']:>3} SpO2={rec['spo2']:>5} T={rec['temperature']:>5}", flush=True)
            elif name == "ward_summaries":
                print(f"  = WARD {rec['window_start'][11:16]}-{rec['window_end'][11:16]}  readings={rec['readings']}  "
                      f"abnormal={rec['abnormal_readings']} ({rec['pct_abnormal']}%)  "
                      f"patients_with_abnormal={rec['patients_with_abnormal']}", flush=True)
    finally:
        c.close()
        for name, r in rows.items():
            pd.DataFrame(r).to_csv(OUT / f"{name}.csv", index=False)
        print("[collector] saved: " + ", ".join(f"{k}={len(v)}" for k, v in rows.items()), flush=True)


if __name__ == "__main__":
    main()
