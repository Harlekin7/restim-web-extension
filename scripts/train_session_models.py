"""Train the two learned models that drive the Session Generator.

Outputs (under data/models/):
  - macro_envelope_sampler.json     — per-style mean+std intensity envelopes
  - pattern_markov.json             — style+phase conditioned Markov transitions

Modeling choices (kept intentionally small with only ~30 sessions):
  - Macro sampler  : per-style mean ± std envelope on 100 resampled points
                     (Variant A in the spec).  CPU only, numpy stdlib.
  - Markov sampler : style x phase conditioned transition table with Add-1
                     Laplace smoothing.  Falls back to a global per-(prev,phase)
                     table when a style cell has < MIN_STYLE_SAMPLES counts.

Run:
  python scripts/train_session_models.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANNOT_DIR = PROJECT_ROOT / "data" / "annotations" / "per_session"
MODELS_DIR = PROJECT_ROOT / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MULTIF_ROOT = Path("E:/MultiF/Content")
SENORGIF_ROOT = PROJECT_ROOT / "data" / "training_funscripts" / "senorgif"

# Hyper-params -------------------------------------------------------------
N_RESAMPLE_POINTS = 100      # canonical envelope resolution
CONTROL_POINTS = 7           # downsampled control points written into MasterCurve
MIN_STYLE_SAMPLES = 5        # min counts in a style/phase cell before trusting it
PHASE_BOUNDARIES = (0.20, 0.40, 0.60, 0.80)   # 5 phases of 20% each
PHASE_NAMES = ("init", "build", "plateau", "edge", "climax")
RNG_SEED_DEFAULT = 1234

# Style canonical names ---------------------------------------------------
STYLES = (
    "sanfter_aufbau",
    "crescendo",
    "beat_drop",
    "edging",
    "ruin",
    "endlos_tease",
)

# All pattern IDs (must match annotate_patterns.ALL_PATTERN_IDS).  We pull this
# at runtime from the union of patterns observed in pattern_frequency.json plus
# a static list so the markov can sample cold patterns too.
STATIC_PATTERN_IDS = [
    # Position
    "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10",
    "P11", "P12", "P13", "P14", "P15",
    # Volume
    "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11", "V12",
    # Pulse-frequency
    "PF1", "PF2", "PF3", "PF4", "PF5",
    # Pulse-width
    "PW1", "PW2", "PW3", "PW4", "PW5",
    # Pulse-rise-time
    "PR1", "PR2", "PR3", "PR4",
    # Pulse mixes
    "PMix1", "PMix2", "PMix3",
    # Carrier
    "C1", "C2", "C3", "C4", "C5",
    # Multi-axis
    "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10",
    "M11", "M12", "M13", "M14", "M15",
]

# Fallback intensity templates (mirror macro_planner.STYLE_CURVES) — used when
# a style has 0 sessions in the corpus.  Kept here to keep the trainer
# stand-alone; if these ever drift, just re-copy from macro_planner.
FALLBACK_STYLE_TEMPLATES: Dict[str, List[Tuple[float, float]]] = {
    "sanfter_aufbau": [(0.00, 0.00), (1.00, 1.00)],
    "crescendo": [(0.00, 0.00), (0.30, 0.20), (0.70, 0.55), (0.90, 0.85), (1.00, 1.00)],
    "beat_drop": [(0.00, 0.10), (0.20, 0.40), (0.40, 0.55), (0.60, 0.65), (0.85, 0.80), (1.00, 0.95)],
    "edging": [(0.00, 0.10), (0.25, 0.55), (0.45, 0.75), (0.70, 0.80), (0.95, 0.85), (1.00, 0.90)],
    "ruin": [(0.00, 0.05), (0.20, 0.30), (0.50, 0.65), (0.80, 0.95), (0.90, 1.00), (1.00, 0.30)],
    "endlos_tease": [(0.00, 0.20), (0.25, 0.45), (0.50, 0.40), (0.75, 0.50), (1.00, 0.45)],
}

DEFAULT_FALLBACK_STD = 0.06   # used when a style only has a fallback template


# ---------------------------------------------------------------------------
# Funscript loading & resampling
# ---------------------------------------------------------------------------

def _load_funscript_actions(path: Path) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"WARN load fail {path}: {exc}", file=sys.stderr)
        return None
    actions = data.get("actions") or []
    if not actions:
        return None
    times = np.fromiter((float(a.get("at", 0.0)) for a in actions), dtype=np.float64, count=len(actions))
    poses = np.fromiter((float(a.get("pos", 0.0)) for a in actions), dtype=np.float64, count=len(actions))
    order = np.argsort(times, kind="stable")
    return times[order], poses[order]


def _resample_envelope(times_ms: np.ndarray, poses: np.ndarray,
                       duration_s: float, n_points: int) -> Optional[np.ndarray]:
    if times_ms.size == 0 or duration_s <= 0:
        return None
    grid_ms = np.linspace(0.0, duration_s * 1000.0, n_points, dtype=np.float64)
    raw = np.interp(grid_ms, times_ms, poses)
    # Restim funscripts use 0..100 for volume; normalise to 0..1
    return np.clip(raw / 100.0, 0.0, 1.0).astype(np.float32)


def _find_volume_funscript(session_name: str) -> Optional[Path]:
    """Map an annotation session name -> volume.funscript path.

    Annotation session names look like:
        multif__<folder name with spaces>
        senorgif__<folder name with underscores>
    """
    if session_name.startswith("multif__"):
        folder_name = session_name[len("multif__"):]
        candidate_dir = MULTIF_ROOT / folder_name
    elif session_name.startswith("senorgif__"):
        folder_name = session_name[len("senorgif__"):]
        candidate_dir = SENORGIF_ROOT / folder_name
    else:
        return None

    if not candidate_dir.exists():
        return None

    # Walk the folder; first .volume.funscript wins (prefer top-level).
    matches: list[Path] = []
    for root, _dirs, files in os.walk(candidate_dir):
        root_p = Path(root)
        for f in files:
            if f.endswith(".volume.funscript"):
                matches.append(root_p / f)
        if matches:
            break
    if not matches:
        # Last-ditch: search recursively
        for root, _dirs, files in os.walk(candidate_dir):
            root_p = Path(root)
            for f in files:
                if f.endswith(".volume.funscript"):
                    matches.append(root_p / f)
    if not matches:
        return None

    matches.sort(key=lambda p: (len(p.parts), len(p.name)))
    return matches[0]


# ---------------------------------------------------------------------------
# Style classification heuristic
# ---------------------------------------------------------------------------

def _phase_means(env: np.ndarray) -> List[float]:
    n = env.shape[0]
    boundaries = [int(round(b * n)) for b in PHASE_BOUNDARIES] + [n]
    out = []
    prev = 0
    for b in boundaries:
        seg = env[prev:b]
        out.append(float(seg.mean()) if seg.size else float(env[-1]))
        prev = b
    return out


def _burstiness(env: np.ndarray) -> float:
    """Variance of 1s windows in the resampled (~duration_s/100s per sample)
    envelope.  Higher = more bursty."""
    if env.size < 4:
        return 0.0
    diffs = np.diff(env)
    return float(np.var(diffs))


def _drop_count(env: np.ndarray, threshold: float = 0.18) -> int:
    """Count substantial local drops > threshold (in normalised units)."""
    if env.size < 5:
        return 0
    drops = 0
    peak = env[0]
    for i in range(1, env.size):
        peak = max(peak, env[i])
        if peak - env[i] >= threshold:
            drops += 1
            peak = env[i]
    return drops


def _is_monotone_increasing(env: np.ndarray, slack: float = 0.10) -> bool:
    """Is the curve roughly monotone going upward?  Allows `slack` worth of
    backtracking compared to the running max."""
    if env.size < 3:
        return False
    running_max = env[0]
    backslip_total = 0.0
    for v in env[1:]:
        if v > running_max:
            running_max = v
        else:
            backslip_total += running_max - v
    norm = backslip_total / env.size
    return norm < slack


def classify_style(env: np.ndarray, slots_stats: Dict) -> str:
    """Heuristic mapping from a resampled volume envelope -> style name.

    Order matters: more specific classes are checked first.  Thresholds were
    tuned by inspecting the 30 annotated sessions and checking that the
    resulting per-style buckets each have at least a few members where
    plausible.
    """
    means = _phase_means(env)            # 5 entries: init, build, plateau, edge, climax
    burst = _burstiness(env)
    drops = _drop_count(env)
    range_span = float(env.max() - env.min())

    # Tail collapse?  (volume in last 5% << peak)
    last5_pct = env[int(0.95 * env.size):]
    peak_total = float(env.max())
    last5_mean = float(last5_pct.mean()) if last5_pct.size else float(env[-1])
    tail_drop = peak_total - last5_mean

    # ---------------- Ruin: very deep last-5% collapse from a real peak ------
    # Require the climax-phase mean to also be substantially lower than edge,
    # so a session that just fades by 30% over the last 30s isn't tagged ruin.
    if tail_drop > 0.40 and peak_total > 0.70 and means[4] < means[3] - 0.05:
        return "ruin"

    # ---------------- Beat-Drop: very bursty (cock-hero style) ---------------
    # Threshold raised to 0.04 — below that, content is more "smooth ramp".
    if burst > 0.04 and drops >= 5:
        return "beat_drop"

    # ---------------- Edging: held-high plateau with several drops -----------
    plateau_high = means[2] > 0.55 and means[3] > 0.55
    if plateau_high and drops >= 4 and burst < 0.05:
        return "edging"

    # ---------------- Crescendo: monotone climb with real climax peak --------
    final_peak_strong = means[4] >= max(means[1], means[2]) - 0.02
    monotone = _is_monotone_increasing(env, slack=0.12)
    big_climb = (means[4] - means[0]) > 0.25
    if monotone and final_peak_strong and big_climb:
        # If burstiness is mid (cock-hero crescendo), tag as crescendo.
        # If burstiness is very low + smooth climb -> sanfter_aufbau.
        if burst > 0.015:
            return "crescendo"
        return "sanfter_aufbau"

    # ---------------- Endlos-Tease: stays in mid range, never peaks high ----
    if range_span < 0.50 and means[4] < 0.70 and peak_total < 0.80:
        return "endlos_tease"

    # ---------------- Fallback: sanfter Aufbau --------------------------------
    return "sanfter_aufbau"


# ---------------------------------------------------------------------------
# Macro envelope training
# ---------------------------------------------------------------------------

def _control_indices(n_points: int, n_ctrl: int) -> List[int]:
    if n_ctrl >= n_points:
        return list(range(n_points))
    # Evenly spaced including 0 and n_points-1
    return [int(round(i)) for i in np.linspace(0, n_points - 1, n_ctrl)]


def _aggregate_style(
    envelopes: List[np.ndarray],
) -> Tuple[np.ndarray, np.ndarray]:
    """Returns (mean_curve_100, std_curve_100)."""
    stacked = np.vstack(envelopes)              # (S, 100)
    mean = stacked.mean(axis=0)
    if stacked.shape[0] >= 2:
        std = stacked.std(axis=0, ddof=0)
    else:
        std = np.full_like(mean, DEFAULT_FALLBACK_STD, dtype=np.float64)
    # Always ensure a tiny floor of stochasticity so two seeds give different curves.
    std = np.maximum(std, 0.01)
    return mean.astype(float), std.astype(float)


def _fallback_curve_from_template(template: List[Tuple[float, float]]) -> np.ndarray:
    grid = np.linspace(0.0, 1.0, N_RESAMPLE_POINTS)
    xs = np.array([p[0] for p in template], dtype=np.float64)
    ys = np.array([p[1] for p in template], dtype=np.float64)
    return np.interp(grid, xs, ys).astype(float)


def train_macro_sampler(
    per_session_envelopes: Dict[str, List[np.ndarray]],
    n_total_sessions: int,
) -> Dict:
    """Build the per-style mean+std envelope sampler model dict."""
    out_styles: Dict[str, Dict] = {}
    cp_idx = _control_indices(N_RESAMPLE_POINTS, CONTROL_POINTS)

    for style in STYLES:
        envs = per_session_envelopes.get(style, [])
        if envs:
            mean_curve, std_curve = _aggregate_style(envs)
            out_styles[style] = {
                "n_samples": len(envs),
                "mean_curve_100pts": [float(v) for v in mean_curve.tolist()],
                "std_curve_100pts": [float(v) for v in std_curve.tolist()],
                "control_point_indices": cp_idx,
                "is_fallback": False,
            }
        else:
            mean_curve = _fallback_curve_from_template(FALLBACK_STYLE_TEMPLATES[style])
            std_curve = np.full_like(mean_curve, DEFAULT_FALLBACK_STD, dtype=np.float64)
            out_styles[style] = {
                "n_samples": 0,
                "mean_curve_100pts": [float(v) for v in mean_curve.tolist()],
                "std_curve_100pts": [float(v) for v in std_curve.tolist()],
                "control_point_indices": cp_idx,
                "is_fallback": True,
            }

    return {
        "model_type": "per_style_meanstd_v1",
        "trained_on_sessions": int(n_total_sessions),
        "n_resample_points": N_RESAMPLE_POINTS,
        "control_points": CONTROL_POINTS,
        "styles": out_styles,
    }


# ---------------------------------------------------------------------------
# Markov training
# ---------------------------------------------------------------------------

def _phase_of(t_start_s: float, duration_s: float) -> str:
    if duration_s <= 0:
        return PHASE_NAMES[0]
    frac = max(0.0, min(0.999999, t_start_s / duration_s))
    for i, b in enumerate(PHASE_BOUNDARIES):
        if frac < b:
            return PHASE_NAMES[i]
    return PHASE_NAMES[-1]


def _normalise_counts(counts: Dict[str, float], pattern_ids: List[str]) -> Dict[str, float]:
    total = sum(counts.values())
    if total <= 0:
        # Uniform
        u = 1.0 / len(pattern_ids)
        return {p: u for p in pattern_ids}
    return {p: counts.get(p, 0.0) / total for p in pattern_ids}


def train_markov(
    sessions: List[Dict],
    style_by_session: Dict[str, str],
    pattern_ids: List[str],
) -> Dict:
    """Build a style/phase conditioned Markov over patterns with Add-1 smoothing."""
    n_pat = len(pattern_ids)

    # global_transitions[prev][next] = count
    global_counts: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    # style_phase_counts[style][(prev, phase)][next] = count
    style_counts: Dict[str, Dict[Tuple[str, str], Dict[str, float]]] = {
        s: defaultdict(lambda: defaultdict(float)) for s in STYLES
    }

    for sess in sessions:
        slots = sess.get("slots", [])
        if len(slots) < 2:
            continue
        sess_name = sess.get("session", "")
        style = style_by_session.get(sess_name, "sanfter_aufbau")
        duration_s = float(slots[-1].get("t_end_s", 0.0))
        if duration_s <= 0:
            continue
        for i in range(len(slots) - 1):
            prev = slots[i].get("pattern_id")
            nxt = slots[i + 1].get("pattern_id")
            if not prev or not nxt:
                continue
            if prev not in pattern_ids or nxt not in pattern_ids:
                continue
            phase = _phase_of(float(slots[i].get("t_start_s", 0.0)), duration_s)
            global_counts[prev][nxt] += 1.0
            style_counts[style][(prev, phase)][nxt] += 1.0

    # Apply Add-1 Laplace smoothing, then normalise.
    global_transitions: Dict[str, Dict[str, float]] = {}
    for prev in pattern_ids:
        smoothed = {p: global_counts[prev].get(p, 0.0) + 1.0 for p in pattern_ids}
        global_transitions[prev] = _normalise_counts(smoothed, pattern_ids)

    # by_style_phase[style][phase][prev] = {next: prob}.  We only emit cells
    # with raw count >= MIN_STYLE_SAMPLES; the runtime falls back to global.
    by_style_phase: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
    cell_stats: Dict[str, Dict[str, int]] = {}     # for the report

    for style in STYLES:
        by_style_phase[style] = {p: {} for p in PHASE_NAMES}
        cell_stats[style] = {"data": 0, "fallback": 0}
        for (prev, phase), counts in style_counts[style].items():
            raw_total = sum(counts.values())
            if raw_total < MIN_STYLE_SAMPLES:
                continue
            smoothed = {p: counts.get(p, 0.0) + 1.0 for p in pattern_ids}
            by_style_phase[style][phase][prev] = _normalise_counts(smoothed, pattern_ids)
            cell_stats[style]["data"] += 1

        # All other (prev, phase) combos for this style are fallbacks at runtime.
        total_cells = len(pattern_ids) * len(PHASE_NAMES)
        cell_stats[style]["fallback"] = total_cells - cell_stats[style]["data"]
        cell_stats[style]["total_cells"] = total_cells

    return {
        "model_type": "stil_phase_markov_v1",
        "n_patterns": n_pat,
        "pattern_ids": list(pattern_ids),
        "phases": list(PHASE_NAMES),
        "min_style_samples": MIN_STYLE_SAMPLES,
        "global_transitions": global_transitions,
        "by_style_phase": by_style_phase,
        "_cell_stats": cell_stats,    # for the report; runtime ignores leading underscore
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def gather_sessions() -> Tuple[List[Dict], Dict[str, np.ndarray], List[str]]:
    """Load all annotation JSONs.  Return (raw_sessions, env_by_name, skipped)."""
    raw_sessions: List[Dict] = []
    env_by_name: Dict[str, np.ndarray] = {}
    skipped: List[str] = []

    for jpath in sorted(ANNOT_DIR.glob("*.json")):
        try:
            with open(jpath, "r", encoding="utf-8") as f:
                sess = json.load(f)
        except Exception as exc:
            print(f"WARN parse fail {jpath}: {exc}", file=sys.stderr)
            skipped.append(jpath.name)
            continue

        sess_name = sess.get("session") or jpath.stem
        sess["session"] = sess_name
        raw_sessions.append(sess)

        # Find volume.funscript
        vol_path = _find_volume_funscript(sess_name)
        if vol_path is None:
            print(f"WARN no volume.funscript for session '{sess_name}'", file=sys.stderr)
            skipped.append(sess_name)
            continue

        parsed = _load_funscript_actions(vol_path)
        if parsed is None:
            print(f"WARN empty volume funscript for '{sess_name}': {vol_path}", file=sys.stderr)
            skipped.append(sess_name)
            continue

        times_ms, poses = parsed
        # Prefer annotation-derived duration, fallback to funscript end-time
        duration_s = float(sess.get("stats", {}).get("duration_s") or 0.0)
        if duration_s <= 0:
            duration_s = float(times_ms.max() / 1000.0) if times_ms.size else 0.0
        env = _resample_envelope(times_ms, poses, duration_s, N_RESAMPLE_POINTS)
        if env is None:
            skipped.append(sess_name)
            continue
        env_by_name[sess_name] = env

    return raw_sessions, env_by_name, skipped


def _build_pattern_id_universe(raw_sessions: List[Dict]) -> List[str]:
    """Use observed patterns + the static catalog so the markov works for cold IDs too."""
    seen: set[str] = set()
    for sess in raw_sessions:
        for slot in sess.get("slots", []):
            pid = slot.get("pattern_id")
            if pid:
                seen.add(pid)
    seen.update(STATIC_PATTERN_IDS)
    # Stable order: static order first, then any newcomers
    extras = sorted(p for p in seen if p not in STATIC_PATTERN_IDS)
    return [p for p in STATIC_PATTERN_IDS if p in seen or True] + extras


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def _curve_range(values: List[float]) -> Tuple[float, float]:
    arr = np.asarray(values, dtype=np.float64)
    return float(arr.min()), float(arr.max())


def _sample_macro(model: Dict, style: str, duration_s: float,
                  vol_floor: float, vol_ceiling: float,
                  rng: np.random.Generator) -> List[Tuple[float, float]]:
    cfg = model["styles"][style]
    mean = np.asarray(cfg["mean_curve_100pts"], dtype=np.float64)
    std = np.asarray(cfg["std_curve_100pts"], dtype=np.float64)
    cp = cfg["control_point_indices"]
    sampled = mean + rng.normal(0.0, 1.0, size=mean.shape) * std
    sampled = np.clip(sampled, 0.0, 1.0)
    # Scale to user caps (treat 0..1 as 0..ceil-floor offset above floor).
    scaled = vol_floor + sampled * (vol_ceiling - vol_floor)
    n = mean.shape[0]
    out = []
    for idx in cp:
        t = (idx / max(n - 1, 1)) * duration_s
        out.append((float(t), float(scaled[idx])))
    return out


def _report(report_path: Path,
            macro_model: Dict,
            markov_model: Dict,
            style_session_counts: Dict[str, int],
            skipped: List[str],
            sample_outputs: Dict[str, List[List[Tuple[float, float]]]],
            markov_demo: Dict[str, float]) -> None:
    lines: list[str] = []
    lines.append("# Session-Generator Model Training Report")
    lines.append("")
    lines.append(f"- Trained on: {macro_model['trained_on_sessions']} sessions")
    if skipped:
        lines.append(f"- Skipped: {len(skipped)} ({', '.join(skipped)})")
    else:
        lines.append("- Skipped: 0")
    lines.append("")

    lines.append("## Style classification (heuristic mapping)")
    for style in STYLES:
        lines.append(f"- `{style}`: {style_session_counts.get(style, 0)} sessions")
    lines.append("")

    lines.append("## Macro envelope sampler")
    for style in STYLES:
        cfg = macro_model["styles"][style]
        mn_lo, mn_hi = _curve_range(cfg["mean_curve_100pts"])
        sd_lo, sd_hi = _curve_range(cfg["std_curve_100pts"])
        flag = " (fallback)" if cfg["is_fallback"] else ""
        lines.append(
            f"- `{style}` n={cfg['n_samples']}{flag} — mean range "
            f"[{mn_lo:.3f}..{mn_hi:.3f}], std range [{sd_lo:.3f}..{sd_hi:.3f}]"
        )
    lines.append("")

    lines.append("## Markov model — cells with data vs fallback")
    cell_stats = markov_model.get("_cell_stats", {})
    for style in STYLES:
        s = cell_stats.get(style, {"data": 0, "fallback": 0, "total_cells": 0})
        lines.append(
            f"- `{style}`: {s['data']} cells with data / {s['fallback']} fallback "
            f"(out of {s['total_cells']} total prev-x-phase cells)"
        )
    lines.append("")

    lines.append("## 3 sample envelope realisations per style")
    for style in STYLES:
        lines.append(f"### {style}")
        for i, samp in enumerate(sample_outputs.get(style, [])):
            short = ", ".join(f"({t:.0f}s, {v:.2f})" for t, v in samp)
            lines.append(f"- Sample {i + 1}: {short}")
        lines.append("")

    lines.append("## Markov demo: sanfter_aufbau / phase=plateau / prev=V1 — top-5")
    for pat, prob in sorted(markov_demo.items(), key=lambda kv: -kv[1])[:5]:
        lines.append(f"- {pat}: {prob:.4f}")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"Loading annotation files from {ANNOT_DIR}")
    raw_sessions, env_by_name, skipped = gather_sessions()
    print(f"  Loaded {len(raw_sessions)} session annotations")
    print(f"  Loaded {len(env_by_name)} envelopes")
    if skipped:
        print(f"  Skipped: {skipped}")

    # ---------------- Style classification ---------------------------------
    style_by_session: Dict[str, str] = {}
    style_envelopes: Dict[str, List[np.ndarray]] = defaultdict(list)
    for sess in raw_sessions:
        sess_name = sess["session"]
        env = env_by_name.get(sess_name)
        if env is None:
            # Sessions without an envelope still need a style for the markov.
            style_by_session[sess_name] = "sanfter_aufbau"
            continue
        style = classify_style(env, sess.get("stats", {}))
        style_by_session[sess_name] = style
        style_envelopes[style].append(env)

    style_session_counts = {s: len(style_envelopes.get(s, [])) for s in STYLES}
    print("Style mapping:")
    for s in STYLES:
        print(f"  {s}: {style_session_counts[s]}")

    # ---------------- Macro sampler ---------------------------------------
    macro_model = train_macro_sampler(style_envelopes, len(env_by_name))
    macro_path = MODELS_DIR / "macro_envelope_sampler.json"
    macro_path.write_text(json.dumps(macro_model, indent=1), encoding="utf-8")
    print(f"Wrote {macro_path}  ({macro_path.stat().st_size / 1024:.1f} KB)")

    # ---------------- Markov ---------------------------------------------
    pattern_ids = _build_pattern_id_universe(raw_sessions)
    markov_model = train_markov(raw_sessions, style_by_session, pattern_ids)
    markov_path = MODELS_DIR / "pattern_markov.json"
    markov_path.write_text(json.dumps(markov_model, indent=1), encoding="utf-8")
    print(f"Wrote {markov_path}  ({markov_path.stat().st_size / 1024:.1f} KB)")

    # ---------------- Sanity samples / demos -----------------------------
    rng = np.random.default_rng(RNG_SEED_DEFAULT)
    sample_outputs: Dict[str, List[List[Tuple[float, float]]]] = {}
    for style in STYLES:
        sample_outputs[style] = []
        for k in range(3):
            sub_rng = np.random.default_rng(RNG_SEED_DEFAULT + k * 17 + hash(style) % 9000)
            sample_outputs[style].append(
                _sample_macro(macro_model, style, duration_s=2700.0,
                              vol_floor=0.25, vol_ceiling=0.80, rng=sub_rng)
            )

    # Markov demo: sanfter_aufbau / plateau / prev=V1 — pull from saved model
    demo_style = "sanfter_aufbau"
    demo_phase = "plateau"
    demo_prev = "V1"
    cells = markov_model["by_style_phase"].get(demo_style, {}).get(demo_phase, {})
    if demo_prev in cells:
        markov_demo = cells[demo_prev]
    else:
        markov_demo = markov_model["global_transitions"].get(demo_prev, {})

    # ---------------- Report --------------------------------------------
    report_path = MODELS_DIR / "training_report.md"
    _report(report_path, macro_model, markov_model,
            style_session_counts, skipped, sample_outputs, markov_demo)
    print(f"Wrote {report_path}")

    # Echo the report to stdout so the orchestrator captures it
    print()
    print(report_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
