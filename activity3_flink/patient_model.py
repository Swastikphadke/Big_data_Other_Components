"""
Activity 3 - synthetic patient vital-sign stream (SYNTHETIC DATA, EDUCATIONAL THRESHOLDS).

10 patients, one reading every 5 s of event time, 10:00-12:00 (14,400 readings):
heart rate (bpm), SpO2 (%), body temperature (deg C).

Planted, documented patterns (ground truth in data/):
  SUSTAINED episodes  - abnormal for many minutes  -> must raise EPISODE alerts
  TRANSIENT bursts    - abnormal for 30-40 s (6-8 readings, below the 9-of-12 rule) -> reading alerts only
  ISOLATED spikes     - one abnormal reading (artefact) -> reading alert only
Network behaviour (for event-time testing): every reading gets a delivery delay.
  ~90 % arrive within 2 s, ~9.5 % are out of order (5-25 s late, inside the 30 s
  watermark bound), ~0.5 % are very late (45-150 s, beyond the bound).
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
DATA = HERE / "data"
T = json.loads((HERE / "thresholds.json").read_text())
SEED = 11
START = datetime(2025, 11, 3, 10, 0, 0)
DURATION_S = 2 * 3600
STEP = T["reading_interval_s"]

PATIENTS = [  # id, bed, baseline HR, SpO2, temperature
    ("P01", "ICU-1", 72, 97.5, 36.8), ("P02", "ICU-2", 84, 96.8, 37.0), ("P03", "ICU-3", 66, 98.0, 36.6),
    ("P04", "ICU-4", 78, 96.5, 36.9), ("P05", "ICU-5", 70, 97.8, 36.7), ("P06", "ICU-6", 80, 97.0, 37.0),
    ("P07", "ICU-7", 64, 98.2, 36.5), ("P08", "ICU-8", 88, 96.4, 37.1), ("P09", "ICU-9", 60, 97.6, 36.7),
    ("P10", "ICU-10", 75, 97.2, 36.8),
]
t = lambda hms: START.replace(hour=int(hms[:2]), minute=int(hms[3:5]), second=int(hms[6:8]))

# kind, patient, vital, start, end, level   (level = value held during the episode)
EPISODES = [
    ("SUSTAINED", "P02", "heart_rate", "10:20:00", "10:32:00", 138),    # tachycardia 12 min
    ("SUSTAINED", "P04", "spo2",       "10:45:00", "10:55:00", 88.0),   # desaturation 10 min
    ("SUSTAINED", "P08", "heart_rate", "11:15:00", "11:30:00", 128),    # multi-vital deterioration
    ("SUSTAINED", "P08", "spo2",       "11:15:00", "11:30:00", 89.0),
    ("SUSTAINED", "P09", "heart_rate", "11:00:00", "11:08:00", 46),     # bradycardia 8 min
    ("TRANSIENT", "P01", "heart_rate", "10:10:00", "10:10:30", 132),    # 6 readings
    ("TRANSIENT", "P05", "spo2",       "11:20:00", "11:20:40", 89.5),   # 8 readings
]
FEVER = {"patient": "P06", "ramp_start": "10:30:00", "peak": "11:10:00", "plateau_end": "11:40:00",
         "recovered": "11:55:00", "peak_c": 39.0}                       # sustained fever, gradual
ISOLATED = [  # patient, time, vital, value
    ("P03", "10:05:35", "heart_rate", 165), ("P10", "10:15:20", "heart_rate", 158),
    ("P05", "10:27:45", "temperature", 35.1), ("P07", "10:40:10", "spo2", 84.0),
    ("P09", "10:52:10", "heart_rate", 170), ("P10", "11:05:50", "temperature", 39.4),
    ("P02", "11:12:40", "spo2", 83.0), ("P03", "11:33:15", "spo2", 85.0),
    ("P01", "11:42:30", "spo2", 86.0), ("P07", "11:50:05", "heart_rate", 42),
]


def abnormal_flags(hr, spo2, temp):
    return {"hr_abnormal": hr > T["heart_rate_high_bpm"] or hr < T["heart_rate_low_bpm"],
            "spo2_abnormal": spo2 < T["spo2_low_pct"],
            "temp_abnormal": temp > T["temperature_high_c"] or temp < T["temperature_low_c"]}


def fever_curve(ts, base):
    rs, pk, pe, rc = (t(FEVER[k]) for k in ("ramp_start", "peak", "plateau_end", "recovered"))
    if ts < rs or ts >= rc:
        return base
    if ts < pk:
        return base + (FEVER["peak_c"] - base) * (ts - rs) / (pk - rs)
    if ts < pe:
        return FEVER["peak_c"]
    return FEVER["peak_c"] - (FEVER["peak_c"] - base - 0.2) * (ts - pe) / (rc - pe)


def generate():
    rng = np.random.default_rng(SEED)
    n = DURATION_S // STEP
    rows = []
    for pid, bed, hr0, sp0, tp0 in PATIENTS:
        drift = rng.uniform(0, 2 * np.pi)
        for i in range(n):
            ts = START + timedelta(seconds=i * STEP)
            hr = hr0 + 4 * np.sin(i / 120 + drift) + rng.normal(0, 2.5)
            sp = sp0 + rng.normal(0, 0.5)
            tp = tp0 + 0.1 * np.sin(i / 300 + drift) + rng.normal(0, 0.06)
            label = "NORMAL"
            if pid == FEVER["patient"]:
                tp = fever_curve(ts, tp0) + rng.normal(0, 0.06)
            for kind, p, vital, s, e, level in EPISODES:
                if p == pid and t(s) <= ts < t(e):
                    noise = rng.normal(0, 3 if vital == "heart_rate" else 0.6)
                    if vital == "heart_rate":
                        hr = level + noise
                    else:
                        sp = level + noise
                    label = kind
            for p, hms, vital, val in ISOLATED:
                if p == pid and ts == t(hms):
                    hr, sp, tp = (val, sp, tp) if vital == "heart_rate" else (hr, val, tp) if vital == "spo2" else (hr, sp, val)
                    label = "ISOLATED"
            hr, sp, tp = int(round(hr)), round(float(min(sp, 100.0)), 1), round(float(tp), 2)
            f = abnormal_flags(hr, sp, tp)
            if pid == FEVER["patient"] and label == "NORMAL" and f["temp_abnormal"]:
                label = "SUSTAINED"          # the fever plateau
            rows.append({"patient_id": pid, "bed": bed, "event_time": ts, "seq": i,
                         "heart_rate": hr, "spo2": sp, "temperature": tp, "label": label, **f})
    df = pd.DataFrame(rows)
    # ---- delivery delay (network / device buffering) -> out-of-order arrival
    u = rng.random(len(df))
    delay = np.where(u < 0.90, rng.uniform(0, 2, len(df)),
                     np.where(u < 0.995, rng.uniform(5, 25, len(df)), rng.uniform(45, 150, len(df))))
    df["delay_s"] = delay.round(2)
    df["arrival_time"] = df.event_time + pd.to_timedelta(df.delay_s, unit="s")
    df["delay_class"] = np.select([delay < 3, delay <= T["watermark_max_out_of_orderness_s"]],
                                  ["ON_TIME", "OUT_OF_ORDER"], "VERY_LATE")
    return df.sort_values("arrival_time").reset_index(drop=True)


def planted_events():
    """Ground truth per planted event (what the system SHOULD report)."""
    rows = []
    for kind, p, vital, s, e, level in EPISODES:
        rows.append({"kind": kind, "patient_id": p, "vital": vital, "true_start": t(s), "true_end": t(e)})
    # fever: noise-free curve crosses 38.0 C on the way up and on the way down
    up = t(FEVER["ramp_start"]) + (t(FEVER["peak"]) - t(FEVER["ramp_start"])) * (
        (T["temperature_high_c"] - 37.0) / (FEVER["peak_c"] - 37.0))
    down = t(FEVER["plateau_end"]) + (t(FEVER["recovered"]) - t(FEVER["plateau_end"])) * (
        (FEVER["peak_c"] - T["temperature_high_c"]) / (FEVER["peak_c"] - 37.0 - 0.2))
    rows.append({"kind": "SUSTAINED", "patient_id": FEVER["patient"], "vital": "temperature",
                 "true_start": up.replace(microsecond=0), "true_end": down.replace(microsecond=0)})
    for p, hms, vital, val in ISOLATED:
        rows.append({"kind": "ISOLATED", "patient_id": p, "vital": vital, "true_start": t(hms), "true_end": t(hms)})
    return pd.DataFrame(rows).sort_values(["kind", "patient_id", "true_start"]).reset_index(drop=True)


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    df = generate()
    df.to_csv(DATA / "vitals_readings.csv", index=False)
    ev = planted_events()
    ev.to_csv(DATA / "planted_events.csv", index=False)
    (DATA / "planted_patterns.json").write_text(json.dumps(
        {"seed": SEED, "start": START.isoformat(), "duration_s": DURATION_S, "step_s": STEP,
         "patients": PATIENTS, "episodes": EPISODES, "fever": FEVER, "isolated": ISOLATED,
         "disclaimer": T["DISCLAIMER"]}, indent=2, default=str))
    print(T["DISCLAIMER"])
    print(f"readings: {len(df):,}  patients: {df.patient_id.nunique()}  -> {DATA / 'vitals_readings.csv'}")
    print("labels:", df.label.value_counts().to_dict())
    print("delivery:", df.delay_class.value_counts().to_dict())
    print("abnormal readings:", int((df.hr_abnormal | df.spo2_abnormal | df.temp_abnormal).sum()))
    print("\nplanted events (ground truth):")
    print(ev.to_string(index=False))
    nat = df[(df.label == "NORMAL") & (df.hr_abnormal | df.spo2_abnormal | df.temp_abnormal)]
    print(f"\nnaturally occurring (noise) abnormal readings outside planted events: {len(nat)}")
    if len(nat):
        print(nat[["patient_id", "event_time", "heart_rate", "spo2", "temperature"]].to_string(index=False))
