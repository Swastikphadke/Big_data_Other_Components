-- Q02 HTTP status code distribution and status class
SELECT
  status,
  CONCAT(CAST(DIV(status, 100) AS STRING), 'xx')            AS status_class,
  COUNT(*)                                                  AS requests,
  ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 3)          AS pct_of_all
FROM `bigdatasla.weblogs.access_logs`
GROUP BY status
ORDER BY requests DESC;
