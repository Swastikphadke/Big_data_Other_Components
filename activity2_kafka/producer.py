"""
Activity 2 - Kafka PRODUCER: streams simulated junction sensor readings.

Every simulated minute, each of the 12 junction sensors publishes one JSON
event to topic `traffic-readings`.  The message KEY is the junction_id, so the
default partitioner sends all events of a junction to the same partition and
Kafka preserves their order.

Time is accelerated: --speed N publishes N simulated minutes per real second
(default 4  ->  06:00-22:00 = 960 minutes in about 4 real minutes).

    python producer.py                    # full day
    python producer.py --start 08:00 --end 09:00 --speed 2
"""
import argparse
import json
import time
from collections import Counter

from confluent_kafka import Producer

import config
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402
from traffic_model import SIM_DATE, generate

delivered, failed = Counter(), Counter()


def on_delivery(err, msg):
    """Called by the client once the broker acknowledges (or rejects) a message."""
    if err:
        failed[str(err)] += 1
    else:
        delivered[msg.partition()] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=4.0, help="simulated minutes per real second")
    ap.add_argument("--start", default="06:00")
    ap.add_argument("--end", default="22:00")
    ap.add_argument("--log", help="also write console output to this file")
    a = ap.parse_args()
    teelog.start(a.log)

    readings, _ = generate()
    lo, hi = f"{SIM_DATE}T{a.start}", f"{SIM_DATE}T{a.end}"
    readings = readings[(readings.event_time >= lo) & (readings.event_time < hi)]

    producer = Producer({
        "bootstrap.servers": config.BOOTSTRAP_SERVERS,
        "client.id": "junction-sensor-gateway",
        "acks": "all",                 # wait for the broker to persist each write
        "enable.idempotence": True,    # no duplicates on retry
        "linger.ms": 20,               # small batching window
        "compression.type": "lz4",
    })
    print(f"[producer] topic={config.TOPIC_READINGS} events={len(readings):,} "
          f"window={a.start}-{a.end} speed={a.speed} sim-min/s", flush=True)

    t_start = time.time()
    sent = 0
    for i, (minute, batch) in enumerate(readings.groupby("event_time", sort=True)):
        for rec in batch.to_dict("records"):
            producer.produce(config.TOPIC_READINGS, key=rec["junction_id"],
                             value=json.dumps(rec), on_delivery=on_delivery)
        sent += len(batch)
        producer.poll(0)                       # serve delivery callbacks
        if minute.endswith(":00:00"):          # progress line every simulated hour
            print(f"[producer] sim {minute[11:16]}  sent={sent:>6,} "
                  f"acked={sum(delivered.values()):>6,}  elapsed={time.time() - t_start:6.1f}s", flush=True)
        # pace: minute i should be published at t_start + i / speed
        delay = t_start + (i + 1) / a.speed - time.time()
        if delay > 0:
            time.sleep(delay)

    producer.flush(30)
    elapsed = time.time() - t_start
    total = sum(delivered.values())
    print(f"[producer] DONE  acked={total:,}  failed={sum(failed.values())}  "
          f"elapsed={elapsed:.1f}s  rate={total / elapsed:,.1f} msg/s", flush=True)
    print("[producer] messages per partition: " +
          ", ".join(f"p{p}={n:,}" for p, n in sorted(delivered.items())), flush=True)
    if failed:
        print("[producer] failures:", dict(failed))


if __name__ == "__main__":
    main()
