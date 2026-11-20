"""
Activity 4 - schema validation demo: MongoDB is schema-flexible, but the
collection validator still enforces consistency of the core fields.
Each attempted write prints ACCEPTED or REJECTED with the server's reason.
The one accepted test document is deleted at the end so the catalog is unchanged.
"""
import argparse
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, WriteError

import config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

NOW = datetime.now(timezone.utc)
VALID = {"sku": "SKU-9000001", "name": "Demo Wireless Earbuds", "brand": "boAt", "department": "Electronics",
         "category": "Headphones", "price": 1499.0, "mrp": 2999.0, "currency": "INR",
         "specs": {"type": "in-ear", "wireless": True, "anc": False, "battery_h": 30},
         "ratings": {"avg": 0.0, "count": 0},
         "inventory": {"stock": 50, "warehouse": "BLR-1", "reorder_level": 10},
         "status": "active", "tags": ["new"], "created_at": NOW, "updated_at": NOW}


def reason(e):
    d = getattr(e, "details", {}) or {}
    info = d.get("errInfo", {}).get("details", {})
    if not info:
        return d.get("errmsg", str(e))[:160]
    # walk MongoDB's structured validation error and report each failing leaf rule with its field path
    parts = []

    def walk(node, path):
        if isinstance(node, list):
            for x in node:
                walk(x, path)
            return
        if not isinstance(node, dict):
            return
        op = node.get("operatorName")
        if op == "required":
            parts.append(f"{path or 'document'}: missing required {node.get('missingProperties')}")
        elif op == "$expr":
            parts.append(f"$expr {node.get('specifiedAs', {}).get('$expr')} -> {node.get('reason')}")
        elif op in ("minimum", "maximum", "enum", "bsonType", "pattern", "minLength"):
            parts.append(f"{path}: {op} {node.get('specifiedAs')} (got {node.get('consideredValue', node.get('consideredType'))})")
        for p in node.get("propertiesNotSatisfied", []):
            walk(p.get("details", []), f"{path}.{p['propertyName']}".strip("."))
        for k in ("details", "schemaRulesNotSatisfied", "clausesNotSatisfied"):
            if k in node:
                walk(node[k], path)

    walk(info, "")
    return " | ".join(parts) or str(info)[:200]


def attempt(coll, label, fn):
    try:
        fn()
        print(f"ACCEPTED  {label}")
        return True
    except (WriteError, DuplicateKeyError) as e:
        print(f"REJECTED  {label}\n          code={e.code} -> {reason(e)}")
        return False


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    coll = MongoClient(config.MONGO_URI)[config.DB_NAME][config.COLLECTION]
    before = coll.count_documents({})
    print(f"documents before demo: {before:,}\n")

    def bad(**changes):
        d = copy.deepcopy(VALID)
        for k, v in changes.items():
            if v is None:
                d.pop(k, None)
            elif "." in k:
                o, i = k.split("."); d[o][i] = v
            else:
                d[k] = v
        return d

    attempt(coll, "1. negative price (price = -10)", lambda: coll.insert_one(bad(price=-10.0)))
    attempt(coll, "2. missing required field 'sku'", lambda: coll.insert_one(bad(sku=None)))
    attempt(coll, "3. status not in enum ('sold-out')", lambda: coll.insert_one(bad(status="sold-out")))
    attempt(coll, "4. negative stock (inventory.stock = -5)", lambda: coll.insert_one(bad(**{"inventory.stock": -5})))
    attempt(coll, "5. price greater than MRP (cross-field $expr rule)", lambda: coll.insert_one(bad(price=3999.0)))
    attempt(coll, "6. price stored as a string ('1499')", lambda: coll.insert_one(bad(price="1499")))
    print()
    flexible = bad(sustainability={"recycled_packaging": True, "carbon_g": 420},
                   specs={"type": "in-ear", "wireless": True, "anc": False, "battery_h": 30,
                          "bluetooth_version": "5.3", "ip_rating": "IPX5"})
    attempt(coll, "7. valid product with NEW attributes (sustainability, specs.bluetooth_version, specs.ip_rating) "
                  "- no schema migration needed", lambda: coll.insert_one(flexible))
    attempt(coll, "8. duplicate SKU (same sku inserted again) - unique index", lambda: coll.insert_one(bad(sku="SKU-9000001")))
    attempt(coll, "9. UPDATE that breaks the schema ($set price = -1) - validation applies to updates too",
            lambda: coll.update_one({"sku": "SKU-9000001"}, {"$set": {"price": -1.0}}))
    attempt(coll, "10. valid UPDATE ($set price = 1299, $inc stock -2)",
            lambda: coll.update_one({"sku": "SKU-9000001"}, {"$set": {"price": 1299.0}, "$inc": {"inventory.stock": -2}}))
    doc = coll.find_one({"sku": "SKU-9000001"}, {"_id": 0, "sku": 1, "price": 1, "inventory.stock": 1, "sustainability": 1})
    print(f"\nstored test document: {doc}")
    coll.delete_one({"sku": "SKU-9000001"})
    print(f"test document removed; documents after demo: {coll.count_documents({}):,} (unchanged: {coll.count_documents({}) == before})")


if __name__ == "__main__":
    main()
