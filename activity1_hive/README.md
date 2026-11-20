# Activity 1 – Apache Hive: Supermarket Sales Analysis

## What it does
A synthetic year (2025) of supermarket line-item sales for a 6-branch chain is loaded into a
two-layer Hive warehouse and analysed with 12 HiveQL queries (revenue, best sellers,
branch performance, peak hours, monthly trend, seasonality, slow movers, payment mix,
partition pruning).

```
generate_sales.py ──► data/raw/sales_transactions.csv (57 MB, 559,626 rows)
                          │  (bind-mounted into container at /opt/assignment)
                          ▼
   HiveServer2 (apache/hive:4.0.1, Tez local mode, embedded Derby metastore)
     supermarket.sales_raw   EXTERNAL, TEXTFILE, schema-on-read
            │  INSERT OVERWRITE … PARTITION (sale_month)   [dynamic partitioning]
            ▼
     supermarket.sales       ORC (ZLIB), partitioned by sale_month (12 partitions)
            │
            ▼  hql/queries/q01…q12  via Beeline (JDBC)
   results/*.csv ──► charts.py ──► charts/*.png
```

## Prerequisites
* Docker Desktop (WSL2 backend), ~3 GB free RAM for the container
* Python 3.12 virtual environment with `requirements.txt` installed (project root)

## Run it (from the project root, Git Bash)
```bash
# 1. generate the dataset (deterministic, seed 42)
.venv/Scripts/python.exe activity1_hive/generate_sales.py

# 2. start Hive (first start takes ~30 s)
docker compose --profile hive up -d

# 3. create tables + load the partitioned ORC table
export MSYS_NO_PATHCONV=1      # Git Bash only: stops /opt/... being rewritten to C:/...
docker exec hive4 beeline -u jdbc:hive2://localhost:10000/ -f /opt/assignment/hql/01_schema.hql

# 4. run all analysis queries (logs -> evidence/act1/queries, CSV -> activity1_hive/results)
bash activity1_hive/run_queries.sh

# 5. charts
.venv/Scripts/python.exe activity1_hive/charts.py

# 6. stop Hive
docker compose --profile hive down
```
Interactive session: `docker exec -it hive4 beeline -u jdbc:hive2://localhost:10000/`
HiveServer2 Web UI: http://localhost:10002

## Verified results (run of 2026-11-03, this machine)
| Metric | Value | Source |
|---|---|---|
| Rows loaded (raw = curated) | 559,626 | 02_schema_load.log |
| Partitions | 12 (2025-01 … 2025-12) | 02_schema_load.log |
| Storage: CSV vs ORC | 57.0 MB → 5.5 MB (≈10.4× smaller) | generator log, `totalSize` in DESCRIBE FORMATTED |
| Total revenue | ₹11,76,20,095 | q01 |
| Avg basket | ₹588.10 | q01 |
| Top branch | Jayanagar, 26.39 % of revenue | q04 |
| Peak hours | 19:00 (26,369 bills), 18:00 (24,066) | q05 |
| Festive month | Oct, +47.83 % MoM | q06 |
| Weekend vs weekday daily revenue | ₹3.95 L vs ₹2.93 L (1.35×) | q10 |
| Partition pruning | EXPLAIN DEPENDENCY reads only `sale_month=2025-10` | q12 |

## Business insights and inventory recommendations (from the query results)
| Finding (query) | Evidence | Recommendation |
|---|---|---|
| Daily-need items move fastest (q03) | Coriander 40,049 units, Greek yogurt 27,254, curd 25,807 in the year | daily replenishment and short reorder cycles for dairy and fresh produce |
| Revenue concentrates in high-value staples and gifts (q02) | Ghee, dry-fruit gift box, rice, cashew, atta lead revenue | keep safety stock on these items; never let them go out of stock |
| Evening peak (q05) | 17:00–21:00 carries 43.8 % of all invoices; 19:00 alone 13.2 % | restock shelves and schedule extra billing staff before 17:00 |
| Weekend uplift (q10) | ₹3.95 L vs ₹2.93 L average daily revenue (+35 %) | larger Friday deliveries; weekend staffing |
| Festive season (q06, q07) | October revenue +47.83 % MoM; Sweets & Dry Fruits at index 272 and Household at 185 in October (100 = average month) | build festive inventory for sweets, dry fruits, diyas, cleaning products from September |
| Summer season (q07) | Frozen & Ice Cream index 193 and Beverages 140 in May | increase freezer and beverage stock March–May; cut back from July |
| Branch differences (q04) | Jayanagar 26.39 % of revenue, Gokulam 8.98 %; basket ≈ ₹585–595 everywhere | allocate stock by branch volume, not equally; basket size is similar, footfall differs |
| Slow movers (q09) | Khova 250g 116 units, Feeding Bottle 160 units in a year | reduce shelf allocation or move to order-on-demand |

## Honesty note
All data is synthetic. The generator deliberately plants patterns (see `data/planted_patterns.json`).
The analysis demonstrates that the Hive pipeline **recovers known patterns**; it does not
discover facts about any real supermarket.

## Issues, corrections and design decisions (viva notes)
1. **Unrealistic first dataset (fixed before evidence).** Product popularity was first drawn from a
   heavy-tailed Pareto distribution; one product (Frozen Peas) took 18 % of all units. Replaced by
   category purchase frequencies x a moderate lognormal spread; prices made fixed realistic MRPs.
   All evidence comes from the corrected dataset (re-generated, re-loaded, re-queried).
2. **Git Bash path conversion.** `docker exec hive4 beeline -f /opt/...` failed with
   `No FileSystem for scheme "C"` because Git Bash rewrote `/opt/...` into a Windows path.
   Fix: `export MSYS_NO_PATHCONV=1` (built into run_queries.sh).
3. **Hive 4 converts managed tables.** `CREATE TABLE sales ... STORED AS ORC` is reported as
   `EXTERNAL_TABLE` with `TRANSLATED_TO_EXTERNAL=TRUE` and `external.table.purge=TRUE`: Hive 4's
   metastore translates non-ACID managed tables to external tables that still delete data on DROP.
4. **COUNT(*) answered from statistics.** On the curated table `COUNT(*)` returned in < 1 s without a
   Tez job, because the INSERT gathered basic stats (`numRows`). So the run does not prove an ORC
   *scan* speed-up; the verified ORC benefit is storage (57.0 MB -> 5.5 MB).
5. **Two-layer design.** External raw table = schema-on-read over files Hive does not own;
   curated ORC table = columnar, compressed, partitioned by month so month filters prune
   partitions (q12 EXPLAIN DEPENDENCY lists only `sale_month=2025-10`).
