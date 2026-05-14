"""Quick raw snippet sampler — no expensive autocorr."""
from __future__ import annotations
import json, os, statistics
from pathlib import Path

ROOT = Path("E:/MultiF/Content")
OUT = Path("C:/Users/soeri/Desktop/Restim Web Extension/data/funscript_analysis")

REQS = [
    ("Barbarella", "Electric Barbarella [1080p HD]", "alpha", 60, 75),
    ("Barbarella", "Electric Barbarella [1080p HD]", "alpha", 3000, 3015),
    ("Barbarella", "Electric Barbarella [1080p HD]", "alpha", 5800, 5815),
    ("Barbarella", "Electric Barbarella [1080p HD]", "beta", 60, 75),
    ("Barbarella", "Electric Barbarella [1080p HD]", "volume", 0, 6040),
    ("Barbarella", "Electric Barbarella [1080p HD]", "pulse_frequency", 0, 6040),
    ("Barbarella", "Electric Barbarella [1080p HD]", "pulse_width", 0, 6040),

    ("CH Crescendo", "Cock Hero Crescendo", "alpha", 60, 75),
    ("CH Crescendo", "Cock Hero Crescendo", "alpha", 1500, 1515),
    ("CH Crescendo", "Cock Hero Crescendo", "pulse_frequency", 60, 75),
    ("CH Crescendo", "Cock Hero Crescendo", "pulse_width", 1500, 1515),
    ("CH Crescendo", "Cock Hero Crescendo", "volume", 0, 3135),

    ("MCB", "MistressAndControlBox", "alpha", 30, 45),
    ("MCB", "MistressAndControlBox", "alpha", 1500, 1515),
    ("MCB", "MistressAndControlBox", "alpha", 3100, 3115),
    ("MCB", "MistressAndControlBox", "volume", 0, 3214),
    ("MCB", "MistressAndControlBox", "pulse_frequency", 0, 3214),

    ("Liya", "E-STIM with Liya Silver (Remix)", "alpha", 4000, 4015),
    ("Liya", "E-STIM with Liya Silver (Remix)", "volume", 0, 8175),

    ("Kafka Owns", "7.1 KAFKA OWNS YOUR COCK - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "alpha", 100, 115),
    ("Kafka Owns", "7.1 KAFKA OWNS YOUR COCK - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "alpha", 2400, 2415),
    ("Kafka Owns", "7.1 KAFKA OWNS YOUR COCK - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "vib", 0, 4920),

    ("Celestial", "Celestial Succubus", "alpha", 1280, 1295),
    ("Celestial", "Celestial Succubus", "beta", 1280, 1295),

    ("Duro", "Cock Hero - Duro 1", "alpha", 60, 75),
    ("Duro", "Cock Hero - Duro 1", "alpha", 1750, 1765),
    ("Duro", "Cock Hero - Duro 1", "pulse_frequency", 60, 75),

    ("Raven", "9.1 RAVEN - THE FORBIDDEN DRAINING RITUAL - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "e1", 1800, 1815),
    ("Raven", "9.1 RAVEN - THE FORBIDDEN DRAINING RITUAL - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "e2", 1800, 1815),
    ("Raven", "9.1 RAVEN - THE FORBIDDEN DRAINING RITUAL - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "e3", 1800, 1815),
    ("Raven", "9.1 RAVEN - THE FORBIDDEN DRAINING RITUAL - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "e4", 1800, 1815),
    ("Raven", "9.1 RAVEN - THE FORBIDDEN DRAINING RITUAL - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60", "alpha", 1800, 1815),

    ("Yor Forger", "2.3 YOR FORGER - WAIFU SESSIONS - EXCLUSIVE - FHD60", "alpha", 1100, 1115),

    ("Euphoria 5", "Euphoria5", "alpha", 80, 95),
    ("Euphoria 5", "Euphoria5", "alpha", 2600, 2615),

    ("Church 2", "CHURCH OF DESIRES - EPISODE 2 - STROKER FUNSCRIPT", "alpha", 2900, 2915),

    ("Nightmare 2", "Cock Hero - Lust Nightmare 2.ldn", "alpha", 100, 115),
    ("Nightmare 2", "Cock Hero - Lust Nightmare 2.ldn", "alpha", 1700, 1715),

    ("WarpZone", "Cock Hero - Warp Zone - djj", "alpha", 60, 75),
    ("WarpZone", "Cock Hero - Warp Zone - djj", "alpha", 2600, 2615),

    ("Samu", "SAMUS ACTION SYNC", "alpha", 2200, 2215),
]


def find_axis(folder: Path, base: str, axis: str):
    target = f"{base}.{axis}.funscript"
    for root, _, files in os.walk(folder):
        if target in files:
            return Path(root) / target
    return None


def load(p: Path):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return json.load(f)


# group by file to load each only once
by_file = {}
for folder, base, axis, t0, t1 in REQS:
    p = find_axis(ROOT / folder, base, axis)
    if p:
        by_file.setdefault(p, []).append((folder, base, axis, t0, t1))

out = []
for p, items in by_file.items():
    try:
        d = load(p)
    except Exception as e:
        for folder, base, axis, t0, t1 in items:
            out.append({"folder": folder, "axis": axis, "t0_s": t0, "t1_s": t1, "error": str(e)})
        continue
    actions = sorted(d.get("actions") or [], key=lambda a: a["at"])
    for folder, base, axis, t0, t1 in items:
        win = [a for a in actions if t0 * 1000 <= a["at"] <= t1 * 1000]
        rec = {"folder": folder, "axis": axis, "t0_s": t0, "t1_s": t1, "n": len(win)}
        if win:
            poses = [a["pos"] for a in win]
            rec["pos_min"] = min(poses)
            rec["pos_max"] = max(poses)
            rec["pos_mean"] = round(statistics.fmean(poses), 1)
            rec["pos_stdev"] = round(statistics.pstdev(poses), 1)
            ivl = [b["at"] - a["at"] for a, b in zip(win, win[1:]) if b["at"] > a["at"]]
            if ivl:
                rec["interval_median_ms"] = round(statistics.median(ivl), 1)
                rec["interval_min_ms"] = min(ivl)
                rec["interval_max_ms"] = max(ivl)
            rec["snippet"] = [(a["at"], a["pos"]) for a in win[:30]]
        out.append(rec)

with open(OUT / "snapshots.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
print(f"Wrote snapshots.json, {len(out)} entries")
