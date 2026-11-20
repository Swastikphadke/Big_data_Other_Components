"""
Activity 4 - synthetic e-commerce product catalog (SYNTHETIC DATA).

200,000 products in 11 categories. Every product shares a common core
(sku, name, brand, category, price, ratings, inventory, status, tags, timestamps)
but `specs` differs completely between categories, and apparel/footwear embed an
array of size/colour `variants` - the kind of heterogeneous data a document
model stores naturally.

Writes data/products.jsonl.gz (all documents), data/sample_products.json
(one example per category) and data/catalog_stats.json.
"""
import argparse
import gzip
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from config import N_PRODUCTS, SEED

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

DATA = Path(__file__).parent / "data"
rng = np.random.default_rng(SEED)

# category: (department, share, price range INR, brands)
CATS = {
    "Smartphones":     ("Electronics", .08, (7999, 149999), ["Samsung", "Apple", "OnePlus", "Xiaomi", "Realme", "Vivo", "Oppo", "Motorola", "Google"]),
    "Laptops":         ("Electronics", .05, (27999, 249999), ["Dell", "HP", "Lenovo", "Asus", "Acer", "Apple", "MSI"]),
    "Headphones":      ("Electronics", .07, (599, 34999), ["Sony", "boAt", "JBL", "Sennheiser", "Bose", "Noise", "Skullcandy"]),
    "Televisions":     ("Electronics", .03, (11999, 249999), ["Samsung", "LG", "Sony", "TCL", "Xiaomi", "OnePlus"]),
    "Home Appliances": ("Home", .07, (2499, 89999), ["LG", "Whirlpool", "Samsung", "Bosch", "IFB", "Godrej", "Haier"]),
    "Apparel":         ("Fashion", .20, (299, 4999), ["Levi's", "Allen Solly", "H&M", "Zara", "Peter England", "Biba", "FabIndia", "Roadster"]),
    "Footwear":        ("Fashion", .10, (499, 14999), ["Nike", "Adidas", "Puma", "Bata", "Woodland", "Skechers", "Red Tape"]),
    "Books":           ("Books", .18, (149, 2499), ["Penguin", "HarperCollins", "Rupa", "Bloomsbury", "Scholastic", "Pearson", "Arihant"]),
    "Beauty":          ("Beauty", .10, (99, 4999), ["Lakme", "Maybelline", "Nivea", "Himalaya", "Mamaearth", "L'Oreal", "Biotique"]),
    "Groceries":       ("Grocery", .08, (25, 1499), ["Tata", "Aashirvaad", "Amul", "Fortune", "Nestle", "MTR", "Haldiram's"]),
    "Sports":          ("Sports", .04, (199, 29999), ["Decathlon", "Yonex", "Cosco", "Nivia", "SG", "Li-Ning"]),
}
SERIES = {  # (category, brand) -> model series, so names stay plausible
    "Smartphones": {"Samsung": ["Galaxy S", "Galaxy A", "Galaxy M"], "Apple": ["iPhone"], "OnePlus": ["Nord", "Nord CE", "Open"],
                    "Xiaomi": ["Redmi Note", "Redmi"], "Realme": ["Narzo", "GT"], "Vivo": ["V", "Y", "T"],
                    "Oppo": ["Reno", "A", "F"], "Motorola": ["Edge", "Moto G"], "Google": ["Pixel"]},
    "Laptops": {"Dell": ["Inspiron", "Vostro", "XPS"], "HP": ["Pavilion", "Victus", "EliteBook"],
                "Lenovo": ["IdeaPad", "ThinkPad", "Legion"], "Asus": ["VivoBook", "ZenBook", "TUF"],
                "Acer": ["Aspire", "Nitro", "Swift"], "Apple": ["MacBook Air", "MacBook Pro"], "MSI": ["Katana", "Modern"]},
    "Headphones": {"Sony": ["WH-1000XM", "WF-C"], "boAt": ["Rockerz", "Airdopes"], "JBL": ["Tune", "Live"],
                   "Sennheiser": ["HD", "Momentum"], "Bose": ["QuietComfort"], "Noise": ["Buds", "Air Buds"],
                   "Skullcandy": ["Crusher", "Hesh"]},
}
SPORT_ITEMS = {"Racket": (499, 14999), "Bat": (799, 24999), "Ball": (149, 1499), "Yoga Mat": (299, 2999),
               "Dumbbell Set": (999, 9999), "Shoes": (1499, 12999), "Shuttlecocks": (199, 1999)}
SPORT_OF = {"Cricket": ["Bat", "Ball"], "Badminton": ["Racket", "Shuttlecocks"], "Football": ["Ball", "Shoes"],
            "Fitness": ["Yoga Mat", "Dumbbell Set"], "Running": ["Shoes"]}
WAREHOUSES = ["BLR-1", "MUM-2", "DEL-1", "HYD-1", "CHN-1"]
COLORS = ["Black", "White", "Navy", "Grey", "Olive", "Maroon", "Beige", "Blue"]
BOOK_WORDS = ["Silent", "River", "Code", "Empire", "Midnight", "Garden", "Data", "Monsoon", "Journey", "Algorithms",
              "Stars", "Ocean", "Machine", "Learning", "History", "City", "Secret", "Mind", "Physics", "Kingdom"]
AUTHORS = ["R. K. Narayan", "Chetan Bhagat", "Amish Tripathi", "Sudha Murty", "Ruskin Bond", "A. Sharma",
           "J. Smith", "M. Iyer", "K. Rao", "P. Menon", "S. Gupta", "T. Thomas"]


def r(a, b):
    return float(rng.uniform(a, b))


def pick(seq):
    return seq[int(rng.integers(len(seq)))]


def specs_for(cat, brand):
    if cat == "Smartphones":
        return {"ram_gb": int(pick([4, 6, 8, 12, 16])), "storage_gb": int(pick([64, 128, 256, 512])),
                "screen_in": round(r(6.1, 6.9), 1), "battery_mah": int(pick([4000, 4500, 5000, 5500, 6000])),
                "os": "iOS" if brand == "Apple" else "Android", "five_g": bool(rng.random() < .7)}
    if cat == "Laptops":
        return {"cpu": "Apple M3" if brand == "Apple" else pick(["Intel Core i5", "Intel Core i7", "AMD Ryzen 5", "AMD Ryzen 7"]),
                "ram_gb": int(pick([8, 16, 32])), "storage_gb": int(pick([256, 512, 1024])),
                "screen_in": float(pick([13.3, 14.0, 15.6, 16.0])),
                "gpu": pick(["Integrated", "RTX 3050", "RTX 4050", "RTX 4060"]), "weight_kg": round(r(1.1, 2.5), 2)}
    if cat == "Headphones":
        return {"type": pick(["over-ear", "on-ear", "in-ear"]), "wireless": bool(rng.random() < .75),
                "anc": bool(rng.random() < .4), "battery_h": int(rng.integers(8, 61))}
    if cat == "Televisions":
        size = int(pick([32, 43, 50, 55, 65, 75]))
        panel = "OLED" if brand in ("LG", "Sony") and size >= 55 and rng.random() < .4 else             ("QLED" if brand in ("Samsung", "TCL", "OnePlus") and size >= 50 and rng.random() < .5 else "LED")
        res = "HD" if size == 32 else ("Full HD" if size == 43 and rng.random() < .5 else "4K")
        return {"screen_in": size, "resolution": res, "panel": panel, "smart_tv": True}
    if cat == "Home Appliances":
        kind = pick(["Refrigerator", "Washing Machine", "Microwave", "Air Conditioner", "Water Purifier"])
        cap = {"Refrigerator": (pick([190, 250, 340, 470, 600]), "litres"), "Washing Machine": (pick([6, 7, 8, 9, 10]), "kg"),
               "Microwave": (pick([20, 25, 28, 32]), "litres"), "Air Conditioner": (pick([1.0, 1.5, 2.0]), "ton"),
               "Water Purifier": (pick([6, 7, 8, 10]), "litres")}[kind]
        return {"appliance": kind, "capacity": cap[0], "capacity_unit": cap[1], "energy_star": int(rng.integers(2, 6)),
                "warranty_years": int(pick([1, 2, 5, 10]))}
    if cat in ("Apparel", "Footwear"):
        return {"material": pick(["Cotton", "Polyester", "Linen", "Denim", "Leather", "Mesh"]),
                "fit" if cat == "Apparel" else "type": pick(["Slim", "Regular", "Relaxed"]) if cat == "Apparel"
                else pick(["Running", "Casual", "Formal", "Sandals"]),
                "gender": pick(["Men", "Women", "Unisex"])}
    if cat == "Books":
        return {"author": pick(AUTHORS), "isbn": f"978-81-{rng.integers(10000, 99999)}-{rng.integers(100, 999)}-{rng.integers(0, 9)}",
                "pages": int(rng.integers(96, 900)), "language": pick(["English", "English", "Hindi", "Kannada", "Tamil"]),
                "format": pick(["Paperback", "Hardcover", "Kindle"])}
    if cat == "Beauty":
        return {"volume_ml": int(pick([30, 50, 100, 200, 400])), "skin_type": pick(["All", "Oily", "Dry", "Sensitive"]),
                "cruelty_free": bool(rng.random() < .5)}
    if cat == "Groceries":
        return {"weight_g": int(pick([100, 250, 500, 1000, 5000])), "veg": bool(rng.random() < .9),
                "shelf_life_days": int(pick([30, 90, 180, 365]))}
    sport = pick(list(SPORT_OF))
    return {"sport": sport, "item": pick(SPORT_OF[sport]), "weight_kg": round(r(.1, 12), 2)}


def name_for(cat, brand, specs, i):
    if cat in ("Smartphones", "Laptops", "Headphones", "Televisions"):
        base = f"{brand} {pick(SERIES.get(cat, {}).get(brand, [brand]))} {rng.integers(10, 99)}"
        if cat == "Smartphones":
            return f"{base}{' 5G' if specs['five_g'] else ''} ({specs['ram_gb']}GB/{specs['storage_gb']}GB)"
        if cat == "Laptops":
            return f"{base} {specs['cpu']} {specs['ram_gb']}GB {specs['storage_gb']}GB SSD"
        if cat == "Headphones":
            return f"{base} {'Wireless ' if specs['wireless'] else ''}{'Noise Cancelling ' if specs['anc'] else ''}{specs['type'].title()} {'Earbuds' if specs['type'] == 'in-ear' else 'Headphones'}"
        return f"{brand} {specs['screen_in']}-inch {specs['resolution']} {specs['panel']} Smart TV {rng.integers(10, 99)}"
    if cat == "Home Appliances":
        unit = {"litres": "L", "kg": " kg", "ton": " Ton"}[specs["capacity_unit"]]
        return f"{brand} {specs['appliance']} {specs['capacity']:g}{unit} {specs['energy_star']}-Star"
    if cat == "Apparel":
        return f"{brand} {specs['gender']} {specs['fit']} Fit {specs['material']} {pick(['T-Shirt', 'Shirt', 'Jeans', 'Kurta', 'Chinos'])}"
    if cat == "Footwear":
        return f"{brand} {specs['gender']} {specs['type']} {pick(['Shoes', 'Sneakers', 'Loafers', 'Slides'])}"
    if cat == "Books":
        return f"The {pick(BOOK_WORDS)} {pick(BOOK_WORDS)} ({specs['format']})"
    if cat == "Beauty":
        return f"{brand} {pick(['Face Wash', 'Moisturiser', 'Sunscreen SPF 50', 'Shampoo', 'Lipstick', 'Serum'])} {specs['volume_ml']}ml"
    if cat == "Groceries":
        return f"{brand} {pick(['Basmati Rice', 'Atta', 'Ghee', 'Masala Mix', 'Tea', 'Namkeen', 'Oats'])} {specs['weight_g']}g"
    return f"{brand} {specs['sport']} {specs['item']}"


def main():
    DATA.mkdir(exist_ok=True)
    cats = list(CATS)
    shares = np.array([CATS[c][1] for c in cats]); shares /= shares.sum()
    cat_idx = rng.choice(len(cats), N_PRODUCTS, p=shares)
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    stats, samples = Counter(), {}
    with gzip.open(DATA / "products.jsonl.gz", "wt", encoding="utf-8") as f:
        for i in range(N_PRODUCTS):
            cat = cats[cat_idx[i]]
            dept, _, (lo, hi), brands = CATS[cat]
            brand = pick(brands)
            specs = specs_for(cat, brand)
            if cat == "Sports":
                lo, hi = SPORT_ITEMS[specs["item"]]
            if cat == "Televisions":   # price scales with screen size
                lo, hi = {32: (9999, 24999), 43: (19999, 49999), 50: (29999, 69999), 55: (34999, 149999),
                          65: (54999, 249999), 75: (89999, 349999)}[specs["screen_in"]]
            price = round(float(np.exp(rng.uniform(np.log(lo), np.log(hi)))), -1) - 1   # log-uniform, ends in 9
            created = t0 + timedelta(minutes=int(rng.integers(0, 60 * 24 * 300)))
            doc = {
                "sku": f"SKU-{i + 1:07d}",
                "name": name_for(cat, brand, specs, i),
                "brand": brand, "department": dept, "category": cat,
                "price": float(price), "mrp": float(round(price * r(1.0, 1.4), -1)), "currency": "INR",
                "specs": specs,
                "ratings": {"avg": round(float(np.clip(rng.normal(4.0, 0.5), 1, 5)), 1),
                            "count": int(rng.lognormal(4, 1.5))},
                "inventory": {"stock": int(rng.negative_binomial(2, 0.06)), "warehouse": pick(WAREHOUSES),
                              "reorder_level": int(pick([5, 10, 20]))},
                "status": "discontinued" if rng.random() < 0.03 else "active",
                "tags": sorted({pick(["bestseller", "new", "sale", "eco", "premium", "budget", "gift"])
                                for _ in range(int(rng.integers(1, 4)))}),
                "created_at": created.isoformat(), "updated_at": created.isoformat(),
            }
            if cat in ("Apparel", "Footwear"):
                sizes = ["S", "M", "L", "XL", "XXL"] if cat == "Apparel" else ["6", "7", "8", "9", "10", "11"]
                doc["variants"] = [{"size": s, "color": c, "stock": int(rng.integers(0, 40))}
                                   for s in sizes for c in rng.choice(COLORS, 2, replace=False).tolist()]
                doc["inventory"]["stock"] = sum(v["stock"] for v in doc["variants"])
            if doc["status"] == "discontinued" and rng.random() < 0.6:
                doc["inventory"]["stock"] = 0
            f.write(json.dumps(doc) + "\n")
            stats[cat] += 1
            samples.setdefault(cat, doc)
    (DATA / "sample_products.json").write_text(json.dumps(list(samples.values()), indent=2))
    (DATA / "catalog_stats.json").write_text(json.dumps({"seed": SEED, "n": N_PRODUCTS, "by_category": stats}, indent=2))
    size = (DATA / "products.jsonl.gz").stat().st_size / 1e6
    print(f"generated {N_PRODUCTS:,} products (seed {SEED}) -> data/products.jsonl.gz ({size:.1f} MB gzip)")
    print("by category:", dict(stats))


if __name__ == "__main__":
    _ap = argparse.ArgumentParser(); _ap.add_argument("--log"); teelog.start(_ap.parse_args().log)
    main()
