# Activity 2 – Apache Kafka: Smart-City Traffic Congestion Alerts

## What it does
Twelve simulated junction sensors publish one reading per (simulated) minute to Kafka. A
congestion-detection service consumes the stream, applies threshold rules to a rolling
window per junction and publishes alert lifecycle events (OPEN / ESCALATE / CLEAR) to a
second topic. A control-room consumer displays those alerts, and an independent archiver
consumer stores every reading. Because the synthetic data has a known ground truth, the
detector's accuracy can be measured.

```
 traffic_model.py (12 junctions, seed 7)
        │
        ▼
 producer.py  ──key=junction_id──►  topic traffic-readings (3 partitions)
 (acks=all, idempotent, lz4)              │                     │
                                          │ group               │ group
                                          ▼ congestion-detector ▼ traffic-archiver
                              congestion_detector.py        archiver.py
                              rolling window (5) per key    results/ingested_readings.csv
                              rules + hysteresis            (+ partition, offset, latency)
                                          │
                                          ▼ key=junction_id
                                 topic congestion-alerts (1 partition)
                                          │ group operator-dashboard
                                          ▼
                                 alert_dashboard.py  ("control room")
 Broker: apache/kafka:4.1.0, single node, KRaft (broker+controller), Docker
```

## Files
| File | Role |
|---|---|
| `config.py` | broker address, topic names, **all thresholds** |
| `traffic_model.py` | synthetic sensor model + noise-free ground truth; writes `data/` |
| `producer.py` | Kafka producer (paced real-time replay of the simulated day) |
| `congestion_detector.py` | consumer → rules → producer of alerts |
| `archiver.py` | second consumer group; also used for the replay demo |
| `alert_dashboard.py` | consumer of `congestion-alerts` |
| `setup_topics.sh` | recreate topics, reset consumer groups |
| `evaluate.py` | integrity, latency and detection-accuracy evaluation |
| `charts.py` | report charts from the result files |
| `run_demo.ps1` | opens one window per component for a live demo |

## Detection rules (`config.py`)
Applied to the average of the last **5** readings of a junction (never a single reading):

| Rule | Condition |
|---|---|
| CONGESTION | avg speed < 20 km/h **and** avg count ≥ 45 veh/min |
| INCIDENT (blockage) | avg speed < 15 km/h **and** avg count < 30 veh/min |
| Severity | MODERATE 15–20, HEAVY 10–15, SEVERE < 10 km/h |
| CLEAR (hysteresis) | avg speed > 25 km/h |

## Run it (project root)
```bash
.venv/Scripts/python.exe activity2_kafka/traffic_model.py        # dataset + ground truth
docker compose --profile kafka up -d                              # broker + Kafka-UI (~600 MB RAM)
bash activity2_kafka/setup_topics.sh                              # topics: 3 + 1 partitions
# in separate terminals (or: powershell -File activity2_kafka/run_demo.ps1)
.venv/Scripts/python.exe -u activity2_kafka/congestion_detector.py --log evidence/act2/03_detector.log
.venv/Scripts/python.exe -u activity2_kafka/archiver.py
.venv/Scripts/python.exe -u activity2_kafka/alert_dashboard.py
.venv/Scripts/python.exe -u activity2_kafka/producer.py --speed 4  # ~4 min for 06:00-22:00
# afterwards
.venv/Scripts/python.exe activity2_kafka/evaluate.py
.venv/Scripts/python.exe activity2_kafka/charts.py
docker compose --profile kafka down
```
Useful broker commands:
```bash
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic traffic-readings
docker exec kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --all-groups
docker exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic congestion-alerts --from-beginning --property print.key=true
```
Kafka-UI: http://localhost:8080

## Verified results (run of 2026-11-03, 19:23–19:31 IST, this machine)
| Measure | Result | Evidence |
|---|---|---|
| Events produced / acknowledged / failed | 11,520 / 11,520 / 0 in 240 s (48 msg/s, paced) | 05_producer.log |
| Ingested by archiver | 11,520 — 0 missing, 0 duplicates, payload identical | 07_evaluation.log |
| Per-junction ordering | preserved; every junction on exactly one partition | 07_evaluation.log |
| End-to-end latency | p50 70 ms, p95 95 ms, p99 160 ms, max 304 ms | 07_evaluation.log |
| Alert events | 50 = 14 OPEN (13 CONGESTION, 1 INCIDENT) + 22 ESCALATE + 14 CLEAR; none left open | 03_detector.log, 04_alert_dashboard.log |
| Ground-truth episodes detected | 13 / 13, mean detection delay 1.8 min | 07_evaluation.log |
| Minute-level precision / recall | 0.865 / 0.979 | 07_evaluation.log |
| Incident (J04 14:00–14:44) | INCIDENT alert 14:03 → cleared 14:47 | 03_detector.log |
| Sensor glitch (J07 12:10) | no alert (rolling average absorbed it) | 07_evaluation.log |
| False alarm | 1 — J09 09:32–09:48 (true peak speed 21.5 km/h, 1.5 above threshold) | 07_evaluation.log |
| Mid-run consumer lag | detector 2–12 msgs/partition, archiver 17–102 | 06_consumer_groups_midrun.log |
| Replay with new group | 11,520 re-read from offset 0, identical to original | 08_replay.log, 11_*.log |
| Scale-out (2 instances, 1 group) | A ← partitions [0,1], B ← [2]; alerts identical to single instance | 09_*, 10_*, 11_*.log |

## Issues, corrections and design decisions (viva notes)
1. **Uneven partitions.** The producer (confluent-kafka / librdkafka 2.16) uses librdkafka's default
   `consistent_random` partitioner: CRC32 of the key modulo the partition count (the Java client would
   use murmur2 instead). Verified during the audit: CRC32(junction_id) % 3 reproduces the observed
   junction-to-partition mapping for all 12 keys; murmur2 does not. With only 12 keys the split came out 5 / 1 / 6 junctions (4,800 / 960 / 5,760 msgs). In the
   scale-out test the range assignor happened to give each instance 6 junctions (A: partitions 0+1, B: partition 2),
   i.e. balanced only by luck. Remedies: more partitions than consumers, or a custom partitioner.
2. **Why key by junction_id.** The detector keeps a rolling window *per junction*. Keying guarantees
   all readings of a junction go to one partition, hence to one consumer instance, in order —
   which is why the 2-instance run produced exactly the same alerts as the 1-instance run.
3. **Ordering is per partition only.** The replay log shows simulated time jumping (11:33 → 17:06 →
   09:59) because a catching-up consumer reads partitions in batches; there is no global order.
4. **Hysteresis trade-off.** Clearing at 25 km/h (not 20) prevents alerts flapping on/off, but keeps
   alerts open ~11.6 min after true congestion ends — the main cause of precision 0.865.
5. **The J09 false alarm was kept, not tuned away.** Its true peak speed (21.5 km/h) is just above the
   threshold; sensor noise pushed the 5-minute average below 20. Fixed thresholds are fragile near
   the boundary; per-junction baselines would help.
6. **Model correction before the run.** J07 Richmond Circle was first configured with severity 0.80,
   which made a "light" junction truly congested for 29 minutes; reduced to 0.70 so the glitch test
   is unambiguous. Done before any evidence run.
7. **Failed first attempt (evidence discarded).** The first orchestrated run piped output through
   `tee.exe` via `cmd /c`; quoting of the path with spaces failed, so neither producer nor detector
   started. Those screenshots were deleted and the scripts gained a `--log` option instead.
8. **Startup warning.** On a freshly started broker the idempotent producer logged
   `Coordinator load in progress: retrying` once while acquiring its producer ID; it then succeeded.
9. **Two listeners.** `localhost:9092` for Windows-side Python clients and `kafka:29092` for other
   containers (Kafka-UI now, Flink in Activity 3).

## Honesty note
All sensor data is synthetic and the traffic model is a simplified illustration, not a calibrated
traffic-engineering model. Accuracy figures measure the detector against the model's own
noise-free ground truth.
