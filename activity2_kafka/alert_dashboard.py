"""
Activity 2 - Kafka CONSUMER for traffic operators.

Subscribes to `congestion-alerts` (group `operator-dashboard`) and prints each
alert lifecycle event as it arrives - the 'control-room' view.
"""
import argparse
import json
import time

from confluent_kafka import Consumer

import config
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idle-exit", type=float, default=30)
    ap.add_argument("--log", help="also write console output to this file")
    a = ap.parse_args()
    teelog.start(a.log)
    c = Consumer({"bootstrap.servers": config.BOOTSTRAP_SERVERS, "group.id": "operator-dashboard",
                  "client.id": "control-room-1", "auto.offset.reset": "earliest"})
    c.subscribe([config.TOPIC_ALERTS])
    print("=" * 96)
    print(" SMART-CITY TRAFFIC CONTROL ROOM - live congestion alerts  (topic: congestion-alerts)")
    print("=" * 96, flush=True)
    n, start, last = 0, time.time(), time.time()
    try:
        while True:
            m = c.poll(1.0)
            if m is None:
                if time.time() - last > a.idle_exit:
                    break
                continue
            if m.error():
                continue
            e = json.loads(m.value()); n += 1; last = time.time()
            tag = {"OPEN": "!! ALERT ", "ESCALATE": "^^ WORSE ", "CLEAR": "-- CLEAR "}[e["event"]]
            extra = f"lasted {e['duration_min']} min, worst avg {e['min_avg_speed_kmph']} km/h" \
                if e["event"] == "CLEAR" else f"avg {e['avg_speed_kmph']} km/h, {e['avg_vehicle_count']} veh/min"
            print(f"{tag} {e['event_time'][11:16]}  {e['alert_type']:<10} {e['severity']:<8} "
                  f"{e['junction_id']} {e['junction_name']:<18} {extra}", flush=True)
    finally:
        c.close()
        print(f"[dashboard] {n} alert events received", flush=True)


if __name__ == "__main__":
    main()
