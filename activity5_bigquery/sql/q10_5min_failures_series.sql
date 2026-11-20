-- Q10 5-minute series of failed requests (5xx) with a rolling baseline over the previous hour (12 buckets)
WITH buckets AS (
  SELECT TIMESTAMP_SECONDS(DIV(UNIX_SECONDS(ts), 300) * 300) AS bucket,
         COUNT(*) AS requests,
         COUNTIF(status >= 500) AS failures
  FROM `bigdatasla.weblogs.access_logs`
  GROUP BY bucket
)
SELECT
  DATETIME(bucket, 'Asia/Kolkata')                          AS bucket_ist,
  requests,
  failures,
  ROUND(AVG(failures) OVER w, 2)                            AS baseline_mean,
  ROUND(STDDEV_SAMP(failures) OVER w, 2)                    AS baseline_sd
FROM buckets
WINDOW w AS (ORDER BY bucket ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING)
ORDER BY bucket;
