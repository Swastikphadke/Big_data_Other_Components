"""
Activity 4 - create the `products` collection WITH schema validation and bulk-load
the synthetic catalog (data/products.jsonl.gz). No secondary indexes are created
here; indexing is part of benchmark.py so that before/after can be measured.
"""
import argparse
import gzip
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from pymongo import MongoClient

import config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

HERE = Path(__file__).parent
CATEGORIES = ["Smartphones", "Laptops", "Headphones", "Televisions", "Home Appliances", "Apparel",
              "Footwear", "Books", "Beauty", "Groceries", "Sports"]
NUM = ["double", "int", "long", "decimal"]
INT = ["int", "long"]

# Core fields are enforced; `specs` stays a free-form object (different per category)
# and additional top-level fields are allowed -> consistency AND flexibility.
PRODUCT_SCHEMA = {
    "bsonType": "object",
    "required": ["sku", "name", "brand", "category", "price", "mrp", "currency", "inventory", "status", "created_at"],
    "properties": {
        "sku": {"bsonType": "string", "pattern": "^SKU-[0-9]{7}$", "description": "SKU-nnnnnnn"},
        "name": {"bsonType": "string", "minLength": 3},
        "brand": {"bsonType": "string"},
        "department": {"bsonType": "string"},
        "category": {"enum": CATEGORIES},
        "price": {"bsonType": NUM, "minimum": 0},
        "mrp": {"bsonType": NUM, "minimum": 0},
        "currency": {"enum": ["INR"]},
        "specs": {"bsonType": "object"},
        "ratings": {"bsonType": "object", "properties": {
            "avg": {"bsonType": NUM, "minimum": 0, "maximum": 5},
            "count": {"bsonType": INT, "minimum": 0}}},
        "inventory": {"bsonType": "object", "required": ["stock", "warehouse"], "properties": {
            "stock": {"bsonType": INT, "minimum": 0},
            "warehouse": {"bsonType": "string"},
            "reorder_level": {"bsonType": INT, "minimum": 0}}},
        "status": {"enum": ["active", "discontinued"]},
        "tags": {"bsonType": "array", "items": {"bsonType": "string"}},
        "variants": {"bsonType": "array", "items": {"bsonType": "object", "required": ["size", "stock"],
                                                    "properties": {"stock": {"bsonType": INT, "minimum": 0}}}},
        "created_at": {"bsonType": "date"},
        "updated_at": {"bsonType": "date"},
    },
}
VALIDATOR = {"$and": [{"$jsonSchema": PRODUCT_SCHEMA},
                      {"$expr": {"$gte": ["$mrp", "$price"]}}]}   # business rule across two fields


def load_docs():
    with gzip.open(HERE / "data" / "products.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            d["created_at"] = datetime.fromisoformat(d["created_at"])
            d["updated_at"] = datetime.fromisoformat(d["updated_at"])
            yield d


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    client = MongoClient(config.MONGO_URI)
    db = client[config.DB_NAME]
    print(f"server version {client.server_info()['version']}  database={config.DB_NAME}")
    if config.COLLECTION in db.list_collection_names():
        db[config.COLLECTION].drop()
        print(f"dropped existing collection {config.COLLECTION}")
    db.create_collection(config.COLLECTION, validator=VALIDATOR, validationLevel="strict", validationAction="error")
    info = db.command("listCollections", filter={"name": config.COLLECTION})["cursor"]["firstBatch"][0]["options"]
    print(f"created collection with validationLevel={info['validationLevel']} validationAction={info['validationAction']}")
    print("required fields:", PRODUCT_SCHEMA["required"])

    coll = db[config.COLLECTION]
    t0, batch, n = time.perf_counter(), [], 0
    for d in load_docs():
        batch.append(d)
        if len(batch) == 5000:
            n += len(coll.insert_many(batch, ordered=False).inserted_ids); batch = []
    if batch:
        n += len(coll.insert_many(batch, ordered=False).inserted_ids)
    dt = time.perf_counter() - t0
    print(f"inserted {n:,} documents in {dt:.1f} s ({n / dt:,.0f} docs/s) via insert_many batches of 5,000")

    st = next(coll.aggregate([{"$collStats": {"storageStats": {}}}]))["storageStats"]
    print(f"count={st['count']:,}  data size={st['size'] / 1e6:.1f} MB  avg document={st['avgObjSize']} B  "
          f"storage (compressed)={st['storageSize'] / 1e6:.1f} MB  indexes={list(st['indexSizes'])}")
    print("documents per category:")
    for r in coll.aggregate([{"$group": {"_id": "$category", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}]):
        print(f"  {r['_id']:<16} {r['n']:>7,}")
    print("distinct top-level field sets (schema flexibility):")
    for r in coll.aggregate([{"$project": {"k": {"$map": {"input": {"$objectToArray": "$specs"}, "in": "$$this.k"}},
                                            "c": "$category", "v": {"$cond": [{"$isArray": "$variants"}, 1, 0]}}},
                             {"$group": {"_id": {"c": "$c", "k": "$k", "v": "$v"}}}, {"$group": {"_id": "$_id.c", "shapes": {"$sum": 1},
                              "example_specs": {"$first": "$_id.k"}, "variants": {"$max": "$_id.v"}}}, {"$sort": {"_id": 1}}]):
        print(f"  {r['_id']:<16} specs keys={r['example_specs']}  embedded variants={'yes' if r['variants'] else 'no'}")


if __name__ == "__main__":
    main()
