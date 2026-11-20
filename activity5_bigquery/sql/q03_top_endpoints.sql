-- Q03 Most frequently accessed endpoints with error counts and latency percentiles
SELECT
  endpoint,
  COUNT(*)                                                  AS requests,
  ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)          AS pct_of_traffic,
  COUNT(DISTINCT client_ip)                                 AS unique_ips,
  COUNTIF(status BETWEEN 400 AND 499)                       AS errors_4xx,
  COUNTIF(status >= 500)                                    AS errors_5xx,
  APPROX_QUANTILES(response_ms, 100)[OFFSET(50)]            AS p50_ms,
  APPROX_QUANTILES(response_ms, 100)[OFFSET(95)]            AS p95_ms
FROM `bigdatasla.weblogs.access_logs`
GROUP BY endpoint
ORDER BY requests DESC
LIMIT 20;
