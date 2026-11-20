-- =====================================================================
-- Activity 1 : Supermarket sales warehouse in Apache Hive
-- Step 1 - database, raw (staging) table, curated ORC table
-- =====================================================================
CREATE DATABASE IF NOT EXISTS supermarket
COMMENT 'Synthetic supermarket chain sales (24CI51 Activity 1)';
USE supermarket;

-- ---------------------------------------------------------------------
-- 1a. RAW layer: EXTERNAL table over the CSV files (schema-on-read).
--     Hive does not copy or own the data; DROP TABLE leaves files intact.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS sales_raw;
CREATE EXTERNAL TABLE sales_raw (
    invoice_id    STRING,
    line_no       INT,
    txn_ts        TIMESTAMP,
    branch_id     STRING,
    branch_name   STRING,
    city          STRING,
    product_id    STRING,
    product_name  STRING,
    category      STRING,
    unit_price    DECIMAL(10,2),
    quantity      INT,
    payment_mode  STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 'file:///opt/assignment/data/raw';

-- ---------------------------------------------------------------------
-- 1b. CURATED layer: managed table, columnar ORC, partitioned by month.
--     Derived columns (amount, sale_hour, day type) are computed once at load.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS sales;
CREATE TABLE sales (
    invoice_id    STRING,
    line_no       INT,
    txn_ts        TIMESTAMP,
    sale_date     DATE,
    sale_hour     INT,
    day_type      STRING,          -- 'Weekday' / 'Weekend'
    branch_id     STRING,
    branch_name   STRING,
    city          STRING,
    product_id    STRING,
    product_name  STRING,
    category      STRING,
    unit_price    DECIMAL(10,2),
    quantity      INT,
    amount        DECIMAL(12,2),   -- unit_price * quantity
    payment_mode  STRING
)
PARTITIONED BY (sale_month STRING)  -- e.g. '2025-10'
STORED AS ORC
TBLPROPERTIES ('orc.compress'='ZLIB');

-- Dynamic partitioning: Hive creates one partition per distinct sale_month
SET hive.exec.dynamic.partition=true;
SET hive.exec.dynamic.partition.mode=nonstrict;

INSERT OVERWRITE TABLE sales PARTITION (sale_month)
SELECT
    invoice_id, line_no, txn_ts,
    to_date(txn_ts)                                   AS sale_date,
    hour(txn_ts)                                      AS sale_hour,
    CASE WHEN dayofweek(txn_ts) IN (1, 7) THEN 'Weekend' ELSE 'Weekday' END AS day_type,
    branch_id, branch_name, city,
    product_id, product_name, category,
    unit_price, quantity,
    CAST(unit_price * quantity AS DECIMAL(12,2))      AS amount,
    payment_mode,
    date_format(txn_ts, 'yyyy-MM')                    AS sale_month
FROM sales_raw;

-- Verification
SHOW TABLES;
SHOW PARTITIONS sales;
SELECT COUNT(*) AS raw_rows     FROM sales_raw;
SELECT COUNT(*) AS curated_rows FROM sales;
DESCRIBE FORMATTED sales;
