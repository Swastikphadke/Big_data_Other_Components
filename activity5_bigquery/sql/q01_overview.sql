-- Q01 Dataset overview: volume, period, distinct clients/endpoints, data served, error share
SELECT
  COUNT(*)                                             AS requests,
  COUNT(DISTINCT client_ip)                            AS unique_ips,
  COUNT(DISTINCT endpoint)                             AS distinct_endpoints,
  MIN(DATETIME(ts, 'Asia/Kolkata'))                    AS first_request_ist,
  MAX(DATETIME(ts, 'Asia/Kolkata'))                    AS last_request_ist,
  ROUND(SUM(bytes_sent) / POW(1024, 3), 2)             AS gib_sent,
  ROUND(AVG(response_ms), 1)                           AS avg_response_ms,
  COUNTIF(status BETWEEN 400 AND 499)                  AS client_errors_4xx,
  COUNTIF(status >= 500)                               AS server_errors_5xx,
  ROUND(100 * COUNTIF(status >= 400) / COUNT(*), 3)    AS error_pct
FROM `bigdatasla.weblogs.access_logs`;
