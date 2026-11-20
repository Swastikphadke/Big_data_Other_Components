"""
Activity 2 - Kafka CONSUMER + PRODUCER: congestion detection service.

Consumes `traffic-readings` in consumer group `congestion-detector`.  For each
junction it keeps the last WINDOW readings (state lives per key, which is safe
because a key always maps to one partition and a partition to one consumer in
the group).  Rules (see config.py), applied to the rolling averages:

    CONGESTION : avg_speed < 20 km/h  AND avg_count >= 45 veh/min
    INCIDENT   : avg_speed < 15 km/h  AND avg_count <  30 veh/min
    CLEAR      : avg_speed > 25 km/h  (hysteresis prevents alert flapping)

Lifecycle events OPEN / ESCALATE / CLEAR are published to `congestion-alerts`
(key = junction_id) and appended to results/alerts.csv.

    python congestion_detector.py [--group congestion-detector] [--instance A]
"""
import argparse
import csv
import json
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

from confluent_kafka import Consumer, Producer

import config
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

RESULTS = Path(__file__).parent / "results"
SEV_RANK = {"MODERATE": 1, "HEAVY": 2, "SEVERE": 3}
FIELDS = ["alert_id", "event", "alert_type", "severity", "junction_id", "junction_name",
          "event_time", "avg_speed_kmph", "avg_vehicle_count", "window", "opened_at_event_time",
          "duration_min", "min_avg_speed_kmph", "processed_at", "detector_instance", "partition", "offset"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="congestion-detector")
    ap.add_argument("--instance", default="A")
    ap.add_argument("--idle-exit", type=float, default=15, help="exit after N s without messages")
    ap.add_argument("--out", default=str(RESULTS / "alerts.csv"))
    ap.add_argument("--no-publish", action="store_true",
                    help="write alerts to CSV only (used for the scale-out experiment)")
    ap.add_argument("--log", help="also write console output to this file")
    a = ap.parse_args()
    teelog.start(a.log)
    RESULTS.mkdir(exist_ok=True)

    consumer = Consumer({
        "bootstrap.servers": config.BOOTSTRAP_SERVERS,
        "group.id": a.group,
        "client.id": f"detector-{a.instance}",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    })
    alert_producer = Producer({"bootstrap.servers": config.BOOTSTRAP_SERVERS,
                               "client.id": f"detector-{a.instance}-alerts", "acks": "all"})

    def on_assign(c, parts):
        print(f"[detector-{a.instance}] partitions ASSIGNED: {[p.partition for p in parts]}", flush=True)

    def on_revoke(c, parts):
        print(f"[detector-{a.instance}] partitions REVOKED: {[p.partition for p in parts]}", flush=True)

    consumer.subscribe([config.TOPIC_READINGS], on_assign=on_assign, on_revoke=on_revoke)

    windows = defaultdict(lambda: deque(maxlen=config.WINDOW))
    open_alerts = {}            # junction_id -> dict(state of the open alert)
    seq, n_msgs, last_msg, n_events = 0, 0, time.time(), 0
    out_file = open(a.out, "w", newline="")
    writer = csv.DictWriter(out_file, fieldnames=FIELDS)
    writer.writeheader()
    print(f"[detector-{a.instance}] group={a.group} topic={config.TOPIC_READINGS} window={config.WINDOW} "
          f"rules: CONGESTION speed<{config.CONGESTION_SPEED_KMPH} & count>={config.CONGESTION_MIN_COUNT}; "
          f"INCIDENT speed<{config.INCIDENT_SPEED_KMPH} & count<{config.INCIDENT_MAX_COUNT}; "
          f"CLEAR speed>{config.CLEAR_SPEED_KMPH}", flush=True)

    def emit(event, st, r, avg_s, avg_c, msg):
        nonlocal n_events
        rec = {"alert_id": st["alert_id"], "event": event, "alert_type": st["type"],
               "severity": st["severity"], "junction_id": r["junction_id"],
               "junction_name": r["junction_name"], "event_time": r["event_time"],
               "avg_speed_kmph": round(avg_s, 1), "avg_vehicle_count": round(avg_c, 1),
               "window": config.WINDOW, "opened_at_event_time": st["opened"],
               "duration_min": st["minutes"], "min_avg_speed_kmph": round(st["min_speed"], 1),
               "processed_at": datetime.now().isoformat(timespec="milliseconds"),
               "detector_instance": a.instance, "partition": msg.partition(), "offset": msg.offset()}
        if not a.no_publish:
            alert_producer.produce(config.TOPIC_ALERTS, key=r["junction_id"], value=json.dumps(rec))
            alert_producer.poll(0)
        writer.writerow(rec); out_file.flush()
        n_events += 1
        print(f"[detector-{a.instance}] {event:<8} {st['type']:<10} {st['severity']:<8} "
              f"{r['junction_id']} {r['junction_name']:<18} sim {r['event_time'][11:16]}  "
              f"avg_speed={avg_s:5.1f}  avg_count={avg_c:5.1f}"
              + (f"  duration={st['minutes']} min" if event == "CLEAR" else ""), flush=True)

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                if n_msgs and time.time() - last_msg > a.idle_exit:
                    break
                continue
            if msg.error():
                print("[detector] error:", msg.error()); continue
            n_msgs += 1; last_msg = time.time()
            r = json.loads(msg.value())
            w = windows[r["junction_id"]]
            w.append(r)
            if len(w) < config.WINDOW:
                continue
            avg_s = sum(x["avg_speed_kmph"] for x in w) / len(w)
            avg_c = sum(x["vehicle_count"] for x in w) / len(w)
            jid = r["junction_id"]

            if jid not in open_alerts:
                kind = None
                if avg_s < config.CONGESTION_SPEED_KMPH and avg_c >= config.CONGESTION_MIN_COUNT:
                    kind = "CONGESTION"
                elif avg_s < config.INCIDENT_SPEED_KMPH and avg_c < config.INCIDENT_MAX_COUNT:
                    kind = "INCIDENT"
                if kind:
                    seq += 1
                    st = {"alert_id": f"{a.instance}-{seq:04d}", "type": kind,
                          "severity": config.severity(avg_s), "opened": r["event_time"],
                          "minutes": 0, "min_speed": avg_s}
                    open_alerts[jid] = st
                    emit("OPEN", st, r, avg_s, avg_c, msg)
            else:
                st = open_alerts[jid]
                st["minutes"] += 1
                st["min_speed"] = min(st["min_speed"], avg_s)
                if avg_s > config.CLEAR_SPEED_KMPH:
                    emit("CLEAR", st, r, avg_s, avg_c, msg)
                    del open_alerts[jid]
                elif SEV_RANK[config.severity(avg_s)] > SEV_RANK[st["severity"]]:
                    st["severity"] = config.severity(avg_s)
                    emit("ESCALATE", st, r, avg_s, avg_c, msg)
    except KeyboardInterrupt:
        pass
    finally:
        alert_producer.flush(10)
        consumer.close()          # commits offsets and leaves the group cleanly
        out_file.close()
        print(f"[detector-{a.instance}] stopped: consumed={n_msgs:,} alert_events={n_events} "
              f"still_open={list(open_alerts)}", flush=True)


if __name__ == "__main__":
    main()
