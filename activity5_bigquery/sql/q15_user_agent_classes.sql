-- Q15 Traffic by client type (user-agent class)
SELECT
  ua_class,
  COUNT(*)                                                  AS requests,
  ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)          AS pct_of_traffic,
  COUNT(DISTINCT client_ip)                                 AS unique_ips,
  ROUND(100 * COUNTIF(status >= 400) / COUNT(*), 2)         AS error_pct
FROM `bigdatasla.weblogs.access_logs`
GROUP BY ua_class
ORDER BY requests DESC;
