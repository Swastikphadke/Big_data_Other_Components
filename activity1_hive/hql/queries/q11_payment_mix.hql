-- Q11. Payment mode mix (by invoice)
SELECT payment_mode,
       COUNT(DISTINCT invoice_id)                                              AS invoices,
       ROUND(100 * COUNT(DISTINCT invoice_id) / SUM(COUNT(DISTINCT invoice_id)) OVER (), 2) AS share_pct
FROM supermarket.sales
GROUP BY payment_mode
ORDER BY invoices DESC;
