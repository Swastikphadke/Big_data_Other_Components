"""
Activity 5 - verify BigQuery Sandbox limitations EMPIRICALLY (no billing enabled).
All probes are harmless: the DML insert selects zero rows, the streaming test uses a
temporary probe table that is deleted afterwards.
"""
import argparse
import subprocess
import sys
import warnings
from pathlib import Path

from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402
import bq_client  # noqa: E402

warnings.filterwarnings("ignore")


def attempt(label, fn):
    try:
        r = fn()
        print(f"ALLOWED   {label}" + (f"  -> {r}" if r is not None else ""))
    except Exception as e:  # noqa: BLE001
        msg = str(e).split("\n")[0][:260]
        print(f"REFUSED   {label}\n          {type(e).__name__}: {msg}")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    c = bq_client.client()
    billing = subprocess.run([bq_client.GCLOUD, "billing", "projects", "describe", bq_client.PROJECT,
                              "--format=value(billingEnabled)"], capture_output=True, text=True).stdout.strip()
    print(f"project {bq_client.PROJECT}: billingEnabled = {billing}  (False => BigQuery Sandbox)")
    ds = c.get_dataset(f"{bq_client.PROJECT}.{bq_client.DATASET}")
    t = c.get_table(bq_client.TABLE)
    print(f"dataset default table expiration     : {ds.default_table_expiration_ms} ms = {ds.default_table_expiration_ms / 86400000:.0f} days")
    print(f"dataset default partition expiration : {ds.default_partition_expiration_ms} ms = {ds.default_partition_expiration_ms / 86400000:.0f} days")
    print(f"table partition expiration           : {t.time_partitioning.expiration_ms} ms -> each daily partition is deleted 60 days after its date")
    print(f"table expires                        : {t.expires}\n")

    attempt("SELECT query (batch analysis)", lambda: list(c.query(f"SELECT COUNT(*) FROM `{bq_client.TABLE}`").result())[0][0])
    attempt("DDL: CREATE TABLE probe table", lambda: c.query(
        f"CREATE OR REPLACE TABLE `{bq_client.PROJECT}.{bq_client.DATASET}.sandbox_probe` (x INT64)").result() and "created")
    attempt("DML: INSERT ... SELECT (zero rows) into probe table", lambda: c.query(
        f"INSERT INTO `{bq_client.PROJECT}.{bq_client.DATASET}.sandbox_probe` (x) SELECT 1 FROM UNNEST([1]) WHERE FALSE").result() and "ok")
    attempt("DML: UPDATE probe table (WHERE FALSE)", lambda: c.query(
        f"UPDATE `{bq_client.PROJECT}.{bq_client.DATASET}.sandbox_probe` SET x = 2 WHERE FALSE").result() and "ok")
    attempt("Streaming insert (tabledata.insertAll) into probe table", lambda: c.insert_rows_json(
        f"{bq_client.PROJECT}.{bq_client.DATASET}.sandbox_probe", [{"x": 1}]) or "no row errors")
    c.delete_table(f"{bq_client.PROJECT}.{bq_client.DATASET}.sandbox_probe", not_found_ok=True)
    print("\nprobe table deleted; access_logs untouched:",
          list(c.query(f"SELECT COUNT(*) FROM `{bq_client.TABLE}`").result())[0][0], "rows")


if __name__ == "__main__":
    main()
