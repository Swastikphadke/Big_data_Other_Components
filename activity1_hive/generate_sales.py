"""
Activity 1 - Synthetic supermarket sales generator.

Produces line-item sales records for a fictional 6-branch supermarket chain
for calendar year 2025.  The data is SYNTHETIC: every pattern in it was
planted deliberately by the rules below and is recorded in
data/planted_patterns.json so that the Hive analysis can be checked against
a known ground truth.

Usage:
    python generate_sales.py                 # default ~500k line items
    python generate_sales.py --invoices 50000 # smaller test run
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
YEAR = 2025
OUT_DIR = Path(__file__).parent / "data"

# ---------------------------------------------------------------- branches
# (branch_id, branch_name, city, relative footfall weight)
BRANCHES = [
    ("B01", "Jayanagar",  "Bengaluru", 1.60),
    ("B02", "Whitefield", "Bengaluru", 1.35),
    ("B03", "Kuvempunagar", "Mysuru",  1.00),
    ("B04", "Vidyanagar", "Hubballi",  0.80),
    ("B05", "Kadri",      "Mangaluru", 0.75),
    ("B06", "Gokulam",    "Mysuru",    0.55),
]

# ---------------------------------------------------------------- catalog
# category -> (price range INR, list of product names)
CATALOG = {   # category -> [(product name, MRP in INR)]
    "Staples": [("Sona Masoori Rice 5kg", 365), ("Basmati Rice 1kg", 155), ("Wheat Atta 5kg", 245),
        ("Toor Dal 1kg", 165), ("Moong Dal 1kg", 140), ("Sugar 1kg", 48), ("Iodised Salt 1kg", 28),
        ("Sunflower Oil 1L", 150), ("Groundnut Oil 1L", 210), ("Ragi Flour 1kg", 75), ("Rava 1kg", 62),
        ("Poha 500g", 45)],
    "Dairy": [("Toned Milk 500ml", 27), ("Curd 500g", 35), ("Paneer 200g", 95), ("Butter 100g", 58),
        ("Ghee 500ml", 345), ("Cheese Slices 200g", 140), ("Buttermilk 200ml", 15),
        ("Flavoured Milk 180ml", 30), ("Fresh Cream 200ml", 70), ("Milk Powder 500g", 235),
        ("Greek Yogurt 100g", 50), ("Khova 250g", 120)],
    "Fruits & Vegetables": [("Tomato 1kg", 40), ("Onion 1kg", 45), ("Potato 1kg", 38),
        ("Banana Robusta 1 dozen", 60), ("Apple Shimla 1kg", 180), ("Carrot 500g", 35),
        ("Coriander Bunch", 15), ("Green Chilli 250g", 20), ("Mango Alphonso 1kg", 250),
        ("Watermelon 1pc", 80), ("Cucumber 500g", 25), ("Lemon 250g", 30)],
    "Beverages": [("Filter Coffee Powder 500g", 285), ("Tea Leaves 500g", 260), ("Cola 750ml", 40),
        ("Orange Juice 1L", 120), ("Mineral Water 1L", 20), ("Energy Drink 250ml", 125),
        ("Lemon Soda 500ml", 30), ("Coconut Water 200ml", 45), ("Green Tea 25 bags", 160),
        ("Health Drink 500g", 255), ("Mango Drink 600ml", 38), ("Iced Tea 300ml", 50)],
    "Snacks": [("Potato Chips 52g", 20), ("Banana Chips 200g", 90), ("Mixture 400g", 110),
        ("Cream Biscuits 150g", 35), ("Marie Biscuits 250g", 40), ("Instant Noodles 70g", 15),
        ("Chocolate Bar 40g", 50), ("Peanut Chikki 100g", 30), ("Popcorn 90g", 45),
        ("Cookies 200g", 70), ("Murukku 200g", 60), ("Nachos 150g", 85)],
    "Frozen & Ice Cream": [("Vanilla Ice Cream 1L", 220), ("Chocolate Cone", 45), ("Kulfi Stick", 30),
        ("Frozen Peas 500g", 110), ("Frozen Parotta 5pc", 95), ("Mango Ice Cream 700ml", 190),
        ("Frozen Nuggets 400g", 245), ("Ice Cream Cup 100ml", 30), ("Frozen Corn 500g", 120),
        ("Fruit Bar", 40)],
    "Sweets & Dry Fruits": [("Mysore Pak 500g", 280), ("Kaju Katli 250g", 350), ("Almonds 500g", 520),
        ("Cashew 500g", 560), ("Raisins 250g", 140), ("Dates 500g", 210), ("Gulab Jamun Tin 1kg", 240),
        ("Dry Fruit Gift Box", 950), ("Pista 250g", 420), ("Soan Papdi 500g", 150)],
    "Personal Care": [("Bath Soap 4x100g", 160), ("Shampoo 340ml", 320), ("Toothpaste 150g", 110),
        ("Hair Oil 200ml", 130), ("Face Wash 100ml", 175), ("Body Lotion 400ml", 365),
        ("Deodorant 150ml", 225), ("Sanitary Pads 20pc", 190), ("Shaving Foam 200g", 210),
        ("Toothbrush 2pc", 75), ("Sunscreen 50ml", 299)],
    "Household": [("Detergent Powder 1kg", 125), ("Dishwash Liquid 750ml", 155),
        ("Floor Cleaner 1L", 199), ("Toilet Cleaner 500ml", 105), ("Garbage Bags 30pc", 99),
        ("Agarbatti Pack", 60), ("Camphor 100g", 85), ("Mosquito Repellent Refill", 89),
        ("Scrub Pad 3pc", 45), ("Aluminium Foil 9m", 120), ("Diya Set 12pc", 150)],
    "Baby & Kids": [("Baby Diapers M 40pc", 699), ("Baby Wipes 72pc", 199), ("Baby Food 300g", 285),
        ("Baby Shampoo 200ml", 225), ("Kids Toothpaste 80g", 65), ("Baby Powder 200g", 170),
        ("Feeding Bottle", 349), ("Baby Oil 200ml", 210)],
}

# How often a category appears in baskets (relative).  Daily-need items dominate.
CATEGORY_FREQ = {
    "Dairy": 1.8, "Fruits & Vegetables": 1.6, "Staples": 1.3, "Snacks": 1.2,
    "Beverages": 1.0, "Personal Care": 0.8, "Household": 0.8,
    "Frozen & Ice Cream": 0.6, "Sweets & Dry Fruits": 0.5, "Baby & Kids": 0.4,
}

# Month multipliers per category (index 0 = Jan).  These are the PLANTED seasonal signals.
SEASONAL = {
    "Beverages":           [1.0, 1.0, 1.4, 1.7, 1.8, 1.2, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    "Frozen & Ice Cream":  [0.7, 0.9, 1.6, 2.2, 2.4, 1.4, 0.9, 0.8, 0.8, 0.9, 0.8, 0.7],
    "Sweets & Dry Fruits": [1.1, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 1.1, 1.2, 3.0, 2.2, 1.3],
    "Household":           [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.6, 1.3, 1.0],
}
# Hour-of-day footfall profile, store open 08:00-22:00 (index = hour)
HOUR_WEIGHTS = {8: 3, 9: 5, 10: 6, 11: 8, 12: 7, 13: 5, 14: 4, 15: 4, 16: 5,
                17: 8, 18: 11, 19: 12, 20: 9, 21: 4}
# Month-level footfall: festive Oct (Diwali 20-Oct-2025) and Nov uplift
MONTH_FOOTFALL = [0.95, 0.90, 0.95, 1.00, 1.00, 0.95, 0.92, 0.97, 1.02, 1.30, 1.15, 1.10]
WEEKEND_FACTOR = 1.35
PAYMENT_MODES = (["UPI", "Card", "Cash"], [0.55, 0.25, 0.20])


def build_products(rng):
    rows = []
    pid = 1
    for cat, items in CATALOG.items():
        for name, price in items:
            # popularity = category purchase frequency x product-level spread
            # (lognormal gives some fast and some slow movers without absurd outliers)
            popularity = CATEGORY_FREQ[cat] * float(rng.lognormal(0.0, 0.55))
            rows.append((f"P{pid:03d}", name, cat, float(price), popularity))
            pid += 1
    df = pd.DataFrame(rows, columns=["product_id", "product_name", "category", "unit_price", "popularity"])
    # Plant two deliberately slow-moving products for the 'slow movers' analysis
    slow = ["Khova 250g", "Feeding Bottle"]
    df.loc[df.product_name.isin(slow), "popularity"] = 0.02
    return df, slow


def main(n_invoices):
    rng = np.random.default_rng(SEED)
    OUT_DIR.mkdir(exist_ok=True)
    products, slow = build_products(rng)

    # ---- invoice-level attributes -----------------------------------------
    days = pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31", freq="D")
    day_w = np.array([MONTH_FOOTFALL[d.month - 1] * (WEEKEND_FACTOR if d.day_of_week >= 5 else 1.0)
                      for d in days])
    br_w = np.array([b[3] for b in BRANCHES])
    hours = np.array(list(HOUR_WEIGHTS))
    hr_w = np.array(list(HOUR_WEIGHTS.values()), dtype=float)

    inv_day = rng.choice(len(days), n_invoices, p=day_w / day_w.sum())
    inv_branch = rng.choice(len(BRANCHES), n_invoices, p=br_w / br_w.sum())
    inv_hour = rng.choice(hours, n_invoices, p=hr_w / hr_w.sum())
    inv_sec = rng.integers(0, 3600, n_invoices)
    inv_ts = (days.values[inv_day] + inv_hour.astype("timedelta64[h]")
              + inv_sec.astype("timedelta64[s]"))
    inv_pay = rng.choice(PAYMENT_MODES[0], n_invoices, p=PAYMENT_MODES[1])
    basket = rng.choice([1, 2, 3, 4, 5, 6], n_invoices, p=[0.22, 0.26, 0.22, 0.15, 0.10, 0.05])

    # ---- expand to line items --------------------------------------------
    idx = np.repeat(np.arange(n_invoices), basket)
    line_no = np.concatenate([np.arange(1, b + 1) for b in basket])
    ts = inv_ts[idx]
    months = pd.DatetimeIndex(ts).month.values

    # product choice depends on month (seasonality)
    prod_idx = np.empty(len(idx), dtype=int)
    for m in range(1, 13):
        mask = months == m
        mult = products.category.map(lambda c: SEASONAL.get(c, [1.0] * 12)[m - 1]).values
        w = products.popularity.values * mult
        prod_idx[mask] = rng.choice(len(products), mask.sum(), p=w / w.sum())

    qty = rng.choice([1, 2, 3, 4, 5], len(idx), p=[0.55, 0.25, 0.11, 0.06, 0.03])
    p = products.iloc[prod_idx].reset_index(drop=True)
    b = [BRANCHES[i] for i in inv_branch[idx]]

    df = pd.DataFrame({
        "invoice_id":   [f"INV{i:07d}" for i in idx + 1],
        "line_no":      line_no,
        "txn_ts":       pd.DatetimeIndex(ts).strftime("%Y-%m-%d %H:%M:%S"),
        "branch_id":    [x[0] for x in b],
        "branch_name":  [x[1] for x in b],
        "city":         [x[2] for x in b],
        "product_id":   p.product_id,
        "product_name": p.product_name,
        "category":     p.category,
        "unit_price":   p.unit_price,
        "quantity":     qty,
        "payment_mode": inv_pay[idx],
    })
    df = df.sort_values(["txn_ts", "invoice_id", "line_no"])
    (OUT_DIR / "raw").mkdir(exist_ok=True)
    out = OUT_DIR / "raw" / "sales_transactions.csv"
    df.to_csv(out, index=False, header=False)  # no header: simpler for Hive
    products.drop(columns="popularity").to_csv(OUT_DIR / "products.csv", index=False)

    planted = {
        "note": "Patterns deliberately built into the synthetic generator (ground truth).",
        "seed": SEED, "invoices": int(n_invoices), "line_items": int(len(df)),
        "branch_footfall_weights": {f"{x[0]} {x[1]}": x[3] for x in BRANCHES},
        "hour_weights": HOUR_WEIGHTS, "peak_hours_expected": [18, 19],
        "month_footfall": MONTH_FOOTFALL, "weekend_factor": WEEKEND_FACTOR,
        "seasonal_category_multipliers": SEASONAL,
        "planted_slow_movers": slow,
        "category_purchase_frequency": CATEGORY_FREQ,
        "payment_mix": dict(zip(*PAYMENT_MODES)),
    }
    (OUT_DIR / "planted_patterns.json").write_text(json.dumps(planted, indent=2))
    print(f"Wrote {len(df):,} line items ({n_invoices:,} invoices) -> {out}")
    print(f"File size: {out.stat().st_size / 1e6:.1f} MB")
    print(df.head(5).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--invoices", type=int, default=200_000)
    main(ap.parse_args().invoices)
