"""
Bulk analysis of Restim funscript files.
Outputs per-axis statistics, per-session aggregates, and segment breakdowns to CSV/JSON.
"""
from __future__ import annotations

import csv
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

# Axis taxonomy: derive from file suffix between '.' and '.funscript'
AXIS_RE = re.compile(r"\.([a-zA-Z0-9_\-]+)\.funscript$")

KNOWN_AXES = {
    "alpha", "beta",
    "alpha-2", "beta-2",
    "alpha-prostate", "beta-prostate",
    "volume", "volume-prostate", "volume-stereostim",
    "frequency",
    "pulse_frequency", "pulse_width", "pulse_rise_time",
    "vib",
    "e1", "e2", "e3", "e4",
    "e1-2", "e2-2", "e3-2", "e4-2",
}


def load_funscript(path: Path) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except Exception as e:
        print(f"WARN load fail {path}: {e}", file=sys.stderr)
        return None


def axis_of(path: Path) -> str:
    m = AXIS_RE.search(path.name)
    if m:
        return m.group(1)
    # plain ".funscript" -> position 1D
    if path.name.endswith(".funscript"):
        return "position1d"
    return "unknown"


def session_key(path: Path) -> str:
    # Use parent folder relative to ROOT as session id
    rel = path.relative_to(ROOT)
    parts = rel.parts
    # If under top-level folder only, take that; else combine
    return parts[0]


def safe_stats(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0}
    n = len(vals)
    mn = min(vals)
    mx = max(vals)
    me = statistics.fmean(vals)
    sd = statistics.pstdev(vals) if n > 1 else 0.0
    md = statistics.median(vals)
    return {"n": n, "min": mn, "max": mx, "mean": me, "stdev": sd, "median": md}


def slope_dist(actions: list[dict]) -> dict:
    if len(actions) < 2:
        return {"n": 0}
    slopes = []
    for a, b in zip(actions, actions[1:]):
        dt = b["at"] - a["at"]
        if dt <= 0:
            continue
        slopes.append(abs(b["pos"] - a["pos"]) / dt * 1000.0)  # pos-units per second
    return safe_stats(slopes)


def interval_dist(actions: list[dict]) -> dict:
    if len(actions) < 2:
        return {"n": 0}
    intervals = [b["at"] - a["at"] for a, b in zip(actions, actions[1:]) if b["at"] - a["at"] >= 0]
    return safe_stats(intervals)


def histogram(vals: list[float], bins: int = 10) -> list[int]:
    if not vals:
        return []
    mn, mx = min(vals), max(vals)
    if mx == mn:
        return [len(vals)] + [0] * (bins - 1)
    step = (mx - mn) / bins
    h = [0] * bins
    for v in vals:
        idx = min(int((v - mn) / step), bins - 1)
        h[idx] += 1
    return h


def segment_means(actions: list[dict], total_ms: float, segments: int = 10) -> list[float]:
    if not actions or total_ms <= 0:
        return []
    seg_size = total_ms / segments
    buckets = [[] for _ in range(segments)]
    for a in actions:
        idx = min(int(a["at"] / seg_size), segments - 1)
        buckets[idx].append(a["pos"])
    out = []
    for b in buckets:
        out.append(statistics.fmean(b) if b else float("nan"))
    return out


def analyze_one(path: Path) -> dict | None:
    data = load_funscript(path)
    if not data:
        return None
    actions = data.get("actions") or []
    if not actions:
        return {
            "session": session_key(path),
            "axis": axis_of(path),
            "file": str(path),
            "n_actions": 0,
        }
    actions = sorted(actions, key=lambda a: a["at"])
    positions = [float(a["pos"]) for a in actions]
    total_ms = actions[-1]["at"]
    pos_stats = safe_stats(positions)
    sl = slope_dist(actions)
    ivl = interval_dist(actions)
    hist = histogram(positions, 10)
    seg = segment_means(actions, total_ms, 10)
    # action density per minute
    density = len(actions) / (total_ms / 60_000.0) if total_ms > 0 else 0
    return {
        "session": session_key(path),
        "axis": axis_of(path),
        "file": str(path),
        "n_actions": len(actions),
        "duration_ms": total_ms,
        "duration_min": total_ms / 60_000.0,
        "density_per_min": density,
        "pos_min": pos_stats.get("min"),
        "pos_max": pos_stats.get("max"),
        "pos_mean": pos_stats.get("mean"),
        "pos_stdev": pos_stats.get("stdev"),
        "pos_median": pos_stats.get("median"),
        "interval_mean_ms": ivl.get("mean"),
        "interval_median_ms": ivl.get("median"),
        "interval_min_ms": ivl.get("min"),
        "interval_max_ms": ivl.get("max"),
        "slope_mean_pps": sl.get("mean"),
        "slope_max_pps": sl.get("max"),
        "slope_stdev_pps": sl.get("stdev"),
        "hist10": hist,
        "segment_means_10": seg,
    }


def main():
    files = sorted(p for p in ROOT.rglob("*.funscript") if p.is_file())
    print(f"Found {len(files)} funscript files", file=sys.stderr)

    rows: list[dict] = []
    by_session: dict[str, list[dict]] = defaultdict(list)
    axes_seen: Counter = Counter()

    for p in files:
        r = analyze_one(p)
        if r is None:
            continue
        rows.append(r)
        by_session[r["session"]].append(r)
        axes_seen[r["axis"]] += 1

    # Per-axis CSV
    csv_path = OUT / "per_file.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "session", "axis", "file", "n_actions", "duration_min",
            "density_per_min", "pos_min", "pos_max", "pos_mean", "pos_stdev",
            "interval_mean_ms", "interval_median_ms",
            "slope_mean_pps", "slope_max_pps", "slope_stdev_pps",
            "hist10", "segment_means_10"
        ])
        for r in rows:
            w.writerow([
                r["session"], r["axis"], r["file"], r["n_actions"],
                f"{(r.get('duration_min') or 0):.2f}",
                f"{(r.get('density_per_min') or 0):.2f}",
                r.get("pos_min"), r.get("pos_max"),
                f"{(r.get('pos_mean') or 0):.2f}", f"{(r.get('pos_stdev') or 0):.2f}",
                f"{(r.get('interval_mean_ms') or 0):.1f}", f"{(r.get('interval_median_ms') or 0):.1f}",
                f"{(r.get('slope_mean_pps') or 0):.2f}", f"{(r.get('slope_max_pps') or 0):.2f}",
                f"{(r.get('slope_stdev_pps') or 0):.2f}",
                json.dumps(r.get("hist10") or []),
                json.dumps([None if (v is None or (isinstance(v, float) and math.isnan(v))) else round(v, 2) for v in (r.get("segment_means_10") or [])]),
            ])

    # Session summary
    sess_path = OUT / "per_session.csv"
    with open(sess_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["session", "axes", "n_axes", "max_duration_min", "total_actions"])
        for s, rs in sorted(by_session.items()):
            axes = sorted({r["axis"] for r in rs})
            dur = max((r.get("duration_min") or 0) for r in rs)
            tot = sum(r["n_actions"] for r in rs)
            w.writerow([s, ";".join(axes), len(axes), f"{dur:.2f}", tot])

    # Save JSON aggregate
    with open(OUT / "all.json", "w", encoding="utf-8") as f:
        json.dump({"axes_seen": dict(axes_seen), "rows": rows}, f, indent=1)

    # Print quick console summary
    print(f"Sessions: {len(by_session)}", file=sys.stderr)
    print(f"Axes seen: {dict(axes_seen)}", file=sys.stderr)
    print(f"Wrote {csv_path}, {sess_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
