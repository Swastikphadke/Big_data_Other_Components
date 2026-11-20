# Activity 4 – MongoDB: E-Commerce Product Catalog

## What it does
A synthetic catalog of **200,000 products in 11 categories** is stored in MongoDB Community Server 8.0
and used to demonstrate document modelling, schema validation, CRUD operations, indexing (with a
before/after benchmark using explain plans), aggregation reports, and a comparison with a
normalised relational design holding the same data.

```
generate_catalog.py ─► data/products.jsonl.gz (seed 2024; 11 categories, different specs per category,
        │                                       embedded size/colour variants for apparel & footwear)
        ▼
 setup_db.py ─► MongoDB 8.0 (Docker, WiredTiger cache 256 MB, 127.0.0.1 only)
                 db ecommerce, collection products, validator = $jsonSchema + $expr (mrp >= price)
        │
        ├─► benchmark.py        6 queries x 25 runs: only _id index ─► create 6 indexes ─► same 6 queries
        ├─► validation_demo.py  invalid writes rejected, flexible write accepted, duplicate SKU blocked
        ├─► crud_demo.py        insert / read / update / delete + 4 aggregation reports
        ├─► sql_compare.py      export same data to SQLite (4 normalised tables) and compare
        └─► mongosh/*.js        checks from the MongoDB shell
 run_all.ps1 runs all of the above from a clean start (volume wiped) and captures evidence.
```

## Document design
```json
{ "sku": "SKU-0010401", "name": "MSI Modern 64 Intel Core i7 32GB 1024GB SSD", "brand": "MSI",
  "department": "Electronics", "category": "Laptops", "price": 28009, "mrp": 30160, "currency": "INR",
  "specs": { "cpu": "Intel Core i7", "ram_gb": 32, "storage_gb": 1024, "screen_in": 14, "gpu": "RTX 3050", "weight_kg": 1.33 },
  "ratings": { "avg": 5.0, "count": 328 },
  "inventory": { "stock": 16, "warehouse": "BLR-1", "reorder_level": 10 },
  "status": "active", "tags": ["gift", "premium", "sale"], "created_at": ISODate(...), "updated_at": ISODate(...) }
```
(an actual document from the run - see `evidence/act4/07_mongosh_m1_overview.log`)
* **Common core** (sku, price, inventory, status …) is identical for every product and is validated.
* **`specs` differs per category** (Books: author/isbn/pages; Laptops: cpu/ram/gpu; Groceries: weight/veg …).
* **`variants`** (apparel, footwear) is an *embedded array* of {size, colour, stock}; total stock is kept in `inventory.stock`.
* Embedding fits because specs/variants are always read with the product and are bounded in size.

## Schema validation (`setup_db.py`)
`validationLevel: strict`, `validationAction: error`; required core fields, types, `minimum: 0` for
price/stock, enums for category/status/currency, SKU pattern `^SKU-[0-9]{7}$`, and a cross-field
business rule `{$expr: {$gte: ["$mrp", "$price"]}}`. `specs` is only required to be an object and
extra top-level fields are allowed → **consistency of the core, flexibility elsewhere**.

## Indexes (created in `benchmark.py`)
| Index | Keys | Purpose | Size |
|---|---|---|---|
| `sku_unique` | `{sku: 1}` unique | point lookup; enforces unique SKU | 2.39 MB |
| `brand_1` | `{brand: 1}` | single-field filter | 1.13 MB |
| `category_1_price_1` | `{category: 1, price: 1}` | equality + range/sort (ESR rule) | 2.17 MB |
| `name_tags_text` | text on name, tags | keyword search | 10.9 MB |
| `stock_active_partial` | `{inventory.stock: 1}`, partial `status: "active"` | low-stock report | 0.96 MB |
| `rating_desc` | `{ratings.avg: -1}` | top-rated listings | 1.53 MB |

## Run it (project root, PowerShell)
```powershell
powershell -ExecutionPolicy Bypass -File activity4_mongodb\run_all.ps1            # clean start, all steps
powershell -ExecutionPolicy Bypass -File activity4_mongodb\run_all.ps1 -KeepRunning  # leave mongod running for a demo
# individual steps (mongod running: docker compose --profile mongo up -d)
.venv\Scripts\python.exe activity4_mongodb\generate_catalog.py
.venv\Scripts\python.exe activity4_mongodb\setup_db.py
.venv\Scripts\python.exe activity4_mongodb\benchmark.py
.venv\Scripts\python.exe activity4_mongodb\validation_demo.py
.venv\Scripts\python.exe activity4_mongodb\crud_demo.py
.venv\Scripts\python.exe activity4_mongodb\sql_compare.py
.venv\Scripts\python.exe activity4_mongodb\charts.py
docker exec -it mongodb mongosh ecommerce        # interactive shell
docker compose --profile mongo down               # stop (add -v to delete the data volume)
```

## Verified results (clean-start run, 2026-11-03 21:18–21:30 IST)
**Load and validation**
* 200,000 documents inserted in 16.7 s (12,000 docs/s), all accepted by the validator; 127.7 MB data,
  40.3 MB on disk (WiredTiger compression), average document 638 B. Container memory 343 MB.
* Validation demo: 6 invalid writes rejected with code 121 (negative price, missing sku, bad status,
  negative stock, price > MRP, price as string), 1 update breaking the schema rejected, duplicate SKU
  rejected by the unique index (E11000); a product with brand-new attributes accepted without any
  migration; collection unchanged afterwards (200,000).

**Benchmark** (same 200,000 docs, same queries, 3 warm-ups + 25 timed runs, plan cache cleared, cache warmed)
| Query | Plan before → after | Docs examined | Server ms | Client median ms | Ratio |
|---|---|---|---|---|---|
| Q1 SKU lookup | COLLSCAN → EXPRESS_IXSCAN | 200,000 → 1 | 172 → 0 | 176.23 → 3.05 | ×57.8 |
| Q2 Laptops 50–80k, sort by price | SORT+COLLSCAN → IXSCAN (no sort) | 200,000 → 2,124 | 179 → 16 | 234.34 → 68.05 | ×3.4 |
| Q3 brand = Sennheiser | COLLSCAN → IXSCAN | 200,000 → 1,962 | 162 → 6 | 209.00 → 52.10 | ×4.0 |
| Q4 20 cheapest phones < 20k | SORT+COLLSCAN → LIMIT+IXSCAN | 200,000 → 20 | 188 → 1 | 185.71 → 3.77 | ×49.3 |
| Q5 all Apparel (20 %) | COLLSCAN → IXSCAN | 200,000 → 39,919 | 224 → 114 | 1,977.96 → 2,127.64 | ×0.9 (no gain) |
| Q6 price ≥ 500 (~85 %) | COLLSCAN → COLLSCAN | 200,000 → 200,000 | 141 → 154 | 5,669.58 → 6,025.38 | ×0.9 (no gain) |

Every query returned the same number of results before and after. Index build took 0.6–5.1 s each;
all indexes together use ~21 MB (about half the size of the compressed data).

**CRUD** (selected): R2 SKU lookup examined 1 document; R3 listing with rating filter read 40 index
keys for 5 results; text search used the text index; a sale decremented stock atomically and a request
for 500 units against 117 in stock matched 0 documents (no oversell); `arrayFilters` updated one
variant and a pipeline update recomputed total stock; bulk restock updated 2,723 low-stock products via
the partial index; 3,718 discontinued zero-stock products deleted (2,396 discontinued items with stock kept).

**Relational comparison** (same 196,282 products exported to SQLite)
* 1 collection of 196,282 documents ↔ 4 tables with **1,965,486 rows** (783,588 EAV spec rows, 628,818 variant rows, 356,798 tag rows).
* Rebuilding one apparel product: 1 document vs **60 joined rows** (3 specs × 10 variants × 2 tags) or 4 separate queries.
* Equivalent queries return identical counts (nested-spec filter 1,959 = 1,959; variant filter 9,569 = 9,569; per-category GROUP BY identical).
* Observed (not a fair benchmark: in-process SQLite vs MongoDB over TCP): 3.0 ms vs 0.46 ms per full product read.

## Analysis (what the numbers mean)
1. Indexes help when they make the query **selective**: Q1/Q4 read 1 and 20 documents instead of
   200,000 (≈50–58× faster); the compound index also removed the in-memory SORT (Q2, Q4).
2. For Q2/Q3 the server time fell ~11–27×, but end-to-end only ~3.4–4×, because transferring and
   decoding ~2,000 documents in Python dominates.
3. Q5/Q6 show **no improvement**: Q6 has no usable index (the compound index starts with `category`);
   Q5 still returns 40,000 documents, so client-side work dominates even though server time halved.
   The 0.9 ratios are within run-to-run variation (Q6 runs ranged from 4.2 s to 9.8 s) and are not
   claimed as slow-downs. A test run earlier the same day gave the same pattern (×70 / ×52 / ×1.0).
4. Indexes cost space (~21 MB) and add work to every insert/update; only indexes that serve real
   queries should be kept.

## Design decisions and issues found (viva notes)
1. **Synthetic data realism fixed before any evidence run**: model series were not tied to brands
   ("Vivo Pixel"), TV panel/resolution contradicted each other, washing machines had litres, cricket
   balls cost ₹8,739, and non-Apple laptops had an Apple M3 CPU. Generator corrected (brand-keyed
   series, size-based TV prices, unit per appliance, item-based sports prices).
2. **ESR rule**: in `category_1_price_1`, equality field first, then the range/sort field, so one index
   serves both the filter and the ordering.
3. **Partial index** only contains active products → smaller, and exactly matches the restock query.
4. **Atomic stock update**: the condition `inventory.stock >= qty` is part of the update filter, so two
   concurrent buyers cannot oversell (single-document updates are atomic).
5. **SQLite export took 23 minutes in the first attempt** (host had ~300 MB free RAM, all rows held
   in Python lists, four secondary indexes maintained during insert, durable journaling). Rewritten to
   stream in 20,000-document chunks, build indexes after loading and disable journaling for the
   temporary file: 15–33 s.
6. **Windows PowerShell 5.1** treats docker's progress output on stderr as an error; with
   `$ErrorActionPreference = "Stop"` the first clean run aborted immediately (no evidence written).
   Fixed by using `Continue` and checking `$LASTEXITCODE`.
7. **Benchmark screenshot**: a 245-column console exceeded the screen width and produced an empty
   window image; it was deleted and replaced by a console window displaying the genuine benchmark log
   file (`benchmark_log_console.png`). The benchmark was not re-run because the CRUD demo had already
   changed the data.
8. No authentication, port bound to 127.0.0.1 only (local demo).

## Limitations and improvements
* Synthetic data: prices are random within category ranges (only TV and sports prices depend on
  attributes) and ratings are random, so the brand-rating report is flat (~4.0).
* Single node: no replica set, so no multi-document transactions or high availability; production
  would use a 3-member replica set and sharding (e.g. on `category` + hashed `sku`) for very large catalogs.
* Benchmark on one laptop under memory pressure; absolute times vary between runs (ratios are stable).
* Money stored as double for simplicity; `Decimal128` would avoid rounding issues.
* Text search uses the built-in text index; a production catalog would use Atlas Search or similar.

## Viva questions to prepare
* Why embed `variants` instead of a separate collection? When would you reference instead?
* What does `docsExamined` vs `keysExamined` vs `nReturned` tell you?
* Why does Q6 not use any index? What index would help, and would it be worth it for an 85 % query?
* What is the ESR rule? Why is `{category, price}` not usable for a price-only filter?
* How does the validator keep data consistent if MongoDB is "schema-less"?
* When is a relational database the better choice for this problem (orders, payments, joins, constraints)?
