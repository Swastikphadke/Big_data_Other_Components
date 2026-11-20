-- Q4. Branch-wise revenue and share of chain revenue
SELECT branch_id, branch_name, city,
       COUNT(DISTINCT invoice_id)                                   AS invoices,
       ROUND(SUM(amount), 2)                                        AS revenue_inr,
       ROUND(100 * SUM(amount) / SUM(SUM(amount)) OVER (), 2)       AS revenue_share_pct,
       ROUND(SUM(amount) / COUNT(DISTINCT invoice_id), 2)           AS avg_basket_inr
FROM supermarket.sales
GROUP BY branch_id, branch_name, city
ORDER BY revenue_inr DESC;
