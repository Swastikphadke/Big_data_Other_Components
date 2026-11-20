"""
Activity 3 - PyFlink streaming job: real-time patient vital-sign monitoring.

EDUCATIONAL DEMONSTRATION ONLY - synthetic data, illustrative thresholds, not a
clinical diagnostic tool.

Runs INSIDE the Flink JobManager container:
    flink run -d -py /opt/activity3/vitals_job.py

One Flink job, one Kafka source, five continuous queries (a StatementSet):
  Q1  reading alerts      stateless filter: every reading outside the thresholds
  Q2  episode ONSET       OVER window (abnormal count in last 12 readings) + MATCH_RECOGNIZE
  Q3  episode RESOLVED    same score, MATCH_RECOGNIZE with hysteresis
  Q4  patient summaries   5-minute event-time TUMBLE window per patient
  Q5  ward summaries      15-minute event-time TUMBLE window for the whole ward
Event time comes from the reading itself; the watermark tolerates 30 s of
out-of-order delivery. Results are written to four Kafka topics.
"""
import json

from pyflink.table import EnvironmentSettings, TableEnvironment

T = json.load(open("/opt/activity3/thresholds.json"))
HRH, HRL, SPL = T["heart_rate_high_bpm"], T["heart_rate_low_bpm"], T["spo2_low_pct"]
TH, TL = T["temperature_high_c"], T["temperature_low_c"]
WM = T["watermark_max_out_of_orderness_s"]
N_SCORE, ON, OFF = T["episode_score_window_readings"], T["episode_onset_min_abnormal"], T["episode_resolve_max_abnormal"]
KAFKA = "kafka:29092"

HR_BAD = f"(heart_rate > {HRH} OR heart_rate < {HRL})"
SP_BAD = f"(spo2 < {SPL})"
TP_BAD = f"(temperature > {TH} OR temperature < {TL})"
ANY_BAD = f"({HR_BAD} OR {SP_BAD} OR {TP_BAD})"

env = TableEnvironment.create(EnvironmentSettings.in_streaming_mode())
cfg = env.get_config()
cfg.set("pipeline.name", "patient-vitals-monitor")
cfg.set("parallelism.default", "2")
cfg.set("execution.checkpointing.interval", "10 s")
cfg.set("table.local-time-zone", "UTC")


def kafka_sink(name, topic, columns):
    env.execute_sql(f"""
    CREATE TABLE {name} ({columns}) WITH (
      'connector' = 'kafka', 'topic' = '{topic}', 'properties.bootstrap.servers' = '{KAFKA}',
      'key.format' = 'raw', 'key.fields' = 'patient_id',
      'format' = 'json', 'json.timestamp-format.standard' = 'ISO-8601',
      'sink.delivery-guarantee' = 'at-least-once')""")


# ------------------------------------------------------------------ source + event time
env.execute_sql(f"""
CREATE TABLE vitals_raw (
  patient_id   STRING,
  bed          STRING,
  event_time   TIMESTAMP(3),
  heart_rate   INT,
  spo2         DOUBLE,
  temperature  DOUBLE,
  seq          BIGINT,
  kafka_ts        TIMESTAMP_LTZ(3) METADATA FROM 'timestamp' VIRTUAL,
  kafka_partition INT              METADATA FROM 'partition' VIRTUAL,
  kafka_offset    BIGINT           METADATA FROM 'offset'    VIRTUAL,
  WATERMARK FOR event_time AS event_time - INTERVAL '{WM}' SECOND
) WITH (
  'connector' = 'kafka', 'topic' = 'patient-vitals',
  'properties.bootstrap.servers' = '{KAFKA}', 'properties.group.id' = 'flink-vitals-monitor',
  'scan.startup.mode' = 'earliest-offset',
  'format' = 'json', 'json.timestamp-format.standard' = 'ISO-8601')""")

# end-of-stream markers only advance the watermark; drop them before any logic
env.execute_sql("CREATE TEMPORARY VIEW vitals AS SELECT * FROM vitals_raw WHERE patient_id <> '__EOS__'")

# one row per (reading, vital) so a single pattern query covers all three vitals
env.execute_sql(f"""
CREATE TEMPORARY VIEW vital_long AS
  SELECT patient_id, bed, event_time, kafka_ts, 'heart_rate' AS vital,
         CAST(heart_rate AS DOUBLE) AS val, CASE WHEN {HR_BAD} THEN 1 ELSE 0 END AS abnormal FROM vitals
  UNION ALL
  SELECT patient_id, bed, event_time, kafka_ts, 'spo2', spo2,
         CASE WHEN {SP_BAD} THEN 1 ELSE 0 END FROM vitals
  UNION ALL
  SELECT patient_id, bed, event_time, kafka_ts, 'temperature', temperature,
         CASE WHEN {TP_BAD} THEN 1 ELSE 0 END FROM vitals""")

# stateful sliding score: abnormal readings among the last N readings (event-time ordered)
env.execute_sql(f"""
CREATE TEMPORARY VIEW vital_scored AS
SELECT patient_id, bed, event_time, kafka_ts, vital, val, abnormal,
       SUM(abnormal) OVER (PARTITION BY patient_id, vital ORDER BY event_time
                           ROWS BETWEEN {N_SCORE - 1} PRECEDING AND CURRENT ROW) AS score
FROM vital_long""")

# ------------------------------------------------------------------ sinks
kafka_sink("reading_alerts", "vital-alerts", """
  patient_id STRING, bed STRING, event_time TIMESTAMP(3), heart_rate INT, spo2 DOUBLE,
  temperature DOUBLE, abnormal_vitals STRING, n_abnormal INT, alert_level STRING, seq BIGINT,
  source_kafka_ts TIMESTAMP_LTZ(3), kafka_partition INT, kafka_offset BIGINT""")
kafka_sink("episode_alerts", "episode-alerts", """
  event_type STRING, patient_id STRING, bed STRING, vital STRING, rising_since TIMESTAMP(3),
  confirmed_at TIMESTAMP(3), resolved_at TIMESTAMP(3), score INT, trigger_value DOUBLE,
  min_val DOUBLE, max_val DOUBLE, trigger_kafka_ts TIMESTAMP_LTZ(3)""")
kafka_sink("patient_summaries", "patient-summaries", """
  patient_id STRING, window_start TIMESTAMP(3), window_end TIMESTAMP(3), readings BIGINT,
  avg_hr DOUBLE, min_hr INT, max_hr INT, avg_spo2 DOUBLE, min_spo2 DOUBLE, avg_temp DOUBLE,
  max_temp DOUBLE, hr_abnormal INT, spo2_abnormal INT, temp_abnormal INT, abnormal_readings INT,
  window_status STRING, last_input_kafka_ts TIMESTAMP_LTZ(3)""")
env.execute_sql(f"""
CREATE TABLE ward_summaries (
  window_start TIMESTAMP(3), window_end TIMESTAMP(3), readings BIGINT, patients BIGINT,
  abnormal_readings INT, patients_with_abnormal BIGINT, pct_abnormal DOUBLE,
  last_input_kafka_ts TIMESTAMP_LTZ(3)
) WITH ('connector' = 'kafka', 'topic' = 'ward-summaries', 'properties.bootstrap.servers' = '{KAFKA}',
        'format' = 'json', 'json.timestamp-format.standard' = 'ISO-8601')""")

stmts = env.create_statement_set()

# Q1 - every abnormal reading (no state, no waiting for the watermark)
stmts.add_insert_sql(f"""
INSERT INTO reading_alerts
SELECT patient_id, bed, event_time, heart_rate, spo2, temperature,
       TRIM(CONCAT(CASE WHEN heart_rate > {HRH} THEN 'HR_HIGH ' WHEN heart_rate < {HRL} THEN 'HR_LOW ' ELSE '' END,
                   CASE WHEN {SP_BAD} THEN 'SPO2_LOW ' ELSE '' END,
                   CASE WHEN temperature > {TH} THEN 'TEMP_HIGH ' WHEN temperature < {TL} THEN 'TEMP_LOW ' ELSE '' END)),
       n_abn, CASE WHEN n_abn >= 2 THEN 'MULTI_VITAL' ELSE 'SINGLE_VITAL' END,
       seq, kafka_ts, kafka_partition, kafka_offset
FROM (SELECT *, (CASE WHEN {HR_BAD} THEN 1 ELSE 0 END) + (CASE WHEN {SP_BAD} THEN 1 ELSE 0 END)
               + (CASE WHEN {TP_BAD} THEN 1 ELSE 0 END) AS n_abn FROM vitals)
WHERE n_abn > 0""")

# Q2 - episode ONSET: score goes from <= OFF (L), possibly through the middle band (M), to >= ON (S)
stmts.add_insert_sql(f"""
INSERT INTO episode_alerts
SELECT 'EPISODE_ONSET', patient_id, bed, vital, rising_since, confirmed_at, CAST(NULL AS TIMESTAMP(3)),
       score, trigger_value, CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), trigger_kafka_ts
FROM vital_scored
MATCH_RECOGNIZE (
  PARTITION BY patient_id, vital
  ORDER BY event_time
  MEASURES FIRST(M.event_time) AS rising_since, S.event_time AS confirmed_at, S.score AS score,
           S.val AS trigger_value, S.kafka_ts AS trigger_kafka_ts, S.bed AS bed
  ONE ROW PER MATCH
  AFTER MATCH SKIP PAST LAST ROW
  PATTERN (L M* S)
  DEFINE L AS L.score <= {OFF},
         M AS M.score > {OFF} AND M.score < {ON},
         S AS S.score >= {ON}
)""")

# Q3 - episode RESOLVED: calm (L) -> rising (M*) -> confirmed (S) -> elevated (X*) -> calm again (R).
# The pattern is ANCHORED at a calm row: a partial match can only start at an L row and dies at
# the next row unless the score rises, so there is one live partial match per episode (linear cost).
# (Run 1 used PATTERN (S X* L), which starts a partial match at EVERY high-score row; during a
#  58-minute fever this grew quadratically and back-pressured the whole job - see README.)
stmts.add_insert_sql(f"""
INSERT INTO episode_alerts
SELECT 'EPISODE_RESOLVED', patient_id, bed, vital, rising_since, confirmed_at, resolved_at,
       score, trigger_value, min_val, max_val, trigger_kafka_ts
FROM vital_scored
MATCH_RECOGNIZE (
  PARTITION BY patient_id, vital
  ORDER BY event_time
  MEASURES FIRST(M.event_time) AS rising_since, S.event_time AS confirmed_at,
           R.event_time AS resolved_at, R.score AS score, R.val AS trigger_value,
           MIN(X.val) AS min_val, MAX(X.val) AS max_val, R.kafka_ts AS trigger_kafka_ts, R.bed AS bed
  ONE ROW PER MATCH
  AFTER MATCH SKIP PAST LAST ROW
  PATTERN (L M* S X* R)
  DEFINE L AS L.score <= {OFF},
         M AS M.score > {OFF} AND M.score < {ON},
         S AS S.score >= {ON},
         X AS X.score > {OFF},
         R AS R.score <= {OFF}
)""")

# Q4 - per-patient 5-minute event-time windows
stmts.add_insert_sql(f"""
INSERT INTO patient_summaries
SELECT patient_id, window_start, window_end, COUNT(*),
       ROUND(AVG(CAST(heart_rate AS DOUBLE)), 1), MIN(heart_rate), MAX(heart_rate),
       ROUND(AVG(spo2), 2), MIN(spo2), ROUND(AVG(temperature), 2), MAX(temperature),
       SUM(CASE WHEN {HR_BAD} THEN 1 ELSE 0 END), SUM(CASE WHEN {SP_BAD} THEN 1 ELSE 0 END),
       SUM(CASE WHEN {TP_BAD} THEN 1 ELSE 0 END), SUM(CASE WHEN {ANY_BAD} THEN 1 ELSE 0 END),
       CASE WHEN SUM(CASE WHEN {ANY_BAD} THEN 1 ELSE 0 END) = 0 THEN 'STABLE'
            WHEN SUM(CASE WHEN {ANY_BAD} THEN 1 ELSE 0 END) * 2 >= COUNT(*) THEN 'ATTENTION'
            ELSE 'REVIEW' END,
       MAX(kafka_ts)
FROM TABLE(TUMBLE(TABLE vitals, DESCRIPTOR(event_time), INTERVAL '{T["patient_summary_window_min"]}' MINUTES))
GROUP BY patient_id, window_start, window_end""")

# Q5 - ward-level 15-minute event-time windows
stmts.add_insert_sql(f"""
INSERT INTO ward_summaries
SELECT window_start, window_end, COUNT(*), COUNT(DISTINCT patient_id),
       SUM(CASE WHEN {ANY_BAD} THEN 1 ELSE 0 END),
       COUNT(DISTINCT CASE WHEN {ANY_BAD} THEN patient_id ELSE CAST(NULL AS STRING) END),
       ROUND(100.0 * SUM(CASE WHEN {ANY_BAD} THEN 1 ELSE 0 END) / COUNT(*), 2),
       MAX(kafka_ts)
FROM TABLE(TUMBLE(TABLE vitals, DESCRIPTOR(event_time), INTERVAL '{T["ward_summary_window_min"]}' MINUTES))
GROUP BY window_start, window_end""")

print("[vitals_job] " + T["DISCLAIMER"])
result = stmts.execute()
print("[vitals_job] submitted job id:", result.get_job_client().get_job_id())
