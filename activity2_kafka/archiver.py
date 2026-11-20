"""
Activity 2 - Kafka CONSUMER (second, independent consumer group).

Group `traffic-archiver` reads the SAME topic as the detector but keeps its own
offsets, so both services receive every event (publish-subscribe).  It writes
every reading to results/ingested_readings.csv together with Kafka metadata
(partition, offset, broker timestamp) and the measured end-to-end latency
(consumer receive time - producer create time).

Re-running with a NEW group id (e.g. --group audit-replay) re-reads the topic
from offset 0: Kafka retains messages, so data can be replayed.
"""
import argparse
import csv
import json
import time
from pathlib import Path

from confluent_kafka import Consumer

import config
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

RESULTS = Path(__file__).parent / "results"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="traffic-archiver")
    ap.add_argument("--out", default=str(RESULTS / "ingested_readings.csv"))
    ap.add_argument("--idle-exit", type=float, default=15)
    ap.add_argument("--log", help="also write console output to this file")
    a = ap.parse_args()
    teelog.start(a.log)
    RESULTS.mkdir(exist_ok=True)

    c = Consumer({"bootstrap.servers": config.BOOTSTRAP_SERVERS, "group.id": a.group,
                  "client.id": f"{a.group}-1", "auto.offset.reset": "earliest"})
    c.subscribe([config.TOPIC_READINGS],
                on_assign=lambda _, ps: print(f"[{a.group}] assigned {[p.partition for p in ps]}", flush=True))
    f = open(a.out, "w", newline="")
    w = csv.writer(f)
    w.writerow(["partition", "offset", "key", "kafka_create_ts_ms", "received_ts_ms", "latency_ms",
                "sensor_id", "junction_id", "junction_name", "event_time", "vehicle_count", "avg_speed_kmph"])
    n, last, per_part = 0, time.time(), {}
    try:
        while True:
            m = c.poll(1.0)
            if m is None:
                if n and time.time() - last > a.idle_exit:
                    break
                continue
            if m.error():
                print("error:", m.error()); continue
            now_ms = int(time.time() * 1000)
            _, create_ms = m.timestamp()
            r = json.loads(m.value())
            w.writerow([m.partition(), m.offset(), m.key().decode(), create_ms, now_ms, now_ms - create_ms,
                        r["sensor_id"], r["junction_id"], r["junction_name"], r["event_time"],
                        r["vehicle_count"], r["avg_speed_kmph"]])
            n += 1; last = time.time(); per_part[m.partition()] = per_part.get(m.partition(), 0) + 1
            if n % 2000 == 0:
                print(f"[{a.group}] archived {n:,} (sim {r['event_time'][11:16]})", flush=True)
    finally:
        c.close(); f.close()
        print(f"[{a.group}] stopped: archived={n:,} per_partition={dict(sorted(per_part.items()))}", flush=True)


if __name__ == "__main__":
    main()
