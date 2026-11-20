-- Q5. Peak sales hours (all branches, full year)
SELECT sale_hour,
       COUNT(DISTINCT invoice_id)   AS invoices,
       ROUND(SUM(amount), 2)        AS revenue_inr
FROM supermarket.sales
GROUP BY sale_hour
ORDER BY sale_hour;
