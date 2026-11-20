"""
Activity 5 - verify every BigQuery result against the local dataset (pandas
re-computation from data/processed/access_logs.csv.gz) and check the detections
against the planted incidents (data/incidents.json).
Prints PASS/FAIL per check and writes results/verification.csv.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

HERE = Path(__file__).parent
RES = HERE / "results"
checks = []


def check(name, ok, detail=""):
    checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail else ""))


def bq(name, **kw):
    return pd.read_csv(RES / f"{name}.csv", **kw)


def same(a, b, cols, key):
    m = a[cols].merge(b[cols], on=key, how="outer", suffixes=("_bq", "_local"), indicator=True)
    if (m["_merge"] != "both").any():
        return False, f"{int((m['_merge'] != 'both').sum())} keys only on one side"
    bad = [c for c in cols if c not in key and not np.allclose(m[f"{c}_bq"].astype(float), m[f"{c}_local"].astype(float), atol=0.011)]
    return not bad, (f"mismatch in {bad}" if bad else f"{len(m)} rows identical")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    d = pd.read_csv(HERE / "data" / "processed" / "access_logs.csv.gz", keep_default_na=False,
                    dtype={"query_string": str, "referrer": str})
    d["ts"] = pd.to_datetime(d.ts, format="ISO8601", utc=True)
    d["ist"] = d.ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    d["err5"] = d.status >= 500
    print(f"local dataset: {len(d):,} rows\n")

    # Q01 overview
    o = bq("q01_overview").iloc[0]
    check("Q01 requests / unique IPs / endpoints",
          (o.requests, o.unique_ips, o.distinct_endpoints) == (len(d), d.client_ip.nunique(), d.endpoint.nunique()),
          f"{o.requests:,} / {o.unique_ips:,} / {o.distinct_endpoints}")
    check("Q01 4xx / 5xx counts and GiB sent",
          o.client_errors_4xx == d.status.between(400, 499).sum() and o.server_errors_5xx == d.err5.sum()
          and abs(o.gib_sent - d.bytes_sent.sum() / 2**30) < 0.01, f"{o.client_errors_4xx:,} / {o.server_errors_5xx:,} / {o.gib_sent} GiB")
    # Q02 status codes
    loc = d.groupby("status").size().rename("requests").reset_index()
    check("Q02 status code counts", *same(bq("q02_status_codes"), loc, ["status", "requests"], ["status"]))
    # Q03 top endpoints
    loc = d.groupby("endpoint").agg(requests=("status", "size"), unique_ips=("client_ip", "nunique"),
                                    errors_4xx=("status", lambda s: s.between(400, 499).sum()),
                                    errors_5xx=("err5", "sum")).reset_index()
    b3 = bq("q03_top_endpoints")
    check("Q03 top-20 endpoints (requests, unique IPs, 4xx, 5xx)",
          *same(b3, loc[loc.endpoint.isin(b3.endpoint)], ["endpoint", "requests", "unique_ips", "errors_4xx", "errors_5xx"], ["endpoint"]))
    check("Q03 ranking is the true top 20", set(b3.endpoint) == set(loc.nlargest(20, "requests").endpoint))
    # Q04 errors by endpoint
    loc = d.groupby("endpoint").agg(errors=("status", lambda s: (s >= 400).sum()), s404=("status", lambda s: (s == 404).sum()),
                                    s429=("status", lambda s: (s == 429).sum()), s500=("status", lambda s: (s == 500).sum())).reset_index()
    check("Q04 errors by endpoint (errors, 404, 429, 500)", *same(bq("q04_errors_by_endpoint"), loc[loc.errors >= 50],
                                                                  ["endpoint", "errors", "s404", "s429", "s500"], ["endpoint"]))
    # Q05 hourly
    loc = d.assign(hour_ist=d.ist.dt.floor("h")).groupby("hour_ist").agg(requests=("status", "size"), errors_5xx=("err5", "sum")).reset_index()
    check("Q05 hourly requests and 5xx (168 hours)", *same(bq("q05_hourly_volume", parse_dates=["hour_ist"]), loc,
                                                          ["hour_ist", "requests", "errors_5xx"], ["hour_ist"]))
    # Q06 daily
    loc = d.assign(day_ist=d.ist.dt.normalize()).groupby("day_ist").agg(requests=("status", "size"), unique_ips=("client_ip", "nunique")).reset_index()
    check("Q06 daily requests and unique IPs", *same(bq("q06_daily_summary", parse_dates=["day_ist"]), loc,
                                                     ["day_ist", "requests", "unique_ips"], ["day_ist"]))
    # Q07 profile
    loc = d.assign(weekday=d.ist.dt.strftime("%u-%a"), hour_of_day=d.ist.dt.hour).groupby(["weekday", "hour_of_day"]).size().rename("requests").reset_index()
    check("Q07 weekday x hour profile", *same(bq("q07_hour_of_day_profile"), loc, ["weekday", "hour_of_day", "requests"], ["weekday", "hour_of_day"]))
    # Q08 peak windows
    w5 = d.assign(w=d.ist.dt.floor("5min")).groupby("w").size()
    b8 = bq("q08_peak_5min_windows", parse_dates=["window_start_ist"])
    check("Q08 10 busiest 5-minute windows",
          all(w5.get(t) == n for t, n in zip(b8.window_start_ist, b8.requests)) and b8.requests.min() >= w5.nlargest(10).min(),
          f"busiest {b8.window_start_ist[0]} with {b8.requests[0]} requests")
    # Q09 top IPs
    pm = d.assign(m=d.ts.dt.floor("min")).groupby(["client_ip", "m"]).size().groupby("client_ip").max().rename("max_requests_per_minute")
    loc = d.groupby("client_ip").size().rename("requests").to_frame().join(pm).reset_index()
    b9 = bq("q09_top_ips")
    check("Q09 top-20 IPs (requests, max requests/minute)",
          *same(b9, loc[loc.client_ip.isin(b9.client_ip)], ["client_ip", "requests", "max_requests_per_minute"], ["client_ip"]))
    # Q10 5-minute failures
    loc = d.assign(bucket_ist=d.ist.dt.floor("5min")).groupby("bucket_ist").agg(requests=("status", "size"), failures=("err5", "sum")).reset_index()
    b10 = bq("q10_5min_failures_series", parse_dates=["bucket_ist"])
    check("Q10 5-minute requests and failures (2,016 buckets)", *same(b10, loc, ["bucket_ist", "requests", "failures"], ["bucket_ist"]))
    # Q11 spike detector re-implemented in pandas
    s = loc.sort_values("bucket_ist").reset_index(drop=True)
    f = s.failures.rolling(288, min_periods=1).sum().shift(13)
    r = s.requests.rolling(288, min_periods=1).sum().shift(13)
    n = s.failures.rolling(288, min_periods=1).count().shift(13)
    s["exp"] = s.requests * f / r
    s["z"] = (s.failures - s.exp) / np.sqrt(np.maximum(s.exp, 0.5))
    fl = s[(n >= 36) & (s.z >= 4) & (s.failures >= 8)].copy()
    fl["inc"] = (fl.bucket_ist.diff() > pd.Timedelta(minutes=10)).cumsum()
    inc = fl.groupby("inc").agg(start=("bucket_ist", "min"), end=("bucket_ist", "max"), buckets=("z", "size"), failed=("failures", "sum")).reset_index(drop=True)
    inc["end"] += pd.Timedelta(minutes=5)
    b11 = bq("q11_failure_spikes", parse_dates=["spike_start_ist", "spike_end_ist"])
    ok = len(b11) == len(inc) and all((b11.spike_start_ist.values == inc.start.values) & (b11.spike_end_ist.values == inc.end.values)
                                      & (b11.flagged_buckets.values == inc.buckets.values)
                                      & (b11.failed_requests_in_flagged_buckets.values == inc.failed.values))
    check("Q11 spike incidents identical to pandas re-implementation", ok, f"{len(b11)} incidents")
    # Q12-Q15
    lg = d[(d.endpoint == "/login") & (d.method == "POST")].assign(hour_ist=d.ist.dt.floor("h"))
    loc = lg.groupby(["client_ip", "hour_ist"]).agg(failed_logins=("status", lambda x: (x == 401).sum()),
                                                    successful_logins=("status", lambda x: (x == 200).sum())).reset_index()
    check("Q12 brute-force rows", *same(bq("q12_suspicious_bruteforce", parse_dates=["hour_ist"]), loc[loc.failed_logins >= 50],
                                        ["client_ip", "hour_ist", "failed_logins", "successful_logins"], ["client_ip", "hour_ist"]))
    pat = r"(?i)(?:\.env|\.git|wp-login|xmlrpc|phpmyadmin|/etc/passwd|server-status|actuator|backup|^/admin)"
    probe = d[d.path.str.contains(pat, regex=True) | d.query_string.str.contains(r"(?i)(?:%27|%20or%20|union|select)", regex=True)]
    loc = probe.groupby("client_ip").agg(probe_requests=("status", "size"), distinct_probe_paths=("path", "nunique")).reset_index()
    check("Q13 scanner rows", *same(bq("q13_suspicious_scanners"), loc[loc.probe_requests >= 10],
                                    ["client_ip", "probe_requests", "distinct_probe_paths"], ["client_ip"]))
    pmm = d.assign(m=d.ts.dt.floor("min")).groupby(["client_ip", "m"]).size()
    rates = pd.DataFrame({"max_rpm": pmm.groupby("client_ip").max(), "minutes_at_20plus_rpm": (pmm >= 20).groupby("client_ip").sum()})
    nb = d[d.ua_class != "search_bot"]
    loc = nb.groupby("client_ip").agg(requests=("status", "size"), rate_limited_429=("status", lambda x: (x == 429).sum())).join(rates).reset_index()
    check("Q14 high-rate client rows", *same(bq("q14_suspicious_high_rate"), loc[loc.minutes_at_20plus_rpm >= 30],
                                             ["client_ip", "requests", "max_rpm", "minutes_at_20plus_rpm", "rate_limited_429"], ["client_ip"]))
    loc = d.groupby("ua_class").agg(requests=("status", "size"), unique_ips=("client_ip", "nunique")).reset_index()
    check("Q15 user-agent classes", *same(bq("q15_user_agent_classes"), loc, ["ua_class", "requests", "unique_ips"], ["ua_class"]))

    # ---- detections vs planted ground truth
    print("\nDETECTIONS vs PLANTED INCIDENTS (data/incidents.json)")
    gt = {i["id"]: i for i in json.loads((HERE / "data" / "incidents.json").read_text())["incidents"]}
    tz = lambda x: pd.Timestamp(x).tz_convert("Asia/Kolkata").tz_localize(None)
    for iid in ("I1", "I2"):
        g = gt[iid]; gs, ge = tz(g["start"]), tz(g["end"])
        hit = b11[(b11.spike_start_ist < ge) & (b11.spike_end_ist > gs)]
        check(f"{iid} {g['type']} detected by Q11", len(hit) > 0,
              "; ".join(f"{x.spike_start_ist:%d %H:%M}-{x.spike_end_ist:%H:%M}" for x in hit.itertuples()) + f"  (truth {gs:%d %H:%M}-{ge:%H:%M})")
    fp = [x for x in b11.itertuples() if not any((x.spike_start_ist < tz(gt[i]["end"])) and (x.spike_end_ist > tz(gt[i]["start"])) for i in ("I1", "I2"))]
    print(f"INFO  Q11 incidents not matching a planted 5xx incident (false positives): {len(fp)} "
          + "; ".join(f"{x.spike_start_ist:%d %H:%M}-{x.spike_end_ist:%H:%M} ({x.failed_requests_in_flagged_buckets} failures, z={x.max_z_score})" for x in fp))
    check("I3 credential-stuffing IPs == Q12 IPs", set(bq("q12_suspicious_bruteforce").client_ip) == set(gt["I3"]["ips"]))
    check("I5 scanner IP == Q13 IPs", set(bq("q13_suspicious_scanners").client_ip) == set(gt["I5"]["ips"]))
    q14 = bq("q14_suspicious_high_rate")
    sip = gt["I4"]["ips"][0]
    rej = sum(1 for l in open(HERE / "data" / "processed" / "rejected_lines.txt", encoding="utf-8") if l.split(": ", 1)[1].startswith(sip))
    row = q14.set_index("client_ip").loc[sip] if sip in set(q14.client_ip) else None
    check("I4 scraper IP found by Q14; counts consistent with generator minus parser-rejected lines",
          row is not None and int(row.requests) + rej == gt["I4"]["requests"]
          and gt["I4"]["throttled_429"] - rej <= int(row.rate_limited_429) <= gt["I4"]["throttled_429"],
          f"generated {gt['I4']['requests']} lines, {rej} truncated & rejected -> {int(row.requests) if row is not None else 0} loaded; "
          f"429s {int(row.rate_limited_429) if row is not None else 0} of {gt['I4']['throttled_429']} generated; "
          f"other Q14 IPs: {sorted(set(q14.client_ip) - {sip})} (= I3 attackers)")
    b8top = b8.window_start_ist[0]
    check("I6 sale campaign contains the busiest 5-minute window", tz(gt["I6"]["start"]) <= b8top < tz(gt["I6"]["end"]), f"{b8top}")
    pd.DataFrame(checks).to_csv(RES / "verification.csv", index=False)
    print(f"\n{sum(c['result'] == 'PASS' for c in checks)}/{len(checks)} checks passed")


if __name__ == "__main__":
    main()
