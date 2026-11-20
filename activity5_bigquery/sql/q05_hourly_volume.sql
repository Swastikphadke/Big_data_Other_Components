-- Q05 Request volume over time: hourly series in IST (7 days x 24 hours)
SELECT
  DATETIME_TRUNC(DATETIME(ts, 'Asia/Kolkata'), HOUR)        AS hour_ist,
  COUNT(*)                                                  AS requests,
  COUNT(DISTINCT client_ip)                                 AS unique_ips,
  COUNTIF(status BETWEEN 400 AND 499)                       AS errors_4xx,
  COUNTIF(status >= 500)                                    AS errors_5xx,
  ROUND(AVG(response_ms), 1)                                AS avg_response_ms
FROM `bigdatasla.weblogs.access_logs`
GROUP BY hour_ist
ORDER BY hour_ist;
