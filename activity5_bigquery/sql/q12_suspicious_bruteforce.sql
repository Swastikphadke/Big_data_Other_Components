-- Q12 Suspicious: brute-force / credential stuffing on login
--     (>= 50 failed POST /login from one IP within one clock hour)
SELECT
  client_ip,
  DATETIME_TRUNC(DATETIME(ts, 'Asia/Kolkata'), HOUR)        AS hour_ist,
  COUNTIF(status = 401)                                     AS failed_logins,
  COUNTIF(status = 200)                                     AS successful_logins,
  ROUND(COUNT(*) / 60, 1)                                   AS attempts_per_minute,
  ANY_VALUE(user_agent)                                     AS user_agent
FROM `bigdatasla.weblogs.access_logs`
WHERE endpoint = '/login' AND method = 'POST'
GROUP BY client_ip, hour_ist
HAVING failed_logins >= 50
ORDER BY failed_logins DESC;
