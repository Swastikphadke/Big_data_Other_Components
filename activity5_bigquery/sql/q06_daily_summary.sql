-- Q06 Daily summary (IST calendar days)
SELECT
  DATE(ts, 'Asia/Kolkata')                                  AS day_ist,
  FORMAT_DATE('%a', DATE(ts, 'Asia/Kolkata'))               AS weekday,
  COUNT(*)                                                  AS requests,
  COUNT(DISTINCT client_ip)                                 AS unique_ips,
  ROUND(100 * COUNTIF(status BETWEEN 400 AND 499) / COUNT(*), 2) AS pct_4xx,
  ROUND(100 * COUNTIF(status >= 500) / COUNT(*), 3)         AS pct_5xx,
  ROUND(SUM(bytes_sent) / POW(1024, 3), 2)                  AS gib_sent
FROM `bigdatasla.weblogs.access_logs`
GROUP BY day_ist, weekday
ORDER BY day_ist;
