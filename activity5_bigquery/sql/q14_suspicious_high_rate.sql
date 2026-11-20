-- Q14 Suspicious: automated high-rate clients that are not known search-engine crawlers
--     (at least 30 separate minutes with >= 20 requests per minute)
WITH per_minute AS (
  SELECT client_ip, TIMESTAMP_TRUNC(ts, MINUTE) AS m, COUNT(*) AS n
  FROM `bigdatasla.weblogs.access_logs`
  GROUP BY client_ip, m
),
rates AS (
  SELECT client_ip, MAX(n) AS max_rpm, COUNTIF(n >= 20) AS minutes_at_20plus_rpm
  FROM per_minute
  GROUP BY client_ip
)
SELECT
  l.client_ip,
  COUNT(*)                                                  AS requests,
  r.max_rpm,
  r.minutes_at_20plus_rpm,
  COUNT(DISTINCT l.path)                                    AS distinct_paths,
  ROUND(100 * COUNTIF(l.endpoint = '/products/{id}') / COUNT(*), 1) AS pct_product_pages,
  COUNTIF(l.status = 429)                                   AS rate_limited_429,
  ANY_VALUE(l.ua_class)                                     AS ua_class,
  ANY_VALUE(l.user_agent)                                   AS user_agent
FROM `bigdatasla.weblogs.access_logs` AS l
JOIN rates AS r USING (client_ip)
WHERE l.ua_class != 'search_bot'
GROUP BY l.client_ip, r.max_rpm, r.minutes_at_20plus_rpm
HAVING r.minutes_at_20plus_rpm >= 30
ORDER BY requests DESC;
