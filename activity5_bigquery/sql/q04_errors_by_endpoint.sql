-- Q04 Error frequency by endpoint and status (endpoints with at least 50 errors)
SELECT
  endpoint,
  COUNT(*)                                                  AS requests,
  COUNTIF(status >= 400)                                    AS errors,
  ROUND(100 * COUNTIF(status >= 400) / COUNT(*), 2)         AS error_rate_pct,
  COUNTIF(status = 401)                                     AS s401,
  COUNTIF(status = 403)                                     AS s403,
  COUNTIF(status = 404)                                     AS s404,
  COUNTIF(status = 429)                                     AS s429,
  COUNTIF(status = 500)                                     AS s500,
  COUNTIF(status IN (502, 503, 504))                        AS s502_503_504
FROM `bigdatasla.weblogs.access_logs`
GROUP BY endpoint
HAVING errors >= 50
ORDER BY errors DESC;
