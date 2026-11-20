-- Q10. Average daily revenue: weekday vs weekend
SELECT day_type,
       COUNT(DISTINCT sale_date)                               AS days,
       ROUND(SUM(amount) / COUNT(DISTINCT sale_date), 2)       AS avg_daily_revenue_inr
FROM supermarket.sales
GROUP BY day_type;
