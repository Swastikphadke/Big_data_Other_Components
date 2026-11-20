"""
Activity 4 - query benchmark BEFORE and AFTER indexing.

Identical conditions in both phases: same 200,000 documents, same six queries,
same client, plan cache cleared, collection scanned once to warm the cache,
3 untimed warm-up runs, then 25 timed runs per query (cursor fully consumed).
Per query and phase we record explain("executionStats") - winning plan stages,
keys examined, documents examined, nReturned, server executionTimeMillis - and the
client-side median / p95 wall time.

Outputs: results/benchmark_raw.csv, results/benchmark_summary.csv,
         results/index_build.csv, results/explain/<phase>_<query>.json
"""
import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

from pymongo import ASCENDING, DESCENDING, TEXT, MongoClient

import config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

HERE = Path(__file__).parent
RES = HERE / "results"
REPS, WARMUP = 25, 3

QUERIES = [  # id, description, filter, sort, limit, expectation
    ("Q1", "point lookup by SKU", {"sku": "SKU-0123456"}, None, 0, "index should help a lot"),
    ("Q2", "Laptops priced 50k-80k, sorted by price", {"category": "Laptops", "price": {"$gte": 50000, "$lte": 80000}},
     [("price", ASCENDING)], 0, "compound index: no scan, no in-memory sort"),
    ("Q3", "all products of brand Sennheiser", {"brand": "Sennheiser"}, None, 0, "single-field index"),
    ("Q4", "20 cheapest Smartphones under 20k (listing page)", {"category": "Smartphones", "price": {"$lt": 20000}},
     [("price", ASCENDING)], 20, "compound index: reads only 20 keys"),
    ("Q5", "all Apparel (20 % of collection)", {"category": "Apparel"}, None, 0, "low selectivity: modest gain"),
    ("Q6", "price >= 500 across all categories (~85 %)", {"price": {"$gte": 500}}, None, 0,
     "no usable index (category is the compound prefix): no gain expected"),
]

INDEXES = [  # keys, options, purpose
    ([("sku", ASCENDING)], {"unique": True, "name": "sku_unique"}, "point lookups; enforces unique SKU"),
    ([("brand", ASCENDING)], {"name": "brand_1"}, "brand filter (single field)"),
    ([("category", ASCENDING), ("price", ASCENDING)], {"name": "category_1_price_1"},
     "equality on category + range/sort on price (ESR rule)"),
    ([("name", TEXT), ("tags", TEXT)], {"name": "name_tags_text", "default_language": "english"}, "keyword search"),
    ([("inventory.stock", ASCENDING)], {"name": "stock_active_partial",
                                        "partialFilterExpression": {"status": "active"}}, "low-stock report (partial)"),
    ([("ratings.avg", DESCENDING)], {"name": "rating_desc"}, "top-rated listings"),
]


def stages(node):
    """Flatten a winning-plan tree into 'LIMIT > FETCH > IXSCAN' form."""
    out = [node.get("stage", "?") + (f"[{node['indexName']}]" if "indexName" in node else "")]
    for key in ("inputStage",):
        if key in node:
            out += stages(node[key])
    for child in node.get("inputStages", []):
        out += stages(child)
    return out


def run_phase(db, coll, phase, raw, summary):
    db.command({"planCacheClear": config.COLLECTION})
    t0 = time.perf_counter()
    n = sum(1 for _ in coll.find({}, {"_id": 1}))             # touch every document: warm cache
    print(f"[{phase}] cache warm-up scan of {n:,} docs took {time.perf_counter() - t0:.2f} s")
    for qid, desc, flt, sort, limit, expect in QUERIES:
        def run():
            c = coll.find(flt)
            if sort:
                c = c.sort(sort)
            if limit:
                c = c.limit(limit)
            return sum(1 for _ in c)
        for _ in range(WARMUP):
            run()
        times = []
        for rep in range(REPS):
            t = time.perf_counter(); nret = run(); ms = (time.perf_counter() - t) * 1000
            times.append(ms); raw.append([phase, qid, rep + 1, round(ms, 3), nret])
        cmd = {"find": config.COLLECTION, "filter": flt}
        if sort:
            cmd["sort"] = dict(sort)
        if limit:
            cmd["limit"] = limit
        ex = db.command({"explain": cmd, "verbosity": "executionStats"})
        (RES / "explain").mkdir(parents=True, exist_ok=True)
        (RES / "explain" / f"{phase}_{qid}.json").write_text(json.dumps(ex, indent=2, default=str))
        wp = ex["queryPlanner"]["winningPlan"]
        plan = " > ".join(stages(wp.get("queryPlan", wp)))
        es = ex["executionStats"]
        row = {"phase": phase, "query": qid, "description": desc, "plan": plan, "nReturned": es["nReturned"],
               "keysExamined": es["totalKeysExamined"], "docsExamined": es["totalDocsExamined"],
               "server_ms": es["executionTimeMillis"], "wall_median_ms": round(statistics.median(times), 2),
               "wall_p95_ms": round(sorted(times)[int(0.95 * REPS) - 1], 2), "wall_min_ms": round(min(times), 2)}
        summary.append(row)
        print(f"[{phase}] {qid} {desc:<46} plan={plan:<55} returned={row['nReturned']:>6,} "
              f"keys={row['keysExamined']:>7,} docs={row['docsExamined']:>7,} server={row['server_ms']:>4} ms "
              f"wall median={row['wall_median_ms']:>8.2f} ms p95={row['wall_p95_ms']:>8.2f} ms")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    RES.mkdir(exist_ok=True)
    client = MongoClient(config.MONGO_URI)
    db = client[config.DB_NAME]; coll = db[config.COLLECTION]
    print(f"collection {config.COLLECTION}: {coll.estimated_document_count():,} docs; reps={REPS}, warm-up={WARMUP}")
    coll.drop_indexes()                       # leaves only the mandatory _id index
    print("BEFORE: indexes =", [i["name"] for i in coll.list_indexes()])
    raw, summary = [], []
    run_phase(db, coll, "before", raw, summary)

    print("\ncreating indexes ...")
    builds = []
    for keys, opts, purpose in INDEXES:
        t = time.perf_counter(); name = coll.create_index(keys, **opts); s = time.perf_counter() - t
        builds.append({"index": name, "keys": json.dumps(keys), "options": json.dumps({k: v for k, v in opts.items() if k != 'name'}),
                       "purpose": purpose, "build_s": round(s, 2)})
        print(f"  {name:<22} {str(keys):<45} built in {s:5.2f} s  ({purpose})")
    st = next(coll.aggregate([{"$collStats": {"storageStats": {}}}]))["storageStats"]
    for b in builds:
        b["size_mb"] = round(st["indexSizes"].get(b["index"], 0) / 1e6, 2)
    print(f"index sizes MB: { {k: round(v / 1e6, 2) for k, v in st['indexSizes'].items()} }  "
          f"total={st['totalIndexSize'] / 1e6:.1f} MB vs data storage {st['storageSize'] / 1e6:.1f} MB")
    print("\nAFTER: indexes =", [i["name"] for i in coll.list_indexes()])
    run_phase(db, coll, "after", raw, summary)

    with open(RES / "benchmark_raw.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["phase", "query", "rep", "wall_ms", "nReturned"]); w.writerows(raw)
    with open(RES / "benchmark_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
    with open(RES / "index_build.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(builds[0])); w.writeheader(); w.writerows(builds)

    print("\nSUMMARY (ratio = before / after; >1 means faster after indexing)")
    b = {r["query"]: r for r in summary if r["phase"] == "before"}
    for r in (r for r in summary if r["phase"] == "after"):
        q = b[r["query"]]
        same = "same results" if q["nReturned"] == r["nReturned"] else "RESULT COUNT DIFFERS!"
        print(f"  {r['query']}  docs examined {q['docsExamined']:>7,} -> {r['docsExamined']:>7,}   "
              f"median {q['wall_median_ms']:>8.2f} -> {r['wall_median_ms']:>7.2f} ms  "
              f"(x{q['wall_median_ms'] / r['wall_median_ms']:.1f})   {same}")


if __name__ == "__main__":
    main()
