-- Q6. Monthly sales trend with month-over-month growth (LAG window function)
SELECT sale_month, revenue_inr, invoices,
       ROUND(100 * (revenue_inr - LAG(revenue_inr) OVER (ORDER BY sale_month))
             / LAG(revenue_inr) OVER (ORDER BY sale_month), 2) AS mom_growth_pct
FROM (
    SELECT sale_month,
           ROUND(SUM(amount), 2)        AS revenue_inr,
           COUNT(DISTINCT invoice_id)   AS invoices
    FROM supermarket.sales
    GROUP BY sale_month
) m
ORDER BY sale_month;
