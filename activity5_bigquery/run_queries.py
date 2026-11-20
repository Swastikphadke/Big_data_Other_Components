"""
Activity 5 - run every SQL file in sql/ on BigQuery and keep local copies.

For each query: dry run (estimated bytes) -> real run with the query cache DISABLED
(so bytes processed are genuine) -> results/<query>.csv + job statistics in
results/query_job_stats.csv. Also runs a partition/cluster-pruning comparison and
finally lists this session's jobs from INFORMATION_SCHEMA.JOBS_BY_USER.
"""
import argparse
import sys
import warnings
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402
import bq_client  # noqa: E402

warnings.filterwarnings("ignore", message="BigQuery Storage module not found")
HERE = Path(__file__).parent
RES = HERE / "results"
LABELS = {"activity": "act5-weblogs"}
T_ = bq_client.TABLE
PRUNING = [  # name, sql, explanation  (bytes are what on-demand pricing charges for)
    ("p1_full_table_1col", f"SELECT COUNTIF(status >= 500) AS failures FROM `{T_}`",
     "no filter: status column of all partitions"),
    ("p2_one_utc_day", f"SELECT COUNTIF(status >= 500) AS failures FROM `{T_}` "
                       "WHERE ts >= TIMESTAMP('2026-10-28 00:00:00 UTC') AND ts < TIMESTAMP('2026-10-29 00:00:00 UTC')",
     "partition filter aligned to one UTC day -> 1 partition"),
    ("p3_one_ist_day", f"SELECT COUNTIF(status >= 500) AS failures FROM `{T_}` "
                       "WHERE ts >= TIMESTAMP('2026-10-28 00:00:00+05:30') AND ts < TIMESTAMP('2026-10-29 00:00:00+05:30')",
     "one IST day spans 2 UTC partitions"),
    ("p4_full_table_wide_col", f"SELECT COUNTIF(status >= 500) AS failures, COUNT(DISTINCT user_agent) AS agents FROM `{T_}`",
     "columnar storage: adding the long user_agent column scans more"),
    ("p5_ist_day_plus_cluster", f"SELECT COUNTIF(status >= 500) AS failures FROM `{T_}` "
                                "WHERE ts >= TIMESTAMP('2026-10-28 00:00:00+05:30') AND ts < TIMESTAMP('2026-10-29 00:00:00+05:30') "
                                "AND endpoint = '/api/v1/payments'",
     "partition + clustered column filter (endpoint column must be read)"),
]


def run(c, name, sql, stats):
    dry = c.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    job = c.query(sql, job_config=bigquery.QueryJobConfig(use_query_cache=False, labels=LABELS), job_id_prefix=f"{name}_")
    df = job.to_dataframe()
    ms = (job.ended - job.started).total_seconds() * 1000
    stats.append({"query": name, "job_id": job.job_id, "rows": len(df), "estimated_bytes": dry.total_bytes_processed,
                  "bytes_processed": job.total_bytes_processed, "bytes_billed": job.total_bytes_billed,
                  "slot_ms": job.slot_millis, "elapsed_ms": round(ms), "cache_hit": job.cache_hit,
                  "created_utc": job.created.strftime("%Y-%m-%d %H:%M:%S")})
    s = stats[-1]
    print(f"\n### {name}  job={job.job_id}\n    rows={len(df)}  processed={s['bytes_processed'] / 2**20:.2f} MiB  "
          f"billed={s['bytes_billed'] / 2**20:.2f} MiB  slot={s['slot_ms']} ms  elapsed={s['elapsed_ms']} ms  cache_hit={job.cache_hit}")
    with pd.option_context("display.width", 250, "display.max_columns", 20, "display.max_colwidth", 70):
        print(df.head(25).to_string(index=False))
    return df


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    RES.mkdir(exist_ok=True)
    c = bq_client.client()
    print(f"project={c.project} location={c.location} table={bq_client.TABLE}")
    t = c.get_table(bq_client.TABLE)
    print(f"table rows={t.num_rows:,} logical bytes={t.num_bytes:,} partitioning={t.time_partitioning} clustering={t.clustering_fields}")
    stats = []
    for f in sorted((HERE / "sql").glob("q*.sql")):
        df = run(c, f.stem, f.read_text(encoding="utf-8"), stats)
        df.to_csv(RES / f"{f.stem}.csv", index=False)

    print("\n" + "=" * 100 + "\nPARTITION / CLUSTER PRUNING (same aggregate, less data scanned)")
    prune = []
    for name, sql, why in PRUNING:
        df = run(c, name, sql, stats)
        prune.append({"query": name, "filter": why, "failures": int(df.iloc[0, 0]), **{k: stats[-1][k] for k in
                      ("estimated_bytes", "bytes_processed", "bytes_billed", "slot_ms", "elapsed_ms")}})
    pd.DataFrame(prune).to_csv(RES / "pruning_comparison.csv", index=False)

    pd.DataFrame(stats).to_csv(RES / "query_job_stats.csv", index=False)
    print("\n" + "=" * 100 + "\nJOB HISTORY from INFORMATION_SCHEMA.JOBS_BY_USER (this activity's labelled query jobs)")
    hist = c.query(f"""
        SELECT job_id, statement_type, total_bytes_processed, total_bytes_billed, total_slot_ms, cache_hit,
               TIMESTAMP_DIFF(end_time, start_time, MILLISECOND) AS elapsed_ms
        FROM `region-{bq_client.LOCATION}`.INFORMATION_SCHEMA.JOBS_BY_USER
        WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)
          AND EXISTS (SELECT 1 FROM UNNEST(labels) l WHERE l.key = 'activity' AND l.value = 'act5-weblogs')
        ORDER BY creation_time""").to_dataframe()
    hist.to_csv(RES / "information_schema_jobs.csv", index=False)
    print(hist.to_string(index=False))
    tot = pd.DataFrame(stats)
    print(f"\nTOTAL for {len(tot)} queries: processed {tot.bytes_processed.sum() / 2**20:.1f} MiB, "
          f"billed {tot.bytes_billed.sum() / 2**20:.1f} MiB (sandbox: first 1 TiB per month free; no billing account)")


if __name__ == "__main__":
    main()
