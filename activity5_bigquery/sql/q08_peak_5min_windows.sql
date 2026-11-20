-- Q08 Peak traffic periods: the 10 busiest 5-minute windows (requests per second)
SELECT
  DATETIME(TIMESTAMP_SECONDS(DIV(UNIX_SECONDS(ts), 300) * 300), 'Asia/Kolkata') AS window_start_ist,
  COUNT(*)                                                  AS requests,
  ROUND(COUNT(*) / 300, 2)                                  AS requests_per_second,
  COUNT(DISTINCT client_ip)                                 AS unique_ips,
  COUNTIF(ua_class = 'script_or_tool')                      AS scripted_requests
FROM `bigdatasla.weblogs.access_logs`
GROUP BY window_start_ist
ORDER BY requests DESC
LIMIT 10;
