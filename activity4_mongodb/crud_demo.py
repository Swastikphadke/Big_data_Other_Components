"""
Activity 4 - CRUD operations and aggregation reports on the product catalog.
Run after benchmark.py (indexes exist). Every step prints the operation, its
result, and for selected reads the winning plan from explain().
Aggregation results are also saved to results/agg_*.csv for charts.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from bson import ObjectId
from pymongo import MongoClient, ReturnDocument

import config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

RES = Path(__file__).parent / "results"
NOW = lambda: datetime.now(timezone.utc)


def show(title):
    print("\n" + "=" * 100 + f"\n{title}\n" + "=" * 100)


def j(x):
    return json.dumps(x, default=str, indent=None)


def plan(coll, flt, sort=None, limit=0, projection=None):
    c = coll.find(flt, projection)
    if sort:
        c = c.sort(sort)
    if limit:
        c = c.limit(limit)
    ex = c.explain()
    wp = ex["queryPlanner"]["winningPlan"]; wp = wp.get("queryPlan", wp)
    out, n = [], wp
    while n:
        out.append(n["stage"] + (f"[{n['indexName']}]" if "indexName" in n else ""))
        n = n.get("inputStage") or (n.get("inputStages") or [None])[0]
    es = ex["executionStats"]
    return f"plan: {' > '.join(out)}   keysExamined={es['totalKeysExamined']} docsExamined={es['totalDocsExamined']}"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    coll = MongoClient(config.MONGO_URI)[config.DB_NAME][config.COLLECTION]
    print(f"products: {coll.count_documents({}):,}   indexes: {[i['name'] for i in coll.list_indexes()]}")

    # ------------------------------------------------------------------ CREATE
    show("C1  insert_one - a new smartphone")
    phone = {"sku": "SKU-9100001", "name": "OnePlus Nord 99 5G (12GB/256GB)", "brand": "OnePlus",
             "department": "Electronics", "category": "Smartphones", "price": 29999.0, "mrp": 34999.0, "currency": "INR",
             "specs": {"ram_gb": 12, "storage_gb": 256, "screen_in": 6.7, "battery_mah": 5500, "os": "Android", "five_g": True},
             "ratings": {"avg": 0.0, "count": 0}, "inventory": {"stock": 120, "warehouse": "BLR-1", "reorder_level": 20},
             "status": "active", "tags": ["new"], "created_at": NOW(), "updated_at": NOW()}
    new_id = coll.insert_one(phone).inserted_id
    print("inserted _id:", new_id)

    show("C2  insert_many - three products with DIFFERENT shapes in one call")
    many = [
        {"sku": "SKU-9100002", "name": "Allen Solly Men Slim Fit Cotton Shirt", "brand": "Allen Solly", "department": "Fashion",
         "category": "Apparel", "price": 1299.0, "mrp": 1999.0, "currency": "INR", "specs": {"material": "Cotton", "fit": "Slim", "gender": "Men"},
         "variants": [{"size": "M", "color": "Navy", "stock": 12}, {"size": "L", "color": "Navy", "stock": 0}],
         "ratings": {"avg": 0.0, "count": 0}, "inventory": {"stock": 12, "warehouse": "MUM-2", "reorder_level": 10},
         "status": "active", "tags": ["new"], "created_at": NOW(), "updated_at": NOW()},
        {"sku": "SKU-9100003", "name": "The Data Monsoon (Paperback)", "brand": "Penguin", "department": "Books", "category": "Books",
         "price": 399.0, "mrp": 499.0, "currency": "INR", "specs": {"author": "M. Iyer", "isbn": "978-81-12345-678-9", "pages": 312,
                                                                    "language": "English", "format": "Paperback"},
         "ratings": {"avg": 0.0, "count": 0}, "inventory": {"stock": 40, "warehouse": "DEL-1", "reorder_level": 5},
         "status": "active", "tags": ["new"], "created_at": NOW(), "updated_at": NOW()},
        {"sku": "SKU-9100004", "name": "Tata Masala Mix 250g", "brand": "Tata", "department": "Grocery", "category": "Groceries",
         "price": 89.0, "mrp": 99.0, "currency": "INR", "specs": {"weight_g": 250, "veg": True, "shelf_life_days": 180},
         "ratings": {"avg": 0.0, "count": 0}, "inventory": {"stock": 300, "warehouse": "HYD-1", "reorder_level": 50},
         "status": "active", "tags": ["new", "budget"], "created_at": NOW(), "updated_at": NOW()},
    ]
    print("inserted:", len(coll.insert_many(many).inserted_ids), "documents")

    # ------------------------------------------------------------------ READ
    show("R1  find by _id")
    print(j(coll.find_one({"_id": ObjectId(new_id)}, {"_id": 1, "sku": 1, "name": 1, "price": 1})))
    show("R2  find by SKU (unique index)")
    print(j(coll.find_one({"sku": "SKU-0123456"}, {"_id": 0, "sku": 1, "name": 1, "category": 1, "price": 1, "inventory": 1})))
    print(plan(coll, {"sku": "SKU-0123456"}))

    show("R3  category + price range: Laptops 50,000-80,000 INR with rating >= 4.5, cheapest first (top 5)")
    f3 = {"category": "Laptops", "price": {"$gte": 50000, "$lte": 80000}, "ratings.avg": {"$gte": 4.5}}
    for d in coll.find(f3, {"_id": 0, "sku": 1, "name": 1, "price": 1, "ratings.avg": 1}).sort("price", 1).limit(5):
        print(" ", j(d))
    print(" ", plan(coll, f3, [("price", 1)], 5))

    show("R4  query INSIDE nested specs: 5G Smartphones with >= 12 GB RAM under 30,000 INR")
    f4 = {"category": "Smartphones", "specs.ram_gb": {"$gte": 12}, "specs.five_g": True, "price": {"$lt": 30000}}
    print("matching:", coll.count_documents(f4))
    for d in coll.find(f4, {"_id": 0, "name": 1, "price": 1, "specs.ram_gb": 1}).sort("price", 1).limit(3):
        print(" ", j(d))

    show("R5  query INSIDE an embedded array: Apparel with size M in Black, in stock ($elemMatch)")
    f5 = {"category": "Apparel", "variants": {"$elemMatch": {"size": "M", "color": "Black", "stock": {"$gt": 0}}}}
    print("matching:", coll.count_documents(f5))
    print(" ", j(coll.find_one(f5, {"_id": 0, "name": 1, "variants": {"$elemMatch": {"size": "M", "color": "Black"}}})))

    show("R6  full-text search: 'wireless noise cancelling' ranked by text score (text index)")
    f6 = {"$text": {"$search": "wireless noise cancelling"}}
    for d in coll.find(f6, {"_id": 0, "name": 1, "price": 1, "score": {"$meta": "textScore"}}).sort(
            [("score", {"$meta": "textScore"})]).limit(3):
        print(" ", j(d))
    print(" ", plan(coll, f6, limit=3))

    show("R7  tags array: products tagged BOTH 'premium' and 'bestseller' ($all)")
    print("matching:", coll.count_documents({"tags": {"$all": ["premium", "bestseller"]}}))

    # ------------------------------------------------------------------ UPDATE
    show("U1  stock update on a sale - atomic conditional decrement (never oversells)")
    sku = "SKU-9100001"
    d = coll.find_one_and_update({"sku": sku, "inventory.stock": {"$gte": 3}},
                                 {"$inc": {"inventory.stock": -3}, "$currentDate": {"updated_at": True}},
                                 projection={"_id": 0, "sku": 1, "inventory.stock": 1}, return_document=ReturnDocument.AFTER)
    print("sold 3 ->", j(d))
    r = coll.update_one({"sku": sku, "inventory.stock": {"$gte": 500}}, {"$inc": {"inventory.stock": -500}})
    print(f"try to sell 500 -> matched={r.matched_count} modified={r.modified_count} (rejected: not enough stock)")

    show("U2  product details update - price change, new tag, timestamp")
    r = coll.update_one({"sku": sku}, {"$set": {"price": 27999.0}, "$addToSet": {"tags": "sale"}, "$currentDate": {"updated_at": True}})
    print(f"matched={r.matched_count} modified={r.modified_count} ->",
          j(coll.find_one({"sku": sku}, {"_id": 0, "price": 1, "mrp": 1, "tags": 1})))

    show("U3  update ONE element of an embedded array (arrayFilters) + recompute total stock (pipeline update)")
    s2 = "SKU-9100002"
    coll.update_one({"sku": s2}, {"$inc": {"variants.$[v].stock": 25}},
                    array_filters=[{"v.size": "L", "v.color": "Navy"}])
    coll.update_one({"sku": s2}, [{"$set": {"inventory.stock": {"$sum": "$variants.stock"}, "updated_at": "$$NOW"}}])
    print(j(coll.find_one({"sku": s2}, {"_id": 0, "variants": 1, "inventory.stock": 1})))

    show("U4  bulk restock - every ACTIVE product below 3 units gets +50 (update_many, partial index)")
    f8 = {"status": "active", "inventory.stock": {"$lt": 3}}
    print("  ", plan(coll, f8))
    print(f"   low-stock active products before: {coll.count_documents(f8):,}")
    r = coll.update_many(f8, {"$inc": {"inventory.stock": 50}, "$currentDate": {"updated_at": True}})
    print(f"   update_many matched={r.matched_count:,} modified={r.modified_count:,}; "
          f"low-stock after: {coll.count_documents(f8):,}")

    # ------------------------------------------------------------------ DELETE
    show("D1  delete discontinued products that have no stock left (delete_many)")
    disc = {"status": "discontinued"}
    print(f"   discontinued before: {coll.count_documents(disc):,} "
          f"(of which stock 0: {coll.count_documents({**disc, 'inventory.stock': 0}):,})")
    r = coll.delete_many({**disc, "inventory.stock": 0})
    print(f"   deleted {r.deleted_count:,}; discontinued items still holding stock (kept to sell off): "
          f"{coll.count_documents(disc):,}")
    show("D2  delete_many by SKU list - remove the demo products inserted above")
    r = coll.delete_many({"sku": {"$in": ["SKU-9100001", "SKU-9100002", "SKU-9100003", "SKU-9100004"]}})
    print(f"   deleted {r.deleted_count}; products now: {coll.count_documents({}):,}")

    # ------------------------------------------------------------------ AGGREGATION REPORTS
    RES.mkdir(exist_ok=True)
    show("A1  category report: products, average price, average rating, inventory value")
    a1 = list(coll.aggregate([
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$category", "products": {"$sum": 1}, "avg_price": {"$avg": "$price"},
                    "avg_rating": {"$avg": "$ratings.avg"}, "units": {"$sum": "$inventory.stock"},
                    "inventory_value": {"$sum": {"$multiply": ["$price", "$inventory.stock"]}}}},
        {"$sort": {"inventory_value": -1}}]))
    df = pd.DataFrame(a1).rename(columns={"_id": "category"}).round(2)
    print(df.to_string(index=False)); df.to_csv(RES / "agg_category_report.csv", index=False)

    show("A2  top 5 brands by average rating (brands with >= 1,000 active products)")
    a2 = list(coll.aggregate([{"$match": {"status": "active"}},
                              {"$group": {"_id": "$brand", "n": {"$sum": 1}, "avg_rating": {"$avg": "$ratings.avg"},
                                          "reviews": {"$sum": "$ratings.count"}}},
                              {"$match": {"n": {"$gte": 1000}}}, {"$sort": {"avg_rating": -1}}, {"$limit": 5}]))
    for x in a2:
        print(f"   {x['_id']:<14} products={x['n']:>6,} avg_rating={x['avg_rating']:.3f} reviews={x['reviews']:,}")

    show("A3  low-stock report per warehouse (active, stock <= reorder level)")
    a3 = list(coll.aggregate([{"$match": {"status": "active", "$expr": {"$lte": ["$inventory.stock", "$inventory.reorder_level"]}}},
                              {"$group": {"_id": "$inventory.warehouse", "low_stock_products": {"$sum": 1}}},
                              {"$sort": {"_id": 1}}]))
    df3 = pd.DataFrame(a3).rename(columns={"_id": "warehouse"}); print(df3.to_string(index=False))
    df3.to_csv(RES / "agg_low_stock_by_warehouse.csv", index=False)

    show("A4  Smartphone price bands ($bucket)")
    a4 = list(coll.aggregate([{"$match": {"category": "Smartphones", "status": "active"}},
                              {"$bucket": {"groupBy": "$price", "boundaries": [0, 15000, 30000, 50000, 80000, 200000],
                                           "default": "other", "output": {"phones": {"$sum": 1},
                                                                          "avg_rating": {"$avg": "$ratings.avg"}}}}]))
    df4 = pd.DataFrame(a4).rename(columns={"_id": "price_from"}).round(3); print(df4.to_string(index=False))
    df4.to_csv(RES / "agg_smartphone_price_bands.csv", index=False)


if __name__ == "__main__":
    main()
