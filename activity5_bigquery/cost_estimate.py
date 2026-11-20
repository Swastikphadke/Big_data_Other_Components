"""
Activity 5 - cost estimation.

PART A (ACTUAL)       : what this prototype used in the BigQuery Sandbox (measured).
PART B (HYPOTHETICAL) : a production scenario with explicit assumptions, priced with the
                        official Google Cloud Billing Catalog prices downloaded on
                        2026-11-03 (pricing/catalog_*.json, region asia-south1 / Mumbai).
Nothing in Part B was deployed or billed.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

HERE = Path(__file__).parent
RES = HERE / "results"
GiB, TiB = 2**30, 2**40


def sku_price(fn, sku_id):
    """Return list of (start_amount, unit_price_usd, unit) tiers for one SKU from the saved catalog."""
    sku = next(s for s in json.load(open(HERE / "pricing" / fn, encoding="utf-8-sig")) if s["skuId"] == sku_id)
    pe = sku["pricingInfo"][0]["pricingExpression"]
    return sku["description"], [(t["startUsageAmount"], int(t["unitPrice"].get("units", "0")) + t["unitPrice"].get("nanos", 0) / 1e9,
                                 pe["usageUnitDescription"]) for t in pe["tieredRates"]]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    P = {k: sku_price(*v) for k, v in {
        "analysis": ("catalog_bigquery.json", "B898-EB89-E9CA"),          # Analysis (asia-south1)
        "active": ("catalog_bigquery.json", "E056-7501-89FA"),            # Active Logical Storage (asia-south1)
        "longterm": ("catalog_bigquery.json", "339A-D3C3-4A8C"),          # Long Term Logical Storage (asia-south1)
        "streaming": ("catalog_bigquery.json", "AC85-E714-3881"),         # Streaming Insert (asia-south1)
        "gcs": ("catalog_cloud_storage.json", "2717-BEFE-3773"),          # Standard Storage Mumbai
        "gcs_a": ("catalog_cloud_storage.json", "4DBF-185F-A415"),        # Regional Standard Class A Operations
    }.items()}
    print("OFFICIAL PRICES (Cloud Billing Catalog API, retrieved 2026-11-03, USD):")
    for k, (desc, tiers) in P.items():
        print(f"  {desc:<42} " + "; ".join(f"from {s:g}: {p:g} per {u}" for s, p, u in tiers))
    q_free, q_price = P["analysis"][1][1][0], P["analysis"][1][1][1]          # 1 TiB free, then USD/TiB
    a_free, a_price = P["active"][1][1][0], P["active"][1][1][1]              # 10 GiB free, then USD/GiB-month
    lt_price = P["longterm"][1][1][1]
    gcs_price = P["gcs"][1][0][1]
    gcs_a_free, gcs_a_price = P["gcs_a"][1][1][0], P["gcs_a"][1][1][1]

    # ---------------------------------------------------------------- PART A: actual usage (measured)
    stats = pd.read_csv(RES / "query_job_stats.csv")
    table = json.load(open(HERE.parent / "evidence" / "act5" / "bq_json" / "table_access_logs.json", encoding="utf-8-sig"))
    rows, tbytes = int(table["numRows"]), int(table["numBytes"])
    raw_gz = HERE / "data" / "raw" / "access_log_2026-10-26_11-01.log.gz"
    raw_bytes = sum(len(l.encode()) for l in gzip.open(raw_gz, "rt", encoding="utf-8"))
    print("\nPART A - ACTUAL USAGE OF THIS PROTOTYPE (BigQuery Sandbox, billing disabled)")
    print(f"  raw logs: {raw_bytes / 2**20:.1f} MiB uncompressed ({raw_gz.stat().st_size / 2**20:.1f} MiB gzip) for {rows:,} requests")
    print(f"  BigQuery table: {tbytes / 2**20:.1f} MiB logical ({tbytes / rows:.0f} B per row) = {tbytes / GiB * 100 / a_free:.2f} % of the 10 GiB free storage")
    print(f"  {len(stats)} query jobs: processed {stats.bytes_processed.sum() / 2**20:.1f} MiB, billed {stats.bytes_billed.sum() / 2**20:.1f} MiB "
          f"= {stats.bytes_billed.sum() / TiB * 100:.4f} % of the 1 TiB monthly free query tier")
    print("  batch load jobs: no charge (no load-job SKU exists in the billing catalog; loading uses the shared slot pool)")
    print("  => actual cost USD 0.00 (sandbox; free tiers not exceeded; no billing account attached)")

    # ---------------------------------------------------------------- PART B: hypothetical production
    A = {"raw_logs_gib_per_day": 20.0, "retention_days_bigquery": 90, "retention_days_gcs_raw": 365,
         "dashboard_queries_per_hour": 15, "dashboard_window_hours": 24, "adhoc_full_week_queries_per_day": 4,
         "upload_objects_per_day": 288 * 10}       # 10 web servers, one gzip object every 5 minutes
    bq_per_raw = tbytes / raw_bytes                            # measured: BigQuery logical bytes per raw log byte
    bq_gib_day = A["raw_logs_gib_per_day"] * bq_per_raw
    bq_stored = bq_gib_day * A["retention_days_bigquery"]
    active = min(bq_stored, bq_gib_day * 90)                  # partitions < 90 days untouched-time stay active
    longterm = bq_stored - active
    gz_ratio = raw_bytes / raw_gz.stat().st_size
    gcs_stored = A["raw_logs_gib_per_day"] / gz_ratio * A["retention_days_gcs_raw"]
    # query volume, scaled from the measured bytes of our 15 analytic queries over one full week
    q = stats[stats["query"].str.startswith("q")]
    frac_per_query = (q.bytes_processed / tbytes).mean()       # avg fraction of the table's bytes each query scans
    dash_scan = frac_per_query * bq_gib_day * A["dashboard_window_hours"] / 24   # partition pruning -> last day only
    dash_month = dash_scan * A["dashboard_queries_per_hour"] * 24 * 30
    adhoc_month = frac_per_query * bq_gib_day * 7 * A["adhoc_full_week_queries_per_day"] * 30
    q_tib = (dash_month + adhoc_month) / 1024
    no_prune_month = frac_per_query * bq_stored * A["dashboard_queries_per_hour"] * 24 * 30 / 1024 + adhoc_month / 1024
    cost = [
        ("BigQuery analysis (on-demand)", f"{q_tib:.2f} TiB/month", max(0, q_tib - q_free) * q_price),
        ("BigQuery active storage", f"{active:.0f} GiB", max(0, active - a_free) * a_price),
        ("BigQuery long-term storage", f"{longterm:.0f} GiB", longterm * lt_price),
        ("Cloud Storage Standard (raw .gz, 1 year)", f"{gcs_stored:.0f} GiB", gcs_stored * gcs_price),
        ("Cloud Storage Class A (uploads)", f"{A['upload_objects_per_day'] * 30:,} ops", max(0, A["upload_objects_per_day"] * 30 - gcs_a_free) * gcs_a_price),
        ("BigQuery batch load jobs (GCS -> BigQuery)", "daily", 0.0),
    ]
    df = pd.DataFrame(cost, columns=["item", "quantity", "usd_per_month"]); df["usd_per_month"] = df.usd_per_month.round(2)
    print("\nPART B - HYPOTHETICAL PRODUCTION ESTIMATE (not deployed; requires a billing account)")
    print("  assumptions:", json.dumps(A))
    print(f"  measured ratios used: BigQuery bytes / raw log bytes = {bq_per_raw:.2f}; raw / gzip = {gz_ratio:.1f}; "
          f"average analytic query scans {frac_per_query * 100:.1f} % of the table bytes")
    print(f"  => BigQuery ingest {bq_gib_day:.1f} GiB/day; dashboards scan {dash_scan:.2f} GiB per query (last 24 h partition only)")
    print(df.to_string(index=False))
    print(f"  TOTAL ~ USD {df.usd_per_month.sum():,.2f} per month")
    print(f"  without partition pruning the dashboards would scan ~{no_prune_month:.1f} TiB/month "
          f"-> analysis ~ USD {max(0, no_prune_month - q_free) * q_price:,.2f} per month")
    df.to_csv(RES / "cost_estimate_production.csv", index=False)
    pd.DataFrame([{"assumption": k, "value": v} for k, v in A.items()] +
                 [{"assumption": "bq_bytes_per_raw_byte (measured)", "value": round(bq_per_raw, 3)},
                  {"assumption": "raw_to_gzip_ratio (measured)", "value": round(gz_ratio, 2)},
                  {"assumption": "avg_fraction_of_table_scanned_per_query (measured)", "value": round(frac_per_query, 4)},
                  {"assumption": "no_partition_pruning_tib_per_month", "value": round(no_prune_month, 2)}]).to_csv(RES / "cost_assumptions.csv", index=False)


if __name__ == "__main__":
    main()
