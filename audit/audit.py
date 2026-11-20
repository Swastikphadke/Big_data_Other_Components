"""
Final audit of all five activities (read-only: nothing under activity*/ or evidence/ is modified).

  A. directory inventory (code, data, results, charts, README, configuration)
  B. evidence/manifest.csv: every referenced artefact resolved on disk (paths, patterns, counts)
  C. numeric cross-check: key figures recomputed from CSV/log sources and searched for in each README
  D. screenshots: modification time vs. the final verified run window of each activity
Writes audit/audit_checks.csv and prints a log (use --log).
"""
import argparse
import csv
import glob
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import teelog  # noqa: E402

rows = []


def rec(section, item, ok, detail=""):
    rows.append({"section": section, "item": item, "result": "OK" if ok else "ISSUE", "detail": detail})
    print(f"[{'OK' if ok else 'ISSUE':5}] {section:<11} {item}" + (f"  -- {detail}" if detail else ""))


# ---------------------------------------------------------------- A. inventory
ACTS = {1: "activity1_hive", 2: "activity2_kafka", 3: "activity3_flink", 4: "activity4_mongodb", 5: "activity5_bigquery"}
CONFIG = {1: ["hql/01_schema.hql", "run_queries.sh"], 2: ["config.py", "setup_topics.sh", "run_demo.ps1"],
          3: ["Dockerfile", "thresholds.json", "setup_topics.ps1"], 4: ["config.py", "relational_schema.sql", "run_all.ps1"],
          5: ["bq/schema_access_logs.json", "bq_setup.ps1", "run_all.ps1"]}


def inventory():
    for n, d in ACTS.items():
        p = ROOT / d
        py = sorted(x.name for x in p.glob("*.py"))
        data = [x for x in (p / "data").rglob("*") if x.is_file()] if (p / "data").exists() else []
        res = [x for x in (p / "results").rglob("*") if x.is_file()] if (p / "results").exists() else []
        charts = sorted((p / "charts").glob("*.png")) if (p / "charts").exists() else []
        cfg_missing = [c for c in CONFIG[n] if not (p / c).exists()]
        ok = (p / "README.md").exists() and py and data and res and charts and not cfg_missing
        rec("inventory", f"Activity {n} {d}", ok,
            f"README={'yes' if (p / 'README.md').exists() else 'NO'} py={len(py)} data_files={len(data)} result_files={len(res)} "
            f"charts={len(charts)} config_missing={cfg_missing}")
    rec("inventory", "docker-compose.yml (Hive, Kafka, Kafka-UI, Flink JM/TM, MongoDB)", (ROOT / "docker-compose.yml").exists())
    rec("inventory", "common/ helpers (chartstyle, teelog, capture_console, capture_web)",
        all((ROOT / "common" / f).exists() for f in ("chartstyle.py", "teelog.py", "capture_console.ps1", "capture_web.ps1")))


# ---------------------------------------------------------------- B. manifest
TOP = ("activity", "evidence", "audit", "common", "docker-compose.yml")


def expand(token, base):
    """Resolve one manifest token to a list of files; returns (files, expected_count or None).
    Token forms: path | name relative to the entry's first directory | glob '*' | range 'q01..q15' |
    optional '(N)' expected count | trailing descriptive words / parenthetical notes are ignored."""
    token = token.strip()
    m = re.search(r"\((\d+)\)\s*$", token)
    expected = int(m.group(1)) if m else None
    token = re.sub(r"\s*\(\d+\)\s*$", "", token).strip()
    token = token.split()[0]                                   # drop descriptions such as '(mongodb)' or 'validator'
    if not token.startswith(TOP) and base:
        token = f"{base}/{token}"
    pat = re.sub(r"(\d+)\.\.(\D*?)(\d+)", "[0-9]*", token)     # q01..q12.log -> q[0-9]*.log ; mongosh_m1..m4 -> mongosh_m[0-9]*
    if "*" in pat:
        files = glob.glob(str(ROOT / pat)) or glob.glob(str(ROOT / pat) + ".png")
        return files, expected
    if "/screenshots/" in token and not re.search(r"\.\w+$", token):
        return glob.glob(str(ROOT / token) + ".png"), expected
    return ([str(ROOT / token)] if (ROOT / token).exists() else []), expected


def manifest():
    with open(ROOT / "evidence" / "manifest.csv", newline="", encoding="utf-8") as f:
        entries = list(csv.DictReader(f))
    print(f"\nmanifest entries: {len(entries)}")
    for e in entries:
        art = e["artifact"]
        if e["type"].startswith("configuration") and "hand-written" in e["produced_by"]:
            pass
        tokens = [t for t in art.split(" + ")]
        first = tokens[0].strip().split()[0]
        base = first.rsplit("/", 1)[0] if "/" in first else None     # entry base = directory of the first artefact
        if base and ("*" in base or ".." in base):
            base = base.split("/*")[0]
        missing, counts = [], []
        for t in tokens:
            t0 = t.strip()
            files, exp = expand(t0, base)
            if not files:
                missing.append(t0)
            elif exp is not None and len(files) != exp:
                counts.append(f"{t0}: {len(files)} found, {exp} stated")
        ok = not missing and not counts
        rec("manifest", f"act{e['activity']} {art[:90]}", ok, "; ".join([f"missing: {m}" for m in missing] + counts))


# ---------------------------------------------------------------- C. numeric cross-check
def readme(n):
    return (ROOT / ACTS[n] / "README.md").read_text(encoding="utf-8")


def claim(n, label, value_str, alternatives=()):
    txt = readme(n)
    found = [s for s in (value_str, *alternatives) if s in txt]
    rec("numbers", f"Activity {n}: {label} = {value_str}", bool(found), "found in README" if found else "NOT found in README")


def numbers():
    r1 = ROOT / ACTS[1] / "results"
    q1 = pd.read_csv(r1 / "q01_overall_kpis.csv").iloc[0]
    rev = str(int(round(q1.total_revenue_inr)))
    head, tail = rev[:-3], rev[-3:]                                    # Indian grouping: 11,76,20,095
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:]); head = head[:-2]
    ind_fmt = ",".join(([head] if head else []) + groups + [tail])
    claim(1, "total revenue (Indian grouping)", f"₹{ind_fmt}")
    claim(1, "average basket", f"{q1.avg_basket_value_inr:.2f}")
    b = pd.read_csv(r1 / "q04_branch_revenue.csv").iloc[0]
    claim(1, "top branch share", f"{b.revenue_share_pct:.2f} %")
    h = pd.read_csv(r1 / "q05_peak_hours.csv").set_index("sale_hour")
    claim(1, "19:00 invoices", f"{h.loc[19, 'invoices']:,}"); claim(1, "18:00 invoices", f"{h.loc[18, 'invoices']:,}")
    m = pd.read_csv(r1 / "q06_monthly_trend.csv").set_index("sale_month")
    claim(1, "October MoM growth", f"{m.loc['2025-10', 'mom_growth_pct']:.2f}")
    w = pd.read_csv(r1 / "q10_weekday_weekend.csv").set_index("day_type")
    claim(1, "weekend avg daily revenue", f"₹{w.loc['Weekend', 'avg_daily_revenue_inr'] / 1e5:.2f} L")
    claim(1, "weekday avg daily revenue", f"₹{w.loc['Weekday', 'avg_daily_revenue_inr'] / 1e5:.2f} L")
    log = (ROOT / "evidence/act1/02_schema_load.log").read_text(encoding="utf-8", errors="ignore")
    n = re.search(r"numRows\s+\|\s+(\d+)", log).group(1)
    claim(1, "rows loaded", f"{int(n):,}")

    r2 = ROOT / ACTS[2] / "results"; ev2 = (ROOT / "evidence/act2/07_evaluation.log").read_text(encoding="utf-8")
    tot = re.search(r"precision=([\d.]+)\s+recall=([\d.]+)", ev2).groups()
    claim(2, "precision", tot[0]); claim(2, "recall", tot[1])
    lat = pd.read_csv(r2 / "evaluation_latency.csv").set_index("stat").latency_ms
    claim(2, "latency p50/p95/p99", f"p50 {lat['p50']:.0f} ms, p95 {lat['p95']:.0f} ms, p99 {lat['p99']:.0f} ms")
    ep = pd.read_csv(r2 / "evaluation_episodes.csv")
    claim(2, "episodes detected", f"{int(ep.detected.sum())} / {len(ep)}")
    claim(2, "mean detection delay", f"{ep.detect_delay_min.mean():.1f} min")
    al = pd.read_csv(r2 / "alerts.csv").event.value_counts()
    claim(2, "alert events", f"{al.sum()} = {al['OPEN']} OPEN")
    ing = pd.read_csv(r2 / "ingested_readings.csv", usecols=["partition"]).partition.value_counts().sort_index()
    claim(2, "messages per partition", f"{ing[0]:,} / {ing[1]:,} / {ing[2]:,}")

    r3 = ROOT / ACTS[3] / "results"; ev3 = (ROOT / "evidence/act3/09_evaluation.log").read_text(encoding="utf-8")
    ra = pd.read_csv(r3 / "reading_alerts.csv")
    claim(3, "reading alerts", f"{len(ra):,} / {len(ra):,}")
    claim(3, "episode events identical to reference", re.search(r"identical \(type, patient, vital, timestamp\): (\d+/\d+)", ev3).group(1).replace("/", " / "))
    lt = pd.read_csv(r3 / "evaluation_latency.csv")
    claim(3, "latency reading alert p50/p95", f"{lt.p50_ms[0]:.0f} / {lt.p95_ms[0]:.0f} ms")
    claim(3, "latency episode p50/p95", f"{lt.p50_ms[1]:,.0f} / {lt.p95_ms[1]:,.0f} ms")
    fm = (ROOT / "evidence/act3/07_final_flink_metrics.log").read_text(encoding="utf-8")
    o = re.search(r"OverAggregate\S*.*?records_in=\s*(\d+) records_out=\s*(\d+)", fm).groups()
    claim(3, "OVER rows in", f"{int(o[0]):,}"); claim(3, "OVER rows out/dropped", f"{int(o[0]) - int(o[1])} = ")
    mem = (ROOT / "evidence/act3/05_memory_during_run.log").read_text(encoding="utf-8")
    hf = min(int(x.replace(",", "")) for x in re.findall(r"host_free=([\d,]+)MB", mem))
    claim(3, "min host free memory", f"{hf} MB")

    r4 = ROOT / ACTS[4] / "results"; s = pd.read_csv(r4 / "benchmark_summary.csv")
    bb, aa = s[s.phase == "before"].set_index("query"), s[s.phase == "after"].set_index("query")
    for q in bb.index:
        claim(4, f"benchmark {q} ratio", f"×{bb.loc[q, 'wall_median_ms'] / aa.loc[q, 'wall_median_ms']:.1f}")
    claim(4, "Q1 medians", f"{bb.loc['Q1', 'wall_median_ms']:.2f} → {aa.loc['Q1', 'wall_median_ms']:.2f}")
    rc = pd.read_csv(r4 / "relational_counts.csv").set_index("item").value
    claim(4, "SQL rows", f"{sum(rc[k] for k in rc.index if k.startswith('sql_rows')):,}")
    claim(4, "join rows for one product", f"{rc['one_product_sql_join_rows']} joined rows")
    claim(4, "nested filter counts", f"{rc['nested_filter_mongo']:,} = {rc['nested_filter_sql']:,}")

    r5 = ROOT / ACTS[5] / "results"; q = pd.read_csv(r5 / "q01_overview.csv").iloc[0]
    claim(5, "requests / IPs", f"{q.requests:,} requests, {q.unique_ips:,} IPs")
    claim(5, "GiB served", f"{q.gib_sent} GiB")
    pk = pd.read_csv(r5 / "q08_peak_5min_windows.csv").iloc[0]
    claim(5, "busiest window", f"max {pk.requests:,} req = {pk.requests_per_second} req/s")
    hr = pd.read_csv(r5 / "q14_suspicious_high_rate.csv").set_index("client_ip").loc["198.51.100.77"]
    claim(5, "scraper", f"{hr.requests:,} req, {hr.minutes_at_20plus_rpm} minutes ≥ 20 req/min, {hr.rate_limited_429:,} × 429")
    js = pd.read_csv(r5 / "query_job_stats.csv")
    claim(5, "query jobs processed", f"{js.bytes_processed.sum() / 2**20:.0f} MiB")
    ce = pd.read_csv(r5 / "cost_estimate_production.csv")
    claim(5, "hypothetical total", f"≈ {ce.usd_per_month.sum():.0f}")
    v = pd.read_csv(r5 / "verification.csv")
    claim(5, "verification", f"{(v.result == 'PASS').sum()}/{len(v)}")
    pr = pd.read_csv(r5 / "pruning_comparison.csv").set_index("query").bytes_processed / 2**20
    claim(5, "pruning one UTC day", f"{pr['p2_one_utc_day']:.2f}")


# ---------------------------------------------------------------- D. screenshots vs final-run windows
WINDOWS = {"act1": ("2026-11-03 18:50", "2026-11-03 19:05"), "act2": ("2026-11-03 19:18", "2026-11-03 19:40"),
           "act3": ("2026-11-03 20:08", "2026-11-03 20:20"), "act3/run1_superseded_backpressure": ("2026-11-03 19:51", "2026-11-03 20:07"),
           "act4": ("2026-11-03 21:18", "2026-11-03 21:35"), "act5": ("2026-11-03 22:03", "2026-11-03 22:45")}


def screenshots():
    for key, (lo, hi) in WINDOWS.items():
        folder = ROOT / "evidence" / key / "screenshots"
        if not folder.exists():
            continue
        shots = sorted(folder.glob("*.png"))
        out = [f"{p.name} @ {datetime.fromtimestamp(p.stat().st_mtime):%H:%M}" for p in shots
               if not (lo <= datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M") <= hi)]
        dbl = [p.name for p in shots if p.name.endswith(".png.png")]
        rec("screenshots", f"{key}: {len(shots)} screenshots within final-run window {lo[11:]}-{hi[11:]}", not out,
            ("outside window: " + ", ".join(out)) if out else "")
        if dbl:
            rec("screenshots", f"{key}: file names with doubled extension", False, ", ".join(dbl))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    print("=== A. INVENTORY"); inventory()
    print("\n=== B. MANIFEST"); manifest()
    print("\n=== C. NUMBERS (source value -> README)"); numbers()
    print("\n=== D. SCREENSHOTS"); screenshots()
    df = pd.DataFrame(rows); df.to_csv(Path(__file__).parent / "audit_checks.csv", index=False)
    print(f"\n{(df.result == 'OK').sum()} OK, {(df.result != 'OK').sum()} ISSUE")


if __name__ == "__main__":
    main()
