-- Q9. Slow-moving products: bottom 10 by units sold (candidates for reduced stocking)
SELECT product_id, product_name, category,
       SUM(quantity)            AS units_sold,
       ROUND(SUM(amount), 2)    AS revenue_inr
FROM supermarket.sales
GROUP BY product_id, product_name, category
ORDER BY units_sold ASC
LIMIT 10;
