-- Q09 IP-wise request patterns: the 20 most active client IPs
WITH per_minute AS (
  SELECT client_ip, TIMESTAMP_TRUNC(ts, MINUTE) AS m, COUNT(*) AS n
  FROM `bigdatasla.weblogs.access_logs`
  GROUP BY client_ip, m
),
ip_rate AS (
  SELECT client_ip, MAX(n) AS max_requests_per_minute FROM per_minute GROUP BY client_ip
)
SELECT
  l.client_ip,
  COUNT(*)                                                  AS requests,
  COUNT(DISTINCT l.endpoint)                                AS distinct_endpoints,
  ROUND(100 * COUNTIF(l.status >= 400) / COUNT(*), 1)       AS error_pct,
  ANY_VALUE(l.ua_class)                                     AS ua_class,
  MIN(DATETIME(l.ts, 'Asia/Kolkata'))                       AS first_seen_ist,
  MAX(DATETIME(l.ts, 'Asia/Kolkata'))                       AS last_seen_ist,
  ANY_VALUE(r.max_requests_per_minute)                      AS max_requests_per_minute
FROM `bigdatasla.weblogs.access_logs` AS l
JOIN ip_rate AS r USING (client_ip)
GROUP BY l.client_ip
ORDER BY requests DESC
LIMIT 20;
