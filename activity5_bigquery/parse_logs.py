"""
Activity 5 - ETL step: parse raw Apache combined logs into a typed CSV for BigQuery.

  data/raw/*.log.gz  ->  data/processed/access_logs.csv.gz   (loaded with `bq load`)
                     ->  data/processed/rejected_lines.txt   (lines that do not match the format)

Derived columns: endpoint (path template, ids replaced by {id}), query_string,
ua_class (browser / mobile_browser / mobile_app / search_bot / script_or_tool).
Timestamps keep their +05:30 offset; BigQuery stores TIMESTAMP in UTC.
"""
import argparse
import csv
import gzip
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

HERE = Path(__file__).parent
LINE = re.compile(r'^(?P<ip>\S+) \S+ \S+ \[(?P<d>\d{2})/(?P<mon>\w{3})/(?P<y>\d{4}):(?P<t>\d{2}:\d{2}:\d{2}) (?P<tz>[+-]\d{4})\] '
                  r'"(?P<method>[A-Z]+) (?P<target>\S+) (?P<proto>HTTP/[\d.]+)" (?P<status>\d{3}) (?P<bytes>\d+|-) '
                  r'"(?P<ref>[^"]*)" "(?P<ua>[^"]*)" (?P<ms>\d+)$')
MON = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
COLUMNS = ["ts", "client_ip", "method", "endpoint", "path", "query_string", "protocol", "status", "bytes_sent",
           "response_ms", "referrer", "user_agent", "ua_class"]


def template(path):
    path = re.sub(r"^/products/\d+$", "/products/{id}", path)
    return re.sub(r"^/images/products/\d+\.jpg$", "/images/products/{id}.jpg", path)


def ua_class(ua):
    u = ua.lower()
    if "googlebot" in u or "bingbot" in u:
        return "search_bot"
    if u.startswith("shopapp/"):
        return "mobile_app"
    if any(k in u for k in ("python-requests", "curl", "nmap", "sqlmap", "harvester", "scrapy", "wget")):
        return "script_or_tool"
    if "mobile" in u or "iphone" in u or "android" in u:
        return "mobile_browser"
    return "browser" if u.startswith("mozilla") else "other"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    out_dir = HERE / "data" / "processed"; out_dir.mkdir(parents=True, exist_ok=True)
    ok = bad = 0
    with gzip.open(out_dir / "access_logs.csv.gz", "wt", newline="", encoding="utf-8") as fo, \
            open(out_dir / "rejected_lines.txt", "w", encoding="utf-8") as fr:
        w = csv.writer(fo); w.writerow(COLUMNS)
        for src in sorted((HERE / "data" / "raw").glob("*.log.gz")):
            with gzip.open(src, "rt", encoding="utf-8") as fi:
                for n, line in enumerate(fi, 1):
                    m = LINE.match(line.rstrip("\n"))
                    if not m:
                        bad += 1; fr.write(f"{src.name}:{n}: {line}"); continue
                    g = m.groupdict()
                    path, _, qs = g["target"].partition("?")
                    tz = f"{g['tz'][:3]}:{g['tz'][3:]}"
                    ts = f"{g['y']}-{MON[g['mon']]:02d}-{g['d']} {g['t']}{tz}"
                    w.writerow([ts, g["ip"], g["method"], template(path), path, qs, g["proto"], int(g["status"]),
                                0 if g["bytes"] == "-" else int(g["bytes"]), int(g["ms"]),
                                "" if g["ref"] == "-" else g["ref"], g["ua"], ua_class(g["ua"])])
                    ok += 1
    size = (out_dir / "access_logs.csv.gz").stat().st_size / 1e6
    print(f"parsed {ok:,} lines, rejected {bad} malformed lines -> data/processed/access_logs.csv.gz ({size:.1f} MB gzip)")
    print(f"columns: {COLUMNS}")


if __name__ == "__main__":
    main()
