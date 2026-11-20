-- Q8. Top 3 products in each branch (RANK window function)
SELECT branch_name, rnk, product_name, units_sold, revenue_inr
FROM (
    SELECT branch_name, product_name,
           SUM(quantity)          AS units_sold,
           ROUND(SUM(amount), 2)  AS revenue_inr,
           RANK() OVER (PARTITION BY branch_name ORDER BY SUM(amount) DESC) AS rnk
    FROM supermarket.sales
    GROUP BY branch_name, product_name
) t
WHERE rnk <= 3
ORDER BY branch_name, rnk;
