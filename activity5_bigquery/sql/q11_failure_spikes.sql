-- Q11 Unusual spikes in failed requests (5xx), traffic-aware and robust to self-masking.
--   1. 5-minute buckets: requests and failures (status >= 500)
--   2. baseline failure RATE = failures / requests over the previous ~24 h, EXCLUDING the most
--      recent hour (rows 300..13 back) so that an ongoing incident cannot inflate its own baseline
--   3. expected failures = requests in this bucket x baseline rate;
--      Poisson z = (failures - expected) / sqrt(expected)
--   4. flag buckets with z >= 4 and at least 8 failures
--   5. merge flagged buckets that are at most 10 minutes apart into one incident
--   6. attach the three endpoints with most 5xx inside each incident
-- (A first version used the previous hour's mean/stddev of failures as baseline; the incident then
--  raised its own baseline and was only flagged for 1 bucket - see README.)
WITH buckets AS (
  SELECT TIMESTAMP_SECONDS(DIV(UNIX_SECONDS(ts), 300) * 300) AS bucket,
         COUNT(*)               AS requests,
         COUNTIF(status >= 500) AS failures
  FROM `bigdatasla.weblogs.access_logs`
  GROUP BY bucket
),
baseline AS (
  SELECT *,
         SUM(failures) OVER w / NULLIF(SUM(requests) OVER w, 0) AS baseline_rate,
         COUNT(*) OVER w                                        AS baseline_buckets
  FROM buckets
  WINDOW w AS (ORDER BY bucket ROWS BETWEEN 300 PRECEDING AND 13 PRECEDING)
),
scored AS (
  SELECT *, requests * baseline_rate AS expected,
         (failures - requests * baseline_rate) / SQRT(GREATEST(requests * baseline_rate, 0.5)) AS z
  FROM baseline
  WHERE baseline_buckets >= 36                      -- need at least 3 hours of history
),
flagged AS (
  SELECT *,
         IF(TIMESTAMP_DIFF(bucket, LAG(bucket) OVER (ORDER BY bucket), MINUTE) <= 10, 0, 1) AS new_incident
  FROM scored
  WHERE z >= 4 AND failures >= 8
),
numbered AS (
  SELECT *, SUM(new_incident) OVER (ORDER BY bucket) AS incident_no FROM flagged
),
incidents AS (
  SELECT incident_no,
         MIN(bucket)                                   AS start_ts,
         TIMESTAMP_ADD(MAX(bucket), INTERVAL 5 MINUTE) AS end_ts,
         COUNT(*)                                      AS flagged_buckets,
         SUM(failures)                                 AS failed_requests_in_flagged_buckets,
         ROUND(SUM(expected), 1)                       AS expected_failures,
         ROUND(MAX(z), 1)                              AS max_z_score
  FROM numbered
  GROUP BY incident_no
),
endpoint_failures AS (
  SELECT i.incident_no, l.endpoint, COUNT(*) AS n
  FROM incidents AS i
  JOIN `bigdatasla.weblogs.access_logs` AS l
    ON l.ts >= i.start_ts AND l.ts < i.end_ts AND l.status >= 500
  GROUP BY i.incident_no, l.endpoint
),
top_endpoints AS (           -- BigQuery cannot run correlated subqueries on other tables: aggregate + join instead
  SELECT incident_no,
         STRING_AGG(CONCAT(endpoint, ' (', CAST(n AS STRING), ')'), ', ' ORDER BY n DESC LIMIT 3) AS top_failing_endpoints
  FROM endpoint_failures
  GROUP BY incident_no
)
SELECT
  i.incident_no,
  DATETIME(i.start_ts, 'Asia/Kolkata')                      AS spike_start_ist,
  DATETIME(i.end_ts, 'Asia/Kolkata')                        AS spike_end_ist,
  i.flagged_buckets,
  i.failed_requests_in_flagged_buckets,
  i.expected_failures,
  i.max_z_score,
  t.top_failing_endpoints
FROM incidents AS i
LEFT JOIN top_endpoints AS t USING (incident_no)
ORDER BY spike_start_ist;
