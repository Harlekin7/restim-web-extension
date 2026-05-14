"""
Deep inspection of selected sessions:
- Sample first/middle/last 50 actions per axis
- Cross-axis correlation (resampled to common timeline)
- Detect alpha-rotation (alpha/beta phase circle)
- Detect repeating patterns (saw, sine, plateau, burst)
- Per-segment intensity markers (volume + pulse_freq + pulse_width product)
"""
from __future__ import annotations

import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from glob import glob
from pathlib import Path

ROOT = Path("E:/MultiF/Content")
OUT = Path("C:/Users/soeri/Desktop/Restim Web Extension/data/funscript_analysis")
OUT.mkdir(parents=True, exist_ok=True)

# Sessions to deep-dive
DEEP = [
    ("Barbarella", "Electric Barbarella [1080p HD]"),
    ("CH Crescendo", "Cock Hero Crescendo"),
    ("MCB", "MistressAndControlBox"),
    ("Liya", "E-STIM with Liya Silver (Remix)"),
    ("Kafka Owns", "7.1 KAFKA OWNS YOUR COCK - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60"),
    ("Celestial", "Celestial Succubus"),
    ("Duro", "Cock Hero - Duro 1"),
    ("Raven", "9.1 RAVEN - THE FORBIDDEN DRAINING RITUAL - EXCLUSIVE VERSION - NO BEAT - NO AROMA - FHD60"),
    ("Yor Forger", "2.3 YOR FORGER - WAIFU SESSIONS - EXCLUSIVE - FHD60"),
    ("Euphoria 5", "Euphoria5"),
    ("RL GL DeSade", "RLGL CH Salon DeSade's Digitalis"),
    ("Church 2", "CHURCH OF DESIRES - EPISODE 2 - STROKER FUNSCRIPT"),
    ("Nightmare 2", "Cock Hero - Lust Nightmare 2.ldn"),
    ("WarpZone", "Cock Hero - Warp Zone - djj"),
    ("Samu", "SAMUS ACTION SYNC"),
]

AXES = ["alpha", "beta", "volume", "pulse_frequency", "pulse_width", "pulse_rise_time", "frequency",
        "alpha-prostate", "beta-prostate", "volume-prostate", "volume-stereostim",
        "e1", "e2", "e3", "e4"]


def load(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return json.load(f)


def find_axis(folder: Path, base: str, axis: str) -> Path | None:
    # Search in folder and subfolders for `<base>.<axis>.funscript`
    target = f"{base}.{axis}.funscript"
    for root, _, files in os.walk(folder):
        if target in files:
            return Path(root) / target
    return None


def resample(actions, t0, t1, n):
    # linear interpolation across actions list -> n samples between t0..t1
    if not actions:
        return [None] * n
    actions = sorted(actions, key=lambda a: a["at"])
    times = [a["at"] for a in actions]
    poses = [float(a["pos"]) for a in actions]
    out = []
    j = 0
    for i in range(n):
        t = t0 + (t1 - t0) * i / (n - 1) if n > 1 else t0
        while j + 1 < len(times) and times[j + 1] < t:
            j += 1
        if t <= times[0]:
            out.append(poses[0])
        elif t >= times[-1]:
            out.append(poses[-1])
        else:
            t1_, t2_ = times[j], times[j + 1]
            p1, p2 = poses[j], poses[j + 1]
            if t2_ == t1_:
                out.append(p1)
            else:
                f = (t - t1_) / (t2_ - t1_)
                out.append(p1 + f * (p2 - p1))
    return out


def pearson(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    mx = statistics.fmean(xs); my = statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in pairs)
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def detect_alpha_rotation(alpha_samples, beta_samples):
    # if (alpha-50, beta-50) trace approximately a circle in segments => rotation
    if not alpha_samples or not beta_samples:
        return None
    total = 0
    rot_segs = 0
    win = 50  # ~50 samples window
    for s in range(0, len(alpha_samples) - win, win):
        a = alpha_samples[s:s+win]
        b = beta_samples[s:s+win]
        if any(x is None for x in a + b):
            continue
        # center
        a = [x - 50 for x in a]
        b = [x - 50 for x in b]
        radii = [math.hypot(x, y) for x, y in zip(a, b)]
        rmean = statistics.fmean(radii)
        rstd = statistics.pstdev(radii)
        # phase angle progression
        angles = [math.atan2(y, x) for x, y in zip(a, b)]
        # unwrap
        unw = [angles[0]]
        for x in angles[1:]:
            d = x - unw[-1]
            while d > math.pi: d -= 2 * math.pi
            while d < -math.pi: d += 2 * math.pi
            unw.append(unw[-1] + d)
        sweep = abs(unw[-1] - unw[0])
        total += 1
        # rotation if radius stable AND sweep > pi (>180°)
        if rmean > 10 and (rstd / max(rmean, 1)) < 0.5 and sweep > math.pi:
            rot_segs += 1
    return {"segments": total, "rotational": rot_segs, "ratio": rot_segs / total if total else None}


def burstiness(actions, total_ms):
    # ratio of high-density zones (>2x mean rate) to total
    if not actions or total_ms <= 0:
        return None
    bin_ms = 1000
    n_bins = max(1, int(total_ms // bin_ms))
    rates = [0] * n_bins
    for a in actions:
        idx = min(int(a["at"] // bin_ms), n_bins - 1)
        rates[idx] += 1
    if not rates:
        return None
    mean = statistics.fmean(rates)
    if mean == 0:
        return 0
    high = sum(1 for r in rates if r > 2 * mean)
    return high / n_bins


def main():
    summary = {}
    for folder, base in DEEP:
        f = ROOT / folder
        if not f.exists():
            continue
        rec = {"folder": folder, "base": base, "axes": {}}
        loaded = {}
        for ax in AXES:
            p = find_axis(f, base, ax)
            if p:
                d = load(p)
                if d and d.get("actions"):
                    loaded[ax] = d["actions"]
                    rec["axes"][ax] = {
                        "n": len(d["actions"]),
                        "duration_ms": d["actions"][-1]["at"],
                        "first50": [(a["at"], a["pos"]) for a in d["actions"][:50]],
                        "last50": [(a["at"], a["pos"]) for a in d["actions"][-50:]],
                    }
        # cross-axis correlation on a common 1000-sample timeline
        max_ms = max((acts[-1]["at"] for acts in loaded.values()), default=0)
        if max_ms > 0 and len(loaded) >= 2:
            samples = {ax: resample(acts, 0, max_ms, 1000) for ax, acts in loaded.items()}
            corrs = {}
            keys = list(samples.keys())
            for i in range(len(keys)):
                for j in range(i + 1, len(keys)):
                    c = pearson(samples[keys[i]], samples[keys[j]])
                    if c is not None and abs(c) > 0.2:
                        corrs[f"{keys[i]} ~ {keys[j]}"] = round(c, 3)
            rec["correlations"] = dict(sorted(corrs.items(), key=lambda kv: -abs(kv[1])))
            # alpha rotation
            if "alpha" in samples and "beta" in samples:
                rec["alpha_rotation"] = detect_alpha_rotation(samples["alpha"], samples["beta"])
            # phase env progression: split into 5 windows -> volume mean
            if "volume" in samples:
                vol = samples["volume"]
                w = len(vol) // 5
                rec["volume_phases"] = [round(statistics.fmean(vol[i*w:(i+1)*w]), 1) for i in range(5)]
            if "pulse_frequency" in samples:
                pf = samples["pulse_frequency"]
                w = len(pf) // 5
                rec["pulse_frequency_phases"] = [round(statistics.fmean(pf[i*w:(i+1)*w]), 1) for i in range(5)]
            if "pulse_width" in samples:
                pw = samples["pulse_width"]
                w = len(pw) // 5
                rec["pulse_width_phases"] = [round(statistics.fmean(pw[i*w:(i+1)*w]), 1) for i in range(5)]
            if "frequency" in samples:
                fr = samples["frequency"]
                w = len(fr) // 5
                rec["carrier_phases"] = [round(statistics.fmean(fr[i*w:(i+1)*w]), 1) for i in range(5)]
        # burstiness for volume
        if "volume" in loaded:
            rec["volume_burstiness"] = round(burstiness(loaded["volume"], loaded["volume"][-1]["at"]) or 0, 3)
        if "alpha" in loaded:
            rec["alpha_burstiness"] = round(burstiness(loaded["alpha"], loaded["alpha"][-1]["at"]) or 0, 3)
        # trim heavy fields before saving
        for ax in rec["axes"]:
            rec["axes"][ax].pop("first50", None)
            rec["axes"][ax].pop("last50", None)
        summary[folder] = rec
    out = OUT / "deep_inspect.json"
    with open(out, "w", encoding="utf-8") as fout:
        json.dump(summary, fout, indent=1, default=str)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
