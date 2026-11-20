-- Q7. Category revenue by month (seasonality) - pivot with conditional aggregation
SELECT sale_month,
       ROUND(SUM(CASE WHEN category = 'Beverages'           THEN amount ELSE 0 END), 0) AS beverages,
       ROUND(SUM(CASE WHEN category = 'Frozen & Ice Cream'  THEN amount ELSE 0 END), 0) AS frozen_icecream,
       ROUND(SUM(CASE WHEN category = 'Sweets & Dry Fruits' THEN amount ELSE 0 END), 0) AS sweets_dryfruits,
       ROUND(SUM(CASE WHEN category = 'Household'           THEN amount ELSE 0 END), 0) AS household,
       ROUND(SUM(CASE WHEN category = 'Staples'             THEN amount ELSE 0 END), 0) AS staples
FROM supermarket.sales
GROUP BY sale_month
ORDER BY sale_month;
