-- Q07 Peak usage periods: requests per hour of day (IST) for each weekday (heatmap input)
SELECT
  FORMAT_DATE('%u-%a', DATE(ts, 'Asia/Kolkata'))            AS weekday,
  EXTRACT(HOUR FROM DATETIME(ts, 'Asia/Kolkata'))           AS hour_of_day,
  COUNT(*)                                                  AS requests
FROM `bigdatasla.weblogs.access_logs`
GROUP BY weekday, hour_of_day
ORDER BY weekday, hour_of_day;
