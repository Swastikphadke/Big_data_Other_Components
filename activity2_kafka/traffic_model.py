"""
Activity 2 - synthetic smart-city traffic model.

Simulates one weekday (06:00-22:00, one reading per junction per minute) for
12 Bengaluru junctions.  The model is SIMPLIFIED and ILLUSTRATIVE (not a
calibrated traffic-engineering model):

    demand(t)   = off-peak base + morning peak (09:30) + evening peak (18:45)
    v/c(t)      = junction_severity * demand(t)            (volume / capacity)
    count(t)    = capacity * min(v/c, 1)                    vehicles per minute
    speed(t)    = free_flow * max(0.18, 1 - 0.8 * (v/c)^2.5) km/h

Gaussian noise is added to the published readings.  The NOISE-FREE values give
a ground-truth state per junction-minute, used later to evaluate the detector.

Planted patterns (documented in data/planted_patterns.json):
  * heavy junctions congest at both peaks, medium ones briefly, light ones never
  * INCIDENT at J04 Marathahalli 14:00-14:44 (speed ~7 km/h, flow ~35 % of normal)
  * SENSOR GLITCH at J07 Richmond Circle 12:10 (one reading: 3 km/h, 0 vehicles)

Run directly to write data/traffic_readings.csv and data/ground_truth.csv.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from config import CONGESTION_MIN_COUNT, CONGESTION_SPEED_KMPH

SEED = 7
SIM_DATE = "2025-11-03"          # a Monday
START, END = "06:00", "22:00"    # simulated operating window (inclusive start, exclusive end)
DATA = Path(__file__).parent / "data"

# id, name, free-flow speed km/h, capacity veh/min, peak severity (v/c at peak), class
JUNCTIONS = [
    ("J01", "Silk Board",         40, 130, 1.25, "heavy"),
    ("J02", "Hebbal Flyover",     45, 125, 1.20, "heavy"),
    ("J03", "KR Puram",           40, 115, 1.15, "heavy"),
    ("J04", "Marathahalli",       42, 105, 1.00, "medium"),
    ("J05", "Electronic City",    50, 100, 0.98, "medium"),
    ("J06", "Mekhri Circle",      38,  90, 0.97, "medium"),
    ("J07", "Richmond Circle",    35,  80, 0.70, "light"),
    ("J08", "Banashankari",       40,  85, 0.78, "light"),
    ("J09", "Yeshwanthpur",       42,  95, 0.82, "light"),
    ("J10", "Goraguntepalya",     45, 110, 0.75, "light"),
    ("J11", "Sony World Signal",  35,  75, 0.70, "light"),
    ("J12", "Trinity Circle",     38,  80, 0.65, "light"),
]
INCIDENT = {"junction_id": "J04", "start": "14:00", "end": "14:45"}
GLITCH = {"junction_id": "J07", "time": "12:10"}


def _gauss(h, mu, sigma):
    return np.exp(-0.5 * ((h - mu) / sigma) ** 2)


def demand(hour):
    """Relative demand 0..1 for fractional hour of day."""
    return 0.28 + 0.72 * np.maximum(_gauss(hour, 9.5, 0.85), 0.95 * _gauss(hour, 18.75, 0.95)) \
        + 0.10 * _gauss(hour, 13.0, 1.2)


def clean_values(free_flow, cap, sev, hour):
    vc = sev * demand(hour)
    count = cap * np.minimum(vc, 1.0)
    speed = free_flow * np.maximum(0.18, 1 - 0.8 * np.power(vc, 2.5))
    return count, speed


def generate():
    """Return (readings, ground_truth) DataFrames, deterministic for SEED."""
    rng = np.random.default_rng(SEED)
    t0 = datetime.fromisoformat(f"{SIM_DATE}T{START}")
    minutes = int((datetime.fromisoformat(f"{SIM_DATE}T{END}") - t0).total_seconds() // 60)
    times = [t0 + timedelta(minutes=m) for m in range(minutes)]
    hours = np.array([t.hour + t.minute / 60 for t in times])
    inc_s = datetime.fromisoformat(f"{SIM_DATE}T{INCIDENT['start']}")
    inc_e = datetime.fromisoformat(f"{SIM_DATE}T{INCIDENT['end']}")
    glitch_t = datetime.fromisoformat(f"{SIM_DATE}T{GLITCH['time']}")

    rows, truth = [], []
    for jid, name, ff, cap, sev, cls in JUNCTIONS:
        c_count, c_speed = clean_values(ff, cap, sev, hours)
        n_count = np.maximum(0, c_count * rng.normal(1, 0.08, len(hours)) + rng.normal(0, 2, len(hours)))
        n_speed = np.clip(c_speed + rng.normal(0, 2.0, len(hours)), 2, ff + 8)
        for i, t in enumerate(times):
            cc, cs, nc, ns = c_count[i], c_speed[i], n_count[i], n_speed[i]
            state = "FREE_FLOW"
            if jid == INCIDENT["junction_id"] and inc_s <= t < inc_e:
                cc, cs = cc * 0.35, 7.0
                nc, ns = cc * rng.normal(1, 0.10), max(2.0, cs + rng.normal(0, 1.5))
                state = "INCIDENT"
            elif cs < CONGESTION_SPEED_KMPH and cc >= CONGESTION_MIN_COUNT:
                state = "CONGESTED"
            if jid == GLITCH["junction_id"] and t == glitch_t:
                nc, ns = 0, 3.0      # faulty sensor sample; true traffic unchanged
            rows.append({
                "sensor_id": f"S-{jid}", "junction_id": jid, "junction_name": name,
                "event_time": t.isoformat(), "vehicle_count": int(round(nc)),
                "avg_speed_kmph": round(float(ns), 1),
            })
            truth.append({"junction_id": jid, "junction_name": name, "class": cls,
                          "event_time": t.isoformat(), "true_count": round(float(cc), 1),
                          "true_speed": round(float(cs), 1), "true_state": state})
    readings = pd.DataFrame(rows).sort_values(["event_time", "junction_id"]).reset_index(drop=True)
    return readings, pd.DataFrame(truth)


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    r, g = generate()
    r.to_csv(DATA / "traffic_readings.csv", index=False)
    g.to_csv(DATA / "ground_truth.csv", index=False)
    (DATA / "planted_patterns.json").write_text(json.dumps({
        "seed": SEED, "date": SIM_DATE, "window": [START, END],
        "junctions": [dict(zip(["id", "name", "free_flow_kmph", "capacity_veh_min",
                                "peak_severity", "class"], j)) for j in JUNCTIONS],
        "incident": INCIDENT, "sensor_glitch": GLITCH,
        "peaks": {"morning_center": "09:30", "evening_center": "18:45"}}, indent=2))
    print(f"readings: {len(r):,} rows -> {DATA / 'traffic_readings.csv'}")
    print("ground-truth minutes by junction and state:")
    print(g.pivot_table(index=["junction_id", "junction_name", "class"], columns="true_state",
                        values="event_time", aggfunc="count", fill_value=0).to_string())
