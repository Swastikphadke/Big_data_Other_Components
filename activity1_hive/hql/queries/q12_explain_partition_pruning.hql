-- Q12. Partition pruning: revenue for October only.
-- EXPLAIN shows Hive reads only the sale_month='2025-10' partition.
EXPLAIN DEPENDENCY
SELECT ROUND(SUM(amount), 2) FROM supermarket.sales WHERE sale_month = '2025-10';
