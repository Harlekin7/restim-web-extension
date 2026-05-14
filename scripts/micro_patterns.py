"""
Micro-pattern probes:
- Sample raw action sequences from specific time windows in selected sessions
- Detect FFT-style periodicity (autocorrelation) for short windows
- Snapshot first / mid / last 30s of select axes for visual pattern read
"""
from __future__ import annotations
import json, math, statistics, os, sys
from pathlib import Path

ROOT = Path("E:/MultiF/Content")
OUT = Path("C:/Users/soeri/Desktop/Restim Web Extension/data/funscript_analysis")

# (session_folder, base, axis, window_label, t0_sec, t1_sec)
WINDOWS = [
    ("Barbarella", "Electric Barbarella [1080p HD]", "alpha", "early30s", 60, 90),
    ("Barbarella", "Electric Barbarella [1080p HD]", "alpha", "mid30s", 3000, 3030),
    ("Barbarella", "Electric Barbarella [1080p HD]", "alpha", "late30s", 5800, 5830),
    ("Barbarella", "Electric Barbarella [1080p HD]", "beta", "early30s", 60, 90),
    ("Barbarella", "Electric Barbarella [1080p HD]", "beta", "late30s", 5800, 5830),
    ("Barbarella", "Electric Barbarella [1080p HD]", "volume", "full", 0, 6040),
    ("Barbarella", "Electric Barbarella [1080p HD]", "pulse_frequency", "full", 0, 6040),
    ("Barbarella", "Electric Barbarella [1080p HD]", "pulse_width", "full", 0, 6040),

    ("CH Crescendo", "Cock Hero Crescendo", "alpha", "early30s", 60, 90),
    ("CH Crescendo", "Cock Hero Crescendo", "alpha", "mid30s", 1500, 1530),
    ("CH Crescendo", "Cock Hero Crescendo", "pulse_frequency", "early30s", 60, 90),
    ("CH Crescendo", "Cock Hero Crescendo", "pulse_width", "mid30s", 1500, 1530),
    ("CH Crescendo", "Cock Hero Crescendo", "volume", "full", 0, 3135),
    ("CH Crescendo", "Cock Hero Crescendo", "frequency", "full", 0, 3135),

    ("MCB", "MistressAndControlBox", "alpha", "early30s", 30, 60),
    ("MCB", "MistressAndControlBox", "alpha", "mid30s", 1500, 1530),
    ("MCB", "MistressAndControlBox", "alpha", "late30s", 3100, 3130),
    ("MCB", "MistressAndControlBox", "volume", "full", 0, 3214),
    ("MCB", "MistressAndControlBox", "pulse_frequency", "full", 0, 3214),
    ("MCB", "MistressAndControlBox", "pulse_width", "full", 0, 3214),

    ("Liya", "E-STIM with Liya Silver (Remix)", "alpha", "mid30s", 4000, 4030),
    ("Liya", "E-STIM with Liya Silver (Remix)", "volume", "full", 0, 8175),
    ("Liya", "E-STIM with Liya Silver (Remix)", "pulse_frequency", "full", 0, 8175),

    ("Kafka Owns", "7.1 KAFKA OWNS YOUR COCK - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "alpha", "early30s", 100, 130),
    ("Kafka Owns", "7.1 KAFKA OWNS YOUR COCK - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "alpha", "mid30s", 2400, 2430),
    ("Kafka Owns", "7.1 KAFKA OWNS YOUR COCK - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "volume", "early120s", 0, 120),
    ("Kafka Owns", "7.1 KAFKA OWNS YOUR COCK - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "volume", "late120s", 4800, 4920),
    ("Kafka Owns", "7.1 KAFKA OWNS YOUR COCK - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "pulse_width", "mid30s", 2400, 2430),
    ("Kafka Owns", "7.1 KAFKA OWNS YOUR COCK - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "vib", "full", 0, 4920),

    ("Celestial", "Celestial Succubus", "alpha", "mid30s", 1280, 1310),
    ("Celestial", "Celestial Succubus", "beta", "mid30s", 1280, 1310),
    ("Celestial", "Celestial Succubus", "volume", "full", 0, 2580),
    ("Celestial", "Celestial Succubus", "pulse_rise_time", "mid30s", 1280, 1310),

    ("Duro", "Cock Hero - Duro 1", "alpha", "early30s", 60, 90),
    ("Duro", "Cock Hero - Duro 1", "alpha", "mid30s", 900, 930),
    ("Duro", "Cock Hero - Duro 1", "alpha", "late30s", 1750, 1780),
    ("Duro", "Cock Hero - Duro 1", "volume", "full", 0, 1851),
    ("Duro", "Cock Hero - Duro 1", "pulse_frequency", "early30s", 60, 90),
    ("Duro", "Cock Hero - Duro 1", "pulse_width", "early30s", 60, 90),

    ("Raven", "9.1 RAVEN - THE FORBIDDEN DRAINING RITUAL - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "e1", "mid30s", 1800, 1830),
    ("Raven", "9.1 RAVEN - THE FORBIDDEN DRAINING RITUAL - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "e2", "mid30s", 1800, 1830),
    ("Raven", "9.1 RAVEN - THE FORBIDDEN DRAINING RITUAL - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "e3", "mid30s", 1800, 1830),
    ("Raven", "9.1 RAVEN - THE FORBIDDEN DRAINING RITUAL - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "e4", "mid30s", 1800, 1830),
    ("Raven", "9.1 RAVEN - THE FORBIDDEN DRAINING RITUAL - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "alpha", "mid30s", 1800, 1830),

    ("Yor Forger", "2.3 YOR FORGER - WAIFU SESSIONS - EXCLUSIVE - FHD60", "alpha", "mid30s", 1100, 1130),
    ("Yor Forger", "2.3 YOR FORGER - WAIFU SESSIONS - EXCLUSIVE - FHD60", "volume", "early120s", 0, 120),

    ("Euphoria 5", "Euphoria5", "alpha", "early30s", 80, 110),
    ("Euphoria 5", "Euphoria5", "alpha", "mid30s", 2600, 2630),
    ("Euphoria 5", "Euphoria5", "volume", "full", 0, 5220),
    ("Euphoria 5", "Euphoria5", "e1", "mid30s", 2600, 2630),

    ("RL GL DeSade", "RLGL CH Salon DeSade's Digitalis", "alpha", "mid30s", 1900, 1930),
    ("RL GL DeSade", "RLGL CH Salon DeSade's Digitalis", "volume", "early120s", 0, 120),

    ("Church 2", "CHURCH OF DESIRES - EPISODE 2 - STROKER FUNSCRIPT", "alpha", "mid30s", 2900, 2930),
    ("Church 2", "CHURCH OF DESIRES - EPISODE 2 - STROKER FUNSCRIPT", "volume", "full", 0, 5850),

    ("Nightmare 2", "Cock Hero - Lust Nightmare 2.ldn", "alpha", "early30s", 100, 130),
    ("Nightmare 2", "Cock Hero - Lust Nightmare 2.ldn", "alpha", "mid30s", 1700, 1730),
    ("Nightmare 2", "Cock Hero - Lust Nightmare 2.ldn", "volume", "full", 0, 3556),

    ("WarpZone", "Cock Hero - Warp Zone - djj", "alpha", "early30s", 60, 90),
    ("WarpZone", "Cock Hero - Warp Zone - djj", "alpha", "mid30s", 2600, 2630),

    ("Samu", "SAMUS ACTION SYNC", "alpha", "mid30s", 2200, 2230),
    ("Samu", "SAMUS ACTION SYNC", "volume", "full", 0, 4477),
]


def find_axis(folder: Path, base: str, axis: str) -> Path | None:
    target = f"{base}.{axis}.funscript"
    for root, _, files in os.walk(folder):
        if target in files:
            return Path(root) / target
    return None


def load(p: Path):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return json.load(f)


def autocorr_period(samples_pos: list[float]) -> int | None:
    # naive: find lag with strongest correlation in 2..len/2
    n = len(samples_pos)
    if n < 20:
        return None
    mean = statistics.fmean(samples_pos)
    centered = [x - mean for x in samples_pos]
    denom = sum(x * x for x in centered)
    if denom == 0:
        return None
    best_lag = None
    best_v = 0
    for lag in range(2, n // 2):
        v = sum(centered[i] * centered[i + lag] for i in range(n - lag)) / denom
        if v > best_v:
            best_v = v
            best_lag = lag
    if best_v > 0.4:
        return best_lag
    return None


def main():
    out = []
    for folder, base, axis, label, t0, t1 in WINDOWS:
        f = ROOT / folder
        p = find_axis(f, base, axis)
        if not p:
            out.append({"folder": folder, "axis": axis, "label": label, "error": "missing"})
            continue
        d = load(p)
        actions = sorted(d.get("actions") or [], key=lambda a: a["at"])
        win = [a for a in actions if t0 * 1000 <= a["at"] <= t1 * 1000]
        rec = {
            "folder": folder, "axis": axis, "label": label,
            "t0_s": t0, "t1_s": t1, "n": len(win),
        }
        if win:
            poses = [a["pos"] for a in win]
            rec["pos_min"] = min(poses)
            rec["pos_max"] = max(poses)
            rec["pos_mean"] = round(statistics.fmean(poses), 1)
            rec["pos_stdev"] = round(statistics.pstdev(poses), 1)
            # interval median
            ivl = [b["at"] - a["at"] for a, b in zip(win, win[1:]) if b["at"] > a["at"]]
            if ivl:
                rec["interval_median_ms"] = round(statistics.median(ivl), 1)
                rec["interval_min_ms"] = min(ivl)
                rec["interval_max_ms"] = max(ivl)
            # autocorrelation period (in samples) using positions only
            rec["autocorr_lag_samples"] = autocorr_period(poses)
            # raw snippet first 24 actions
            rec["snippet_at_pos"] = [(a["at"], a["pos"]) for a in win[:24]]
        out.append(rec)
    p = OUT / "micro_windows.json"
    with open(p, "w", encoding="utf-8") as fout:
        json.dump(out, fout, indent=1, default=str)
    print(f"Wrote {p}, {len(out)} windows")


if __name__ == "__main__":
    main()
