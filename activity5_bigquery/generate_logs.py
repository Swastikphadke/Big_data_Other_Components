"""
Activity 5 - synthetic web-server access logs (SYNTHETIC DATA).

7 days (Mon 26-Oct-2026 00:00 to Sun 01-Nov-2026 23:59 IST) of an online shop
(shop.example.in) in Apache "combined" format plus response time in ms:

  IP - - [dd/Mon/yyyy:HH:MM:SS +0530] "METHOD /path?query HTTP/1.1" status bytes "referrer" "user-agent" ms

Normal traffic follows a daily cycle (quiet 02-06 h, peaks around noon and 20-22 h),
weekend evenings are busier. Planted incidents (ground truth -> data/incidents.json):
  I1 payment outage        Wed 28-Oct 14:10-14:35   /api/v1/payments, /checkout -> 503/504
  I2 bad deployment        Fri 30-Oct 09:00-10:30   /api/v1/recommendations -> 500
  I3 credential stuffing   Thu 29-Oct 02:00-03:00   203.0.113.17-19 POST /login -> mostly 401
  I4 product scraper       Sat 31-Oct 06:00-18:00   198.51.100.77 crawls /products/{id} -> 429 once throttled
  I5 vulnerability scan    Tue 27-Oct 22:00-22:20   198.51.100.200 probes /.env, /wp-login.php ... -> 404/403
  I6 sale campaign         Fri 30-Oct 20:00-22:00   traffic x1.7
Attacker addresses use the documentation ranges 203.0.113.0/24 and 198.51.100.0/24.
25 deliberately truncated lines test the parser's error handling.
Writes data/raw/access_log_2026-10-26_11-01.log.gz
"""
import argparse
import gzip
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import teelog  # noqa: E402

HERE = Path(__file__).parent
RAW = HERE / "data" / "raw"
IST = timezone(timedelta(hours=5, minutes=30))
START = datetime(2026, 10, 26, tzinfo=IST)   # Monday; recent week (sandbox expires partitions > 60 days old)
DAYS = 7
SEED = 55
rng = np.random.default_rng(SEED)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# endpoint, method, share, median latency ms, median bytes, status table [(code, p)]
ENDPOINTS = [
    ("/", "GET", 8.0, 110, 18000, [(200, .995)]),
    ("/products", "GET", 10.0, 140, 42000, [(200, .995)]),
    ("/products/{id}", "GET", 22.0, 120, 26000, [(200, .97), (404, .025)]),
    ("/search", "GET", 9.0, 260, 30000, [(200, .99)]),
    ("/cart", "GET", 5.0, 90, 9000, [(200, .995)]),
    ("/cart/add", "POST", 4.0, 110, 600, [(200, .99)]),
    ("/checkout", "GET", 2.0, 180, 15000, [(200, .993)]),
    ("/api/v1/payments", "POST", 1.2, 420, 900, [(200, .975), (402, .02)]),
    ("/api/v1/orders", "POST", 1.5, 300, 1200, [(201, .99)]),
    ("/login", "GET", 1.5, 80, 7000, [(200, .997)]),
    ("/login", "POST", 1.5, 150, 500, [(200, .9), (401, .095)]),
    ("/logout", "GET", 0.6, 40, 300, [(302, .998)]),
    ("/account", "GET", 2.0, 130, 11000, [(200, .99)]),
    ("/wishlist", "GET", 1.5, 120, 8000, [(200, .99)]),
    ("/api/v1/recommendations", "GET", 6.0, 180, 4000, [(200, .997)]),
    ("/static/js/app.js", "GET", 7.0, 12, 210000, [(200, .7), (304, .3)]),
    ("/static/css/main.css", "GET", 6.0, 10, 48000, [(200, .7), (304, .3)]),
    ("/images/products/{id}.jpg", "GET", 9.0, 25, 85000, [(200, .75), (304, .24)]),
    ("/favicon.ico", "GET", 1.0, 5, 4000, [(200, .6), (304, .4)]),
]
HOUR_W = np.array([.55, .35, .22, .15, .13, .17, .30, .55, .85, 1.05, 1.2, 1.35, 1.45, 1.35, 1.25, 1.2, 1.2,
                   1.25, 1.4, 1.6, 1.8, 1.85, 1.5, .95])          # IST hour-of-day profile
BASE_PER_MIN = 72
UAS = {"desktop": ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
                   "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0"],
       "mobile": ["Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36",
                  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1"],
       "app": ["ShopApp/5.2.1 (Android 14; build 5210)", "ShopApp/5.2.0 (iOS 17.6; build 5200)"],
       "bot": ["Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
               "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"]}
SEARCH_TERMS = ["shoes", "laptop", "kurta", "phone+case", "headphones", "rice", "saree", "watch", "backpack", "tv"]


def iso(day, h, m=0):
    return (START + timedelta(days=day, hours=h, minutes=m)).isoformat()


def fmt(t, ip, method, path, status, nbytes, ref, ua, ms):
    return (f'{ip} - - [{t.day:02d}/{MONTHS[t.month - 1]}/{t.year}:{t:%H:%M:%S} +0530] "{method} {path} HTTP/1.1" '
            f'{status} {nbytes} "{ref}" "{ua}" {ms}')


def path_for(ep):
    if ep == "/products/{id}":
        return f"/products/{rng.integers(1000, 60000)}"
    if ep == "/images/products/{id}.jpg":
        return f"/images/products/{rng.integers(1000, 60000)}.jpg"
    if ep == "/search":
        return f"/search?q={SEARCH_TERMS[rng.integers(len(SEARCH_TERMS))]}&page={rng.integers(1, 4)}"
    if ep == "/products":
        return f"/products?category={['electronics', 'fashion', 'home', 'books', 'grocery'][rng.integers(5)]}"
    return ep


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--log"); a = ap.parse_args(); teelog.start(a.log)
    RAW.mkdir(parents=True, exist_ok=True)
    # ---- client population: 24,000 IPs with skewed activity, each with a fixed user agent class
    n_ip = 24000
    first = rng.choice([49, 103, 106, 117, 122, 157, 171, 182, 223], n_ip)
    ips = np.array([f"{f}.{b}.{c}.{d}" for f, b, c, d in zip(first, rng.integers(1, 255, n_ip),
                                                               rng.integers(0, 255, n_ip), rng.integers(1, 255, n_ip))])
    ip_w = rng.pareto(1.3, n_ip) + 0.05
    cls = rng.choice(["desktop", "mobile", "app", "bot"], n_ip, p=[.50, .37, .11, .02])
    ip_w[cls == "bot"] *= 2.5                                # crawlers are busier than people
    ip_ua = np.array([UAS[c][rng.integers(len(UAS[c]))] for c in cls])
    ip_p = ip_w / ip_w.sum()
    ep_p = np.array([e[2] for e in ENDPOINTS]); ep_p /= ep_p.sum()

    lines = []     # (epoch_seconds, line)
    for m in range(DAYS * 24 * 60):
        t0 = START + timedelta(minutes=m)
        rate = BASE_PER_MIN * HOUR_W[t0.hour]
        if t0.weekday() >= 5 and t0.hour >= 17:
            rate *= 1.15                                     # weekend evenings
        if t0.date() == (START + timedelta(days=4)).date() and 20 <= t0.hour < 22:
            rate *= 1.7                                      # I6 sale campaign
        n = rng.poisson(rate)
        if n == 0:
            continue
        secs = np.sort(rng.integers(0, 60, n))
        who = rng.choice(n_ip, n, p=ip_p)
        eps = rng.choice(len(ENDPOINTS), n, p=ep_p)
        for s, w, e in zip(secs, who, eps):
            t = t0 + timedelta(seconds=int(s))
            ep, method, _, lat, size, table = ENDPOINTS[e]
            if cls[w] == "bot" and ep not in ("/", "/products", "/products/{id}", "/search", "/images/products/{id}.jpg",
                                              "/static/js/app.js", "/static/css/main.css", "/favicon.ico"):
                ep, method, _, lat, size, table = ENDPOINTS[2]          # crawlers only fetch public pages
            u = rng.random(); status, acc = 500, 0.0
            for code, p in table:
                acc += p
                if u < acc:
                    status = code; break
            else:
                status = 500 if rng.random() < .6 else 503      # residual baseline server errors
            if t0.date() == (START + timedelta(days=2)).date() and t0.hour == 14 and 10 <= t0.minute < 35 \
                    and ep in ("/api/v1/payments", "/checkout") and rng.random() < .7:
                status = 503 if rng.random() < .7 else 504; lat = 3000                 # I1
            if t0.date() == (START + timedelta(days=4)).date() and (t0.hour == 9 or (t0.hour == 10 and t0.minute < 30)) \
                    and ep == "/api/v1/recommendations" and rng.random() < .3:
                status = 500                                                            # I2
            ms = int(rng.lognormal(np.log(lat), .45)) if status < 500 or lat >= 3000 else int(rng.lognormal(np.log(lat * 2), .5))
            nbytes = 0 if status == 304 else int(rng.lognormal(np.log(size), .3)) if status < 400 else int(rng.integers(150, 600))
            ref = "-" if cls[w] in ("bot", "app") or rng.random() < .3 else f"https://shop.example.in{['/', '/products', '/search?q=shoes'][rng.integers(3)]}"
            lines.append((t.timestamp(), fmt(t, ips[w], method, path_for(ep), status, nbytes, ref, ip_ua[w], ms)))
    n_normal = len(lines)

    incidents = []
    # ---- I3 credential stuffing
    cs_ips = ["203.0.113.17", "203.0.113.18", "203.0.113.19"]
    t, end, n3 = START + timedelta(days=3, hours=2), START + timedelta(days=3, hours=3), 0
    while t < end:
        for ip in cs_ips:
            ok = rng.random() < .03
            lines.append((t.timestamp(), fmt(t, ip, "POST", "/login", 200 if ok else 401, int(rng.integers(300, 600)), "-",
                                             "python-requests/2.31.0", int(rng.lognormal(np.log(140), .3)))))
            n3 += 1
        t += timedelta(seconds=float(rng.uniform(1.0, 2.6)))
    incidents.append({"id": "I3", "type": "credential stuffing", "ips": cs_ips, "start": iso(3, 2),
                      "end": iso(3, 3), "requests": n3})
    # ---- I4 scraper with rate limiting
    t, end, pid, n4, n429 = START + timedelta(days=5, hours=6), START + timedelta(days=5, hours=18), 1000, 0, 0
    while t < end:
        throttled = t >= START + timedelta(days=5, hours=7) and rng.random() < .35
        status = 429 if throttled else (404 if rng.random() < .025 else 200)
        n429 += status == 429
        lines.append((t.timestamp(), fmt(t, "198.51.100.77", "GET", f"/products/{pid}", status,
                                         int(rng.integers(150, 400)) if status != 200 else int(rng.lognormal(np.log(26000), .3)), "-",
                                         "Mozilla/5.0 (compatible; DataHarvester/2.1; +http://bot.example.net)", int(rng.lognormal(np.log(110), .4)))))
        pid += 1; n4 += 1
        t += timedelta(seconds=float(rng.uniform(1.0, 2.2)))
    incidents.append({"id": "I4", "type": "scraper", "ips": ["198.51.100.77"], "start": iso(5, 6),
                      "end": iso(5, 18), "requests": n4, "throttled_429": int(n429)})
    # ---- I5 vulnerability scan
    probes = [("/.env", 404), ("/wp-login.php", 404), ("/phpmyadmin/", 404), ("/admin/config.php", 403), ("/.git/config", 404),
              ("/server-status", 403), ("/cgi-bin/../../etc/passwd", 400), ("/api/v1/users?id=1%27%20OR%20%271%27=%271", 400),
              ("/backup.zip", 404), ("/admin", 403), ("/xmlrpc.php", 404), ("/actuator/env", 404)]
    t, end, n5 = START + timedelta(days=1, hours=22), START + timedelta(days=1, hours=22, minutes=20), 0
    while t < end:
        p, st = probes[rng.integers(len(probes))]
        lines.append((t.timestamp(), fmt(t, "198.51.100.200", ["GET", "POST"][rng.random() < .15], p, st,
                                         int(rng.integers(150, 500)), "-", "Mozilla/5.0 (compatible; Nmap Scripting Engine)", int(rng.integers(3, 30)))))
        n5 += 1; t += timedelta(seconds=float(rng.uniform(0.6, 1.4)))
    incidents.append({"id": "I5", "type": "vulnerability scan", "ips": ["198.51.100.200"], "start": iso(1, 22),
                      "end": iso(1, 22, 20), "requests": n5})
    incidents = [{"id": "I1", "type": "payment outage (5xx)", "endpoints": ["/api/v1/payments", "/checkout"],
                  "start": iso(2, 14, 10), "end": iso(2, 14, 35)},
                 {"id": "I2", "type": "bad deployment (500)", "endpoints": ["/api/v1/recommendations"],
                  "start": iso(4, 9), "end": iso(4, 10, 30)}] + incidents + \
                [{"id": "I6", "type": "sale campaign traffic peak (x1.7)", "start": iso(4, 20),
                  "end": iso(4, 22)}]

    lines.sort(key=lambda x: x[0])
    out = [l for _, l in lines]
    bad_idx = sorted(rng.choice(len(out), 25, replace=False))
    for i in bad_idx:                                       # truncated writes (e.g. log rotation)
        out[i] = out[i][: int(rng.integers(20, 60))]
    fn = RAW / "access_log_2026-10-26_11-01.log.gz"
    with gzip.open(fn, "wt", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    meta = {"seed": SEED, "site": "shop.example.in", "period_ist": [iso(0, 0), iso(7, 0)],
            "lines": len(out), "normal_requests": n_normal, "malformed_lines": 25, "client_ips": n_ip,
            "incidents": incidents}
    (HERE / "data" / "incidents.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {len(out):,} log lines ({n_normal:,} normal + {len(out) - n_normal:,} incident; 25 malformed) "
          f"-> {fn.relative_to(HERE)} ({fn.stat().st_size / 1e6:.1f} MB gzip)")
    for i in incidents:
        print(f"  {i['id']} {i['type']:<34} {i['start'][:16]} - {i['end'][11:16]}  " + (f"requests={i['requests']}" if "requests" in i else ""))
    print("sample lines:"); [print("  " + out[k]) for k in (0, len(out) // 2)]


if __name__ == "__main__":
    main()
