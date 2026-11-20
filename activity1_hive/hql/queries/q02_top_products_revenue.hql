-- Q2. Top 10 best-selling products by revenue
SELECT product_id, product_name, category,
       SUM(quantity)            AS units_sold,
       ROUND(SUM(amount), 2)    AS revenue_inr
FROM supermarket.sales
GROUP BY product_id, product_name, category
ORDER BY revenue_inr DESC
LIMIT 10;
