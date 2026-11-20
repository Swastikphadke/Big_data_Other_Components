"""
Activity 3 - bedside-device gateway: publishes SYNTHETIC vital-sign readings to
Kafka topic `patient-vitals` (key = patient_id, 2 partitions).

Readings are sent in ARRIVAL order (event_time + simulated network delay), so
Flink receives some events out of order and a few very late - exactly the
situation event-time processing and watermarks are designed for.

--speed N : N seconds of simulated time per real second (default 30 -> 2 h in 4 min)

At the end one end-of-stream marker (patient_id "__EOS__", event time 15 min after
the last reading) is written to EVERY partition. Flink's watermark is the minimum
over all partitions, so this lets the last event-time windows close; the Flink job
filters the marker out before any processing.
"""
import argparse
import csv
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd
from confluent_kafka import Producer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

HERE = Path(__file__).parent
BOOTSTRAP, TOPIC, PARTITIONS = "localhost:9092", "patient-vitals", 2
T = json.loads((HERE / "thresholds.json").read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=30.0)
    ap.add_argument("--log")
    a = ap.parse_args()
    teelog.start(a.log)
    df = pd.read_csv(HERE / "data" / "vitals_readings.csv", parse_dates=["event_time", "arrival_time"])
    df = df.sort_values("arrival_time").reset_index(drop=True)
    sent_log = []

    def on_delivery(err, msg, rec):
        if err is None:
            sent_log.append((rec["patient_id"], rec["seq"], msg.partition(), msg.offset(), msg.timestamp()[1]))

    p = Producer({"bootstrap.servers": BOOTSTRAP, "client.id": "bedside-gateway", "acks": "all",
                  "enable.idempotence": True, "linger.ms": 10})
    print("[producer] " + T["DISCLAIMER"], flush=True)
    print(f"[producer] topic={TOPIC} readings={len(df):,} speed={a.speed}x  "
          f"out-of-order={int((df.delay_class == 'OUT_OF_ORDER').sum())} very-late={int((df.delay_class == 'VERY_LATE').sum())}",
          flush=True)
    sim0 = df.arrival_time.iloc[0]
    wall0 = time.time()
    next_report = sim0.floor("10min") + timedelta(minutes=10)
    for rec in df.to_dict("records"):
        wait = wall0 + (rec["arrival_time"] - sim0).total_seconds() / a.speed - time.time()
        if wait > 0:                      # compute once: avoids a negative-sleep race at high speed
            time.sleep(wait)
        value = {"patient_id": rec["patient_id"], "bed": rec["bed"],
                 "event_time": rec["event_time"].strftime("%Y-%m-%dT%H:%M:%S.000"),
                 "heart_rate": int(rec["heart_rate"]), "spo2": float(rec["spo2"]),
                 "temperature": float(rec["temperature"]), "seq": int(rec["seq"])}
        p.produce(TOPIC, key=rec["patient_id"], value=json.dumps(value),
                  on_delivery=lambda e, m, r=rec: on_delivery(e, m, r))
        p.poll(0)
        if rec["arrival_time"] >= next_report:
            print(f"[producer] sim {next_report:%H:%M}  delivered={len(sent_log):>6,}  "
                  f"elapsed={time.time() - wall0:6.1f}s", flush=True)
            next_report += timedelta(minutes=10)
    p.flush(30)
    eos_time = (df.event_time.max() + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S.000")
    for part in range(PARTITIONS):
        p.produce(TOPIC, partition=part, key="__EOS__", value=json.dumps(
            {"patient_id": "__EOS__", "bed": "-", "event_time": eos_time, "heart_rate": 0,
             "spo2": 0.0, "temperature": 0.0, "seq": -1}))
    p.flush(30)
    print(f"[producer] DONE delivered={len(sent_log):,}/{len(df):,} in {time.time() - wall0:.1f}s; "
          f"end-of-stream markers sent to partitions 0..{PARTITIONS - 1} (event_time {eos_time})", flush=True)
    per_part = pd.Series([s[2] for s in sent_log]).value_counts().sort_index().to_dict()
    print(f"[producer] readings per partition: {per_part}", flush=True)
    out = HERE / "results"; out.mkdir(exist_ok=True)
    with open(out / "sent_log.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["patient_id", "seq", "partition", "offset", "kafka_ts_ms"]); w.writerows(sent_log)


if __name__ == "__main__":
    main()
