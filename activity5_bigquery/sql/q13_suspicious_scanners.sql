-- Q13 Suspicious: vulnerability scanning
--     requests for sensitive files / admin paths, or SQL-injection patterns in the query string
SELECT
  client_ip,
  COUNT(*)                                                  AS probe_requests,
  COUNT(DISTINCT path)                                      AS distinct_probe_paths,
  ROUND(100 * COUNTIF(status >= 400) / COUNT(*), 1)         AS pct_4xx_5xx,
  MIN(DATETIME(ts, 'Asia/Kolkata'))                         AS first_seen_ist,
  MAX(DATETIME(ts, 'Asia/Kolkata'))                         AS last_seen_ist,
  ANY_VALUE(user_agent)                                     AS user_agent,
  STRING_AGG(DISTINCT path, ' ' LIMIT 6)                    AS sample_paths
FROM `bigdatasla.weblogs.access_logs`
WHERE REGEXP_CONTAINS(path, r'(?i)(\.env|\.git|wp-login|xmlrpc|phpmyadmin|/etc/passwd|server-status|actuator|backup|^/admin)')
   OR REGEXP_CONTAINS(query_string, r'(?i)(%27|%20or%20|union|select)')
GROUP BY client_ip
HAVING probe_requests >= 10
ORDER BY probe_requests DESC;
