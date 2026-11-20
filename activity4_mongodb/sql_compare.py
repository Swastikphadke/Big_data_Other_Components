"""
Activity 4 - document model vs relational model, on the SAME data.

Exports the current MongoDB catalog into a normalised SQLite schema
(relational_schema.sql: products + product_specs (EAV) + product_variants +
product_tags), then runs equivalent queries in both systems and compares:
  * result counts (must match -> same data, equivalent queries)
  * query shape: joins / statements needed, rows returned to rebuild one product
  * schema evolution: what adding a new attribute requires
Timings are printed only as an observation: SQLite runs in-process, MongoDB
over TCP, so this is NOT a fair engine benchmark.
Writes results/relational_comparison.csv.
"""
import argparse
import random
import sqlite3
import statistics
import sys
import time
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

import config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

HERE = Path(__file__).parent
RES = HERE / "results"
DB_FILE = RES / "relational_tmp.sqlite"


def ms(fn, reps):
    t = []
    for _ in range(reps):
        s = time.perf_counter(); fn(); t.append((time.perf_counter() - s) * 1000)
    return statistics.median(t)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    coll = MongoClient(config.MONGO_URI)[config.DB_NAME][config.COLLECTION]
    DB_FILE.unlink(missing_ok=True)
    con = sqlite3.connect(DB_FILE)
    # temporary comparison database: durability not needed while bulk loading
    con.executescript("PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; PRAGMA cache_size = -65536;")
    ddl = (HERE / "relational_schema.sql").read_text()
    tables_ddl, index_ddl = ddl.split("CREATE INDEX", 1)
    con.executescript(tables_ddl)                     # tables + PK/UNIQUE/CHECK/FK now, secondary indexes after load

    # ---------------------------------------------------------------- export Mongo -> normalised tables (streamed)
    t0 = time.perf_counter()
    P, S, V, T = [], [], [], []
    n_docs = 0

    def flush():
        con.executemany("INSERT INTO products VALUES (" + ",".join("?" * 17) + ")", P)
        con.executemany("INSERT INTO product_specs VALUES (?,?,?)", S)
        con.executemany("INSERT INTO product_variants VALUES (?,?,?,?)", V)
        con.executemany("INSERT INTO product_tags VALUES (?,?)", T)
        P.clear(); S.clear(); V.clear(); T.clear()

    for pid, d in enumerate(coll.find({}, {"_id": 0}, batch_size=2000), start=1):
        P.append((pid, d["sku"], d["name"], d["brand"], d.get("department"), d["category"], d["price"], d["mrp"],
                  d["currency"], d["ratings"]["avg"], d["ratings"]["count"], d["inventory"]["stock"],
                  d["inventory"]["warehouse"], d["inventory"].get("reorder_level"), d["status"],
                  str(d["created_at"]), str(d["updated_at"])))
        S.extend((pid, k, str(v)) for k, v in d.get("specs", {}).items())
        V.extend((pid, v["size"], v["color"], v["stock"]) for v in d.get("variants", []))
        T.extend((pid, t) for t in d.get("tags", []))
        n_docs = pid
        if len(P) == 20000:
            flush()
    flush()
    con.commit()
    t_load = time.perf_counter() - t0
    t1 = time.perf_counter(); con.executescript("CREATE INDEX" + index_ddl); con.commit()
    print(f"exported {n_docs:,} MongoDB documents into 4 tables in {t_load:.1f} s "
          f"(+ {time.perf_counter() - t1:.1f} s to build secondary indexes):")
    P = range(n_docs)   # only len(P) is used below
    rows = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("products", "product_specs", "product_variants", "product_tags")}
    for t, n in rows.items():
        print(f"   {t:<17} {n:>9,} rows")
    print(f"   total rows {sum(rows.values()):,} to represent {len(P):,} documents")

    comp = []

    # ---------------------------------------------------------------- 1. rebuild one full product
    print("\n1. READ ONE COMPLETE PRODUCT (apparel item with variants, specs and tags)")
    sku = coll.find_one({"category": "Apparel"}, {"sku": 1})["sku"]
    doc = coll.find_one({"sku": sku}, {"_id": 0})
    sql_join = """SELECT p.*, s.spec_key, s.spec_value, v.size, v.color, v.stock AS v_stock, t.tag
                  FROM products p LEFT JOIN product_specs s ON s.product_id = p.product_id
                  LEFT JOIN product_variants v ON v.product_id = p.product_id
                  LEFT JOIN product_tags t ON t.product_id = p.product_id WHERE p.sku = ?"""
    jr = con.execute(sql_join, (sku,)).fetchall()
    print(f"   MongoDB : 1 find_one, 1 document returned ({len(doc['specs'])} specs, {len(doc['variants'])} variants, "
          f"{len(doc['tags'])} tags embedded)")
    print(f"   SQL     : 1 statement with 3 LEFT JOINs returns {len(jr)} rows "
          f"(= {len(doc['specs'])} x {len(doc['variants'])} x {len(doc['tags'])} combinations) that the application must de-duplicate")
    print("             alternative: 4 separate statements (products, specs, variants, tags)")
    skus = [d["sku"] for d in coll.aggregate([{"$sample": {"size": 200}}, {"$project": {"sku": 1}}])]
    random.seed(1)
    m_ms = ms(lambda: [coll.find_one({"sku": s}) for s in skus], 3) / len(skus)
    q4 = ["SELECT * FROM products WHERE sku=?", "SELECT spec_key, spec_value FROM product_specs WHERE product_id=?",
          "SELECT size, color, stock FROM product_variants WHERE product_id=?", "SELECT tag FROM product_tags WHERE product_id=?"]

    def sql_read(s):
        p = con.execute(q4[0], (s,)).fetchone()
        for q in q4[1:]:
            con.execute(q, (p[0],)).fetchall()
    s_ms = ms(lambda: [sql_read(s) for s in skus], 3) / len(skus)
    print(f"   observed median per product: MongoDB {m_ms:.3f} ms (over TCP) | SQLite {s_ms:.3f} ms (in-process, 4 statements)")
    comp.append(("Read one complete product", "1 find_one -> 1 nested document", f"1 query + 3 LEFT JOINs -> {len(jr)} rows, or 4 queries"))

    # ---------------------------------------------------------------- 2. nested attribute filter
    print("\n2. FILTER ON CATEGORY-SPECIFIC ATTRIBUTES: 5G smartphones, RAM >= 12 GB, price < 30,000")
    mf = {"category": "Smartphones", "specs.ram_gb": {"$gte": 12}, "specs.five_g": True, "price": {"$lt": 30000}}
    sq = """SELECT COUNT(*) FROM products p
            JOIN product_specs r ON r.product_id = p.product_id AND r.spec_key = 'ram_gb'
            JOIN product_specs g ON g.product_id = p.product_id AND g.spec_key = 'five_g'
            WHERE p.category = 'Smartphones' AND CAST(r.spec_value AS INTEGER) >= 12
              AND g.spec_value = 'True' AND p.price < 30000"""
    mc, sc = coll.count_documents(mf), con.execute(sq).fetchone()[0]
    print(f"   MongoDB : {mf}")
    print(f"   SQL     : two self-joins on the EAV table + CAST of TEXT values")
    print(f"   results : MongoDB {mc:,} | SQL {sc:,}  -> {'MATCH' if mc == sc else 'MISMATCH'}")
    comp.append(("Filter on nested / category-specific attributes", "dot notation on specs.*, typed values",
                 "self-join per attribute on EAV table, values stored as TEXT and CAST"))

    # ---------------------------------------------------------------- 3. array element filter
    print("\n3. ARRAY ELEMENT FILTER: apparel in size M, Black, in stock")
    mf3 = {"category": "Apparel", "variants": {"$elemMatch": {"size": "M", "color": "Black", "stock": {"$gt": 0}}}}
    sq3 = """SELECT COUNT(DISTINCT p.product_id) FROM products p JOIN product_variants v ON v.product_id = p.product_id
             WHERE p.category = 'Apparel' AND v.size = 'M' AND v.color = 'Black' AND v.stock > 0"""
    mc3, sc3 = coll.count_documents(mf3), con.execute(sq3).fetchone()[0]
    print(f"   results : MongoDB {mc3:,} | SQL {sc3:,}  -> {'MATCH' if mc3 == sc3 else 'MISMATCH'}")
    comp.append(("Query inside a list (variants)", "$elemMatch on embedded array", "JOIN product_variants + DISTINCT"))

    # ---------------------------------------------------------------- 4. aggregate (relational strength)
    print("\n4. GROUP-BY REPORT: active products and average price per category")
    m4 = {r["_id"]: r["n"] for r in coll.aggregate([{"$match": {"status": "active"}}, {"$group": {"_id": "$category", "n": {"$sum": 1}}}])}
    s4 = dict(con.execute("SELECT category, COUNT(*) FROM products WHERE status='active' GROUP BY category").fetchall())
    print(f"   per-category counts identical: {m4 == s4}   (both systems express this easily: $group vs GROUP BY)")
    comp.append(("Aggregation report", "$match + $group pipeline", "GROUP BY (equally simple)"))

    # ---------------------------------------------------------------- 5. schema evolution
    print("\n5. SCHEMA EVOLUTION: headphones gain 'ip_rating'; products gain 'sustainability' object")
    print("   MongoDB : write the new fields; validator allows extra properties; existing documents untouched")
    print("   SQL     : either ALTER TABLE ADD COLUMN (nullable for every non-headphone row) or new EAV rows;")
    print("             a nested 'sustainability' object needs a new table or JSON column")
    t = time.perf_counter(); con.execute("ALTER TABLE products ADD COLUMN ip_rating TEXT"); con.commit()
    print(f"   (SQLite ALTER TABLE ADD COLUMN took {(time.perf_counter() - t) * 1000:.1f} ms - a metadata change; the cost of"
          f" schema change is mostly coordination/migrations, not execution time)")
    comp.append(("Add a new attribute", "just write it (validator keeps core fields consistent)",
                 "migration: ALTER TABLE / EAV rows / new table"))
    comp.append(("Integrity guarantees", "validator ($jsonSchema, $expr) + unique index; multi-document ACID needs a replica set",
                  "foreign keys, CHECK constraints, ACID transactions across tables by default"))
    comp.append(("Storage of one product", "1 document",
                 f"1 + {rows['product_specs'] / rows['products']:.1f} spec + {rows['product_variants'] / rows['products']:.1f} variant + "
                 f"{rows['product_tags'] / rows['products']:.1f} tag rows (average)"))
    pd.DataFrame(comp, columns=["aspect", "mongodb_document_model", "relational_model"]).to_csv(
        RES / "relational_comparison.csv", index=False)
    pd.DataFrame([{"item": "mongodb_documents", "value": len(P)}] +
                 [{"item": f"sql_rows_{t}", "value": n} for t, n in rows.items()] +
                 [{"item": "one_product_mongo_docs", "value": 1}, {"item": "one_product_sql_join_rows", "value": len(jr)},
                  {"item": "nested_filter_mongo", "value": mc}, {"item": "nested_filter_sql", "value": sc},
                  {"item": "array_filter_mongo", "value": mc3}, {"item": "array_filter_sql", "value": sc3}]
                 ).to_csv(RES / "relational_counts.csv", index=False)
    con.close(); DB_FILE.unlink(missing_ok=True)
    print("\nsaved results/relational_comparison.csv (temporary SQLite file removed)")


if __name__ == "__main__":
    main()
