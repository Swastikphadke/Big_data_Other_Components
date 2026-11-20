-- Q1. Overall KPIs: total revenue, invoices, units, average basket value
SELECT
    ROUND(SUM(amount), 2)                                   AS total_revenue_inr,
    COUNT(DISTINCT invoice_id)                              AS total_invoices,
    SUM(quantity)                                           AS total_units,
    COUNT(*)                                                AS line_items,
    ROUND(SUM(amount) / COUNT(DISTINCT invoice_id), 2)      AS avg_basket_value_inr
FROM supermarket.sales;
