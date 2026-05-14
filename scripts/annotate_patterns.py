"""
Pattern Annotator for Restim Multi-Axis Funscripts.

Hybrid pipeline:

  Phase 1  Heuristic template-matching for ~20 well-defined patterns
           (Static-Floor, Spike-Drop, Sägezahn, Linear-Build, Rotation,
           Step-Climb, Beat-Lock, Pulse-Mix configurations, etc.)
  Phase 2  Cluster-based mapping (KMeans, scikit-learn, seed=42) for the
           remaining slots. Each cluster centroid is mapped to a fallback
           pattern id by examining its mean feature signature.
  Phase 3  Pattern-transition matrix (Add-1 Laplace smoothing) computed
           across all sessions.

Window strategy
---------------
* Window size: 5 s (good compromise: long enough to capture 1.4 Hz beat
  patterns or a single ringdown, short enough to keep sub-minute resolution
  for V-spikes and PF-spike-drops).
* Hop:        2.5 s (50 % overlap so transitions land cleanly on slot
  boundaries without inflating slot count).
* Adjacent slots with the same pattern id are merged afterwards.

Inputs
------
* E:/MultiF/Content/             — 26 sessions (one folder per session)
* data/training_funscripts/senorgif/ — 9 sessions (one folder per session)

Outputs (data/annotations/)
---------------------------
  per_session/<session_name>.json     — list of {t_start_s, t_end_s, pattern_id, confidence}
  compatibility_matrix.json           — {from_id: {to_id: smoothed_prob}}
  pattern_frequency.json              — {pattern_id: total_slot_count}
  annotation_report.md                — human-readable summary

Run
---
  python scripts/annotate_patterns.py
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

try:
    from sklearn.cluster import KMeans
    HAVE_SKLEARN = True
except Exception:  # pragma: no cover - documented fallback
    HAVE_SKLEARN = False

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = [
    Path("E:/MultiF/Content"),
    PROJECT_ROOT / "data" / "training_funscripts" / "senorgif",
]
OUT_DIR = PROJECT_ROOT / "data" / "annotations"
PER_SESSION_DIR = OUT_DIR / "per_session"
PER_SESSION_DIR.mkdir(parents=True, exist_ok=True)

WIN_S = 5.0
HOP_S = 2.5
RNG_SEED = 42
np.random.seed(RNG_SEED)

# Canonical pattern-id list (60 patterns from FUNSCRIPT_PATTERNS.md, plus the
# S-series isn't part of the per-slot annotator — those are session macros).
ALL_PATTERN_IDS = [
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

PRIMARY_AXES = [
    "alpha", "beta", "volume", "pulse_frequency", "pulse_width",
    "pulse_rise_time", "frequency",
]
EXTRA_AXES = [
    "alpha-prostate", "beta-prostate", "volume-prostate", "volume-stereostim",
    "alpha-2", "beta-2",
    "e1", "e2", "e3", "e4", "vib",
]
ALL_AXES = PRIMARY_AXES + EXTRA_AXES

AXIS_RE = re.compile(r"\.([a-zA-Z0-9_\-]+)\.funscript$")


# ---------------------------------------------------------------------------
# Loading / resampling
# ---------------------------------------------------------------------------

def load_funscript(path: Path) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (times_ms_float64, pos_float64) numpy arrays, sorted by time."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except Exception as e:
        print(f"WARN load fail {path}: {e}", file=sys.stderr)
        return None
    actions = data.get("actions") or []
    if not actions:
        return None
    times = np.fromiter((a["at"] for a in actions), dtype=np.float64, count=len(actions))
    poses = np.fromiter((a["pos"] for a in actions), dtype=np.float64, count=len(actions))
    order = np.argsort(times, kind="stable")
    return times[order], poses[order]


def discover_sessions() -> list[tuple[str, Path, str]]:
    """Return list of (session_name, folder_path, base_filename).

    Recurse into subfolders to support layouts like
    `Euphoria 5/Euphoria 5 funscripts/<base>.<axis>.funscript`. The session
    name is prefixed with its source-root tag (multif / senorgif) so cross-
    source name collisions ("CH Crescendo" vs "CH_Crescendo") cannot
    overwrite each other on disk.
    """
    sessions: list[tuple[str, Path, str]] = []
    for src in SOURCE_DIRS:
        if not src.exists():
            print(f"WARN source dir missing: {src}", file=sys.stderr)
            continue
        # Cheap source-tag: "senorgif" if path ends with that, else "multif"
        src_tag = "senorgif" if src.name == "senorgif" else "multif"
        for child in sorted(src.iterdir()):
            if not child.is_dir():
                continue
            # Walk to find the first funscript with an axis suffix
            picked: tuple[Path, str] | None = None
            for root, _dirs, files in os.walk(child):
                for f in sorted(files):
                    if not f.endswith(".funscript"):
                        continue
                    m = AXIS_RE.search(f)
                    if m and m.group(1) in ALL_AXES:
                        base = f[: m.start()]
                        picked = (Path(root), base)
                        break
                if picked:
                    break
            if picked:
                sessions.append((f"{src_tag}__{child.name}", picked[0], picked[1]))
    return sessions


def load_session_axes(folder: Path, base: str) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Return {axis: (times_ms, pos)} for every present axis."""
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    # Cache filename listing per directory walk
    file_map: dict[str, Path] = {}
    for root, _, files in os.walk(folder):
        root_p = Path(root)
        for f in files:
            file_map[f] = root_p / f
    for axis in ALL_AXES:
        target = f"{base}.{axis}.funscript"
        if target in file_map:
            parsed = load_funscript(file_map[target])
            if parsed is not None:
                out[axis] = parsed
    return out


def resample_axis(
    arrs: tuple[np.ndarray, np.ndarray],
    t_start_ms: float,
    t_end_ms: float,
    n: int,
) -> np.ndarray:
    """Linear-interpolate pre-parsed (times, pos) arrays into n samples."""
    times, poses = arrs
    if times.size == 0 or n <= 0:
        return np.zeros(n, dtype=np.float32)
    grid = np.linspace(t_start_ms, t_end_ms, n, dtype=np.float64)
    return np.interp(grid, times, poses).astype(np.float32)


# ---------------------------------------------------------------------------
# Heuristic detectors
# ---------------------------------------------------------------------------

def _slope_per_s(samples: np.ndarray, win_s: float) -> float:
    if samples.size < 2 or win_s <= 0:
        return 0.0
    # least-squares slope in pos/sec
    t = np.linspace(0.0, win_s, samples.size)
    a, _b = np.polyfit(t, samples, 1)
    return float(a)


def _zero_crossings(samples: np.ndarray, mid: float) -> int:
    sign = np.sign(samples - mid)
    nz = sign != 0
    if nz.sum() < 2:
        return 0
    s = sign[nz]
    return int((s[1:] != s[:-1]).sum())


def _phase_unwrap_sweep(alpha: np.ndarray, beta: np.ndarray) -> tuple[float, float, float]:
    """Return (sweep_rad, mean_radius, radius_cv)."""
    a = alpha - 50.0
    b = beta - 50.0
    radii = np.hypot(a, b)
    rmean = float(radii.mean())
    rstd = float(radii.std())
    angles = np.arctan2(b, a)
    # unwrap in-place via np.unwrap
    unw = np.unwrap(angles)
    sweep = float(abs(unw[-1] - unw[0]))
    cv = (rstd / rmean) if rmean > 1e-6 else 1.0
    return sweep, rmean, cv


def _bimodality(samples: np.ndarray) -> float:
    """Rough bimodality coefficient (0..1 — higher = more bimodal)."""
    if samples.size < 4:
        return 0.0
    s = samples.astype(np.float64)
    s = (s - s.mean())
    sd = s.std()
    if sd < 1e-6:
        return 0.0
    s = s / sd
    # Sarle's bimodality: (skew^2 + 1) / kurtosis
    n = float(s.size)
    skew = float((s ** 3).mean())
    kurt = float((s ** 4).mean()) + 1e-9
    bc = (skew ** 2 + 1.0) / kurt
    # normalise: BC for uniform = ~0.55, for Gaussian = 0.33
    return float(min(max(bc - 0.33, 0.0) / 0.55, 1.0))


def detect_static_floor(alpha: np.ndarray, beta: np.ndarray) -> tuple[bool, float]:
    """P1 — alpha ~ 0, beta ~ 50, both nearly constant."""
    if alpha.std() < 2.0 and beta.std() < 2.0 and alpha.mean() < 10.0 and abs(beta.mean() - 50.0) < 5.0:
        return True, 0.95
    return False, 0.0


def detect_static_center(alpha: np.ndarray, beta: np.ndarray) -> tuple[bool, float]:
    """P2 — alpha ~ 50, beta ~ 50."""
    if alpha.std() < 3.0 and beta.std() < 3.0 and abs(alpha.mean() - 50.0) < 5.0 and abs(beta.mean() - 50.0) < 5.0:
        return True, 0.9
    return False, 0.0


def detect_alpha_rotation(alpha: np.ndarray, beta: np.ndarray) -> tuple[bool, float]:
    """P8 — full-circle rotation. Sweep>pi, stable radius, mean radius>10."""
    if alpha.size < 20 or beta.size < 20:
        return False, 0.0
    sweep, rmean, cv = _phase_unwrap_sweep(alpha, beta)
    if rmean > 12.0 and cv < 0.55 and sweep > math.pi:
        # confidence scaled by sweep magnitude
        conf = min(0.6 + (sweep / (4 * math.pi)), 0.95)
        return True, float(conf)
    return False, 0.0


def detect_half_pendel(alpha: np.ndarray, beta: np.ndarray) -> tuple[bool, float]:
    """P9 — alpha varies broadly, beta locked."""
    if alpha.std() > 18.0 and beta.std() < 12.0:
        return True, 0.7
    return False, 0.0


def detect_beta_lock(alpha: np.ndarray, beta: np.ndarray) -> tuple[bool, float]:
    """P7 — alpha pendulum, beta locked at 50 (slightly stricter than P9)."""
    if alpha.std() > 25.0 and beta.std() < 6.0 and abs(beta.mean() - 50.0) < 8.0:
        return True, 0.85
    return False, 0.0


def detect_micro_jitter(alpha: np.ndarray) -> tuple[bool, float]:
    """P11 — low stdev, high zero-crossings around mean."""
    if alpha.std() < 6.0 and _zero_crossings(alpha, float(alpha.mean())) > 10:
        return True, 0.7
    return False, 0.0


def detect_step_climb(alpha: np.ndarray) -> tuple[bool, float]:
    """P12 — step-wise ascending. Use cumulative slope test."""
    if alpha.size < 10:
        return False, 0.0
    # find roughly monotonic step-wise increase
    # split into 4 sub-windows, mean of each must increase (with tolerance)
    chunks = np.array_split(alpha, 4)
    means = np.array([c.mean() for c in chunks])
    diffs = np.diff(means)
    if (diffs > 2.0).sum() >= 2 and means[-1] - means[0] > 15.0:
        return True, 0.6
    return False, 0.0


def detect_beat_lock_position(alpha: np.ndarray, win_s: float) -> tuple[bool, float]:
    """P3 / P15 — sinus-like swings 0.5..2 Hz with multiple zero crossings."""
    if alpha.std() < 18.0:
        return False, 0.0
    crossings = _zero_crossings(alpha, float(alpha.mean()))
    # crossings/window/2 ≈ frequency
    if crossings < 4:
        return False, 0.0
    freq = crossings / (2.0 * win_s)
    if 0.5 <= freq <= 3.0 and alpha.std() > 20.0:
        return True, 0.7
    return False, 0.0


def detect_hard_toggle(alpha: np.ndarray) -> tuple[bool, float]:
    """P5 — square-wave toggle between two extremes."""
    if alpha.size < 8:
        return False, 0.0
    if _bimodality(alpha) > 0.4 and alpha.std() > 25.0:
        # check that values cluster at two ends
        lo = (alpha < (alpha.mean() - alpha.std() * 0.5)).sum()
        hi = (alpha > (alpha.mean() + alpha.std() * 0.5)).sum()
        if lo > alpha.size * 0.25 and hi > alpha.size * 0.25:
            return True, 0.8
    return False, 0.0


# Volume detectors -----------------------------------------------------------

def detect_volume_constant(volume: np.ndarray) -> tuple[bool, float]:
    """V1 within a slot (constant local volume) — used as fallback when no movement."""
    if volume.std() < 2.0:
        return True, 0.85
    return False, 0.0


def detect_volume_linear_build(volume: np.ndarray, win_s: float) -> tuple[bool, float]:
    """V9-style local linear build inside the window."""
    if volume.size < 8:
        return False, 0.0
    slope = _slope_per_s(volume, win_s)
    span = float(volume.max() - volume.min())
    if slope > 1.5 and span > 8.0 and volume.std() > 4.0:
        return True, min(0.5 + slope / 30.0, 0.9)
    return False, 0.0


def detect_volume_step_climb(volume: np.ndarray) -> tuple[bool, float]:
    """V8 / step-climb."""
    if volume.size < 10:
        return False, 0.0
    chunks = np.array_split(volume, 4)
    means = np.array([c.mean() for c in chunks])
    if np.all(np.diff(means) >= -1.0) and (means[-1] - means[0]) > 8.0:
        return True, 0.6
    return False, 0.0


def detect_volume_spike_drop(volume: np.ndarray) -> tuple[bool, float]:
    """V6 — sudden jump >20% then drop within window."""
    if volume.size < 8:
        return False, 0.0
    diffs = np.diff(volume)
    pos = np.argmax(diffs)
    neg = np.argmin(diffs)
    if diffs[pos] > 20.0 and diffs[neg] < -20.0 and pos < neg:
        return True, 0.75
    return False, 0.0


def detect_volume_two_level(volume: np.ndarray) -> tuple[bool, float]:
    """V9 / V10 two-level toggle."""
    if volume.size < 8:
        return False, 0.0
    if _bimodality(volume) > 0.45 and volume.std() > 8.0:
        return True, 0.65
    return False, 0.0


def detect_volume_saturation(volume: np.ndarray) -> tuple[bool, float]:
    """V11 — value glued to top."""
    if volume.size < 4:
        return False, 0.0
    if volume.mean() > 92.0 and volume.std() < 5.0:
        return True, 0.85
    return False, 0.0


# Pulse-frequency / pulse-width / pulse-rise-time ---------------------------

def detect_pf_static(pf: np.ndarray) -> tuple[bool, float]:
    if pf.std() < 2.0:
        return True, 0.85
    return False, 0.0


def detect_pf_spike_drop(pf: np.ndarray) -> tuple[bool, float]:
    """PF5 — quick up & quick back down (return to roughly same baseline)."""
    if pf.size < 8:
        return False, 0.0
    diffs = np.diff(pf)
    if diffs.max() > 20.0 and diffs.min() < -20.0:
        # Baseline check
        start_med = float(np.median(pf[: max(2, pf.size // 5)]))
        end_med = float(np.median(pf[-max(2, pf.size // 5) :]))
        if abs(end_med - start_med) < 12.0 and (pf.max() - start_med) > 20.0:
            return True, 0.75
    return False, 0.0


def detect_pw_sawtooth(pw: np.ndarray) -> tuple[bool, float]:
    """PW1 — bimodal pulse_width oscillation."""
    if pw.size < 8:
        return False, 0.0
    if _bimodality(pw) > 0.45 and pw.std() > 6.0 and _zero_crossings(pw, float(pw.mean())) > 4:
        return True, 0.7
    return False, 0.0


def detect_pw_linear_build(pw: np.ndarray, win_s: float) -> tuple[bool, float]:
    if pw.size < 8:
        return False, 0.0
    slope = _slope_per_s(pw, win_s)
    if slope > 1.0 and pw.std() > 3.0:
        return True, min(0.5 + slope / 20.0, 0.85)
    return False, 0.0


def detect_pw_plateau_hold(pw: np.ndarray) -> tuple[bool, float]:
    if pw.size < 4:
        return False, 0.0
    if pw.std() < 2.0:
        return True, 0.8
    return False, 0.0


def detect_pr_falling(pr: np.ndarray, win_s: float) -> tuple[bool, float]:
    """PR1 — falling rise time."""
    if pr.size < 8:
        return False, 0.0
    slope = _slope_per_s(pr, win_s)
    if slope < -1.0 and pr.std() > 2.0:
        return True, min(0.5 + abs(slope) / 20.0, 0.85)
    return False, 0.0


def detect_pr_mid_hold(pr: np.ndarray) -> tuple[bool, float]:
    if pr.size < 4:
        return False, 0.0
    if 18.0 <= pr.mean() <= 45.0 and pr.std() < 6.0:
        return True, 0.7
    return False, 0.0


# Carrier --------------------------------------------------------------------

def detect_carrier_static(freq: np.ndarray) -> tuple[bool, float]:
    if freq.std() < 2.0:
        return True, 0.85
    return False, 0.0


def detect_carrier_volume_lockstep(volume: np.ndarray, freq: np.ndarray) -> tuple[bool, float]:
    if volume.size < 8 or freq.size < 8:
        return False, 0.0
    vstd = volume.std(); fstd = freq.std()
    if vstd < 2.0 or fstd < 2.0:
        return False, 0.0
    r = float(np.corrcoef(volume, freq)[0, 1])
    if r > 0.85:
        return True, min(0.6 + r / 3.0, 0.95)
    return False, 0.0


def detect_carrier_linear_sweep(freq: np.ndarray, win_s: float) -> tuple[bool, float]:
    if freq.size < 8:
        return False, 0.0
    slope = _slope_per_s(freq, win_s)
    if abs(slope) > 1.5 and freq.std() > 4.0:
        return True, min(0.5 + abs(slope) / 30.0, 0.9)
    return False, 0.0


# Multi-axis -----------------------------------------------------------------

def detect_triple_sync_build(volume: np.ndarray, freq: np.ndarray, pw: np.ndarray, win_s: float) -> tuple[bool, float]:
    """M1 — Volume + Carrier + PulseWidth all rising."""
    if volume.size < 8 or freq.size < 8 or pw.size < 8:
        return False, 0.0
    sv = _slope_per_s(volume, win_s)
    sf = _slope_per_s(freq, win_s)
    sp = _slope_per_s(pw, win_s)
    if sv > 0.8 and sf > 0.8 and sp > 0.5:
        return True, 0.75
    return False, 0.0


def detect_mirror_prostate(alpha: np.ndarray, alpha_p: np.ndarray) -> tuple[bool, float]:
    """M3 — alpha and alpha-prostate strongly anti-correlated."""
    if alpha.size < 8 or alpha_p.size < 8 or alpha.std() < 2.0 or alpha_p.std() < 2.0:
        return False, 0.0
    r = float(np.corrcoef(alpha, alpha_p)[0, 1])
    if r < -0.85:
        return True, min(0.7 + abs(r) / 3.0, 0.95)
    return False, 0.0


def detect_stereostim_floor(volume: np.ndarray, vss: np.ndarray) -> tuple[bool, float]:
    """M5 — volume-stereostim closely tracks volume but never below 50."""
    if volume.size < 8 or vss.size < 8:
        return False, 0.0
    if vss.min() >= 48.0 and float(np.corrcoef(volume, vss)[0, 1]) > 0.85:
        return True, 0.85
    return False, 0.0


def detect_4phase_round_robin(e1: np.ndarray, e2: np.ndarray, e3: np.ndarray, e4: np.ndarray) -> tuple[bool, float]:
    """M6 — paired anti-correlation across e1..e4."""
    if min(e1.size, e2.size, e3.size, e4.size) < 8:
        return False, 0.0
    if min(e1.std(), e2.std(), e3.std(), e4.std()) < 2.0:
        return False, 0.0
    r13 = float(np.corrcoef(e1, e3)[0, 1])
    r24 = float(np.corrcoef(e2, e4)[0, 1])
    if r13 < -0.2 and r24 < -0.2:
        return True, 0.75
    return False, 0.0


def detect_pmix1(pf: np.ndarray, pw: np.ndarray, pr: np.ndarray) -> tuple[bool, float]:
    """PMix1 — PF↑ + PW↑ + PR↓ at the same time (correlation-based)."""
    if pf.size < 8 or pw.size < 8 or pr.size < 8:
        return False, 0.0
    if pf.std() < 2.0 or pw.std() < 2.0 or pr.std() < 2.0:
        return False, 0.0
    r_pwpf = float(np.corrcoef(pf, pw)[0, 1])
    r_pfpr = float(np.corrcoef(pf, pr)[0, 1])
    r_pwpr = float(np.corrcoef(pw, pr)[0, 1])
    if r_pwpf > 0.5 and r_pfpr < -0.5 and r_pwpr < -0.5:
        return True, 0.8
    return False, 0.0


def detect_pmix2(pf: np.ndarray, pw: np.ndarray, pr: np.ndarray) -> tuple[bool, float]:
    """PMix2 — soft pulse: PW low, PR high, PF mid."""
    if pf.size < 4 or pw.size < 4 or pr.size < 4:
        return False, 0.0
    if pw.mean() < 25.0 and pr.mean() > 40.0 and 35.0 <= pf.mean() <= 65.0:
        return True, 0.7
    return False, 0.0


def detect_pmix3(pf: np.ndarray, pw: np.ndarray, pr: np.ndarray) -> tuple[bool, float]:
    """PMix3 — hard click: PF high, PW high, PR low."""
    if pf.size < 4 or pw.size < 4 or pr.size < 4:
        return False, 0.0
    if pf.mean() > 70.0 and pw.mean() > 50.0 and pr.mean() < 20.0:
        return True, 0.75
    return False, 0.0


# ---------------------------------------------------------------------------
# Per-window classification
# ---------------------------------------------------------------------------


def classify_window(samples: dict[str, np.ndarray]) -> tuple[str | None, float]:
    """Run heuristics in a deterministic priority order.

    Returns (pattern_id, confidence) or (None, 0.0) if no heuristic fires.
    Priority is roughly multi-axis -> position -> pulse-mix -> per-axis.
    """
    a = samples.get("alpha")
    b = samples.get("beta")
    v = samples.get("volume")
    pf = samples.get("pulse_frequency")
    pw = samples.get("pulse_width")
    pr = samples.get("pulse_rise_time")
    fr = samples.get("frequency")
    ap = samples.get("alpha-prostate")
    vss = samples.get("volume-stereostim")
    e1 = samples.get("e1"); e2 = samples.get("e2"); e3 = samples.get("e3"); e4 = samples.get("e4")

    # ---- Multi-axis (high specificity first) ----
    if e1 is not None and e2 is not None and e3 is not None and e4 is not None:
        ok, conf = detect_4phase_round_robin(e1, e2, e3, e4)
        if ok:
            return "M6", conf
    if v is not None and vss is not None:
        ok, conf = detect_stereostim_floor(v, vss)
        if ok:
            return "M5", conf
    if a is not None and ap is not None:
        ok, conf = detect_mirror_prostate(a, ap)
        if ok:
            return "M3", conf
    if v is not None and fr is not None and pw is not None:
        ok, conf = detect_triple_sync_build(v, fr, pw, WIN_S)
        if ok:
            return "M1", conf
    if v is not None and fr is not None:
        ok, conf = detect_carrier_volume_lockstep(v, fr)
        if ok:
            return "C2", conf

    # ---- Pulse-mix bundles ----
    if pf is not None and pw is not None and pr is not None:
        ok, conf = detect_pmix1(pf, pw, pr)
        if ok:
            return "PMix1", conf
        ok, conf = detect_pmix3(pf, pw, pr)
        if ok:
            return "PMix3", conf
        ok, conf = detect_pmix2(pf, pw, pr)
        if ok:
            return "PMix2", conf

    # ---- Position patterns ----
    if a is not None and b is not None:
        ok, conf = detect_static_floor(a, b)
        if ok:
            return "P1", conf
        ok, conf = detect_static_center(a, b)
        if ok:
            return "P2", conf
        ok, conf = detect_alpha_rotation(a, b)
        if ok:
            return "P8", conf
        ok, conf = detect_beta_lock(a, b)
        if ok:
            return "P7", conf
        ok, conf = detect_half_pendel(a, b)
        if ok:
            return "P9", conf
        ok, conf = detect_hard_toggle(a)
        if ok:
            return "P5", conf
        ok, conf = detect_beat_lock_position(a, WIN_S)
        if ok:
            return "P3", conf
        ok, conf = detect_step_climb(a)
        if ok:
            return "P12", conf
        ok, conf = detect_micro_jitter(a)
        if ok:
            return "P11", conf

    # ---- Volume ----
    if v is not None:
        ok, conf = detect_volume_saturation(v)
        if ok:
            return "V11", conf
        ok, conf = detect_volume_spike_drop(v)
        if ok:
            return "V6", conf
        ok, conf = detect_volume_step_climb(v)
        if ok:
            return "V8", conf
        ok, conf = detect_volume_linear_build(v, WIN_S)
        if ok:
            return "V9", conf
        ok, conf = detect_volume_two_level(v)
        if ok:
            return "V9", conf
        ok, conf = detect_volume_constant(v)
        if ok:
            return "V1", conf

    # ---- Pulse axes ----
    if pf is not None:
        ok, conf = detect_pf_spike_drop(pf)
        if ok:
            return "PF5", conf
        ok, conf = detect_pf_static(pf)
        if ok:
            return "PF1", conf
    if pw is not None:
        ok, conf = detect_pw_sawtooth(pw)
        if ok:
            return "PW1", conf
        ok, conf = detect_pw_linear_build(pw, WIN_S)
        if ok:
            return "PW2", conf
        ok, conf = detect_pw_plateau_hold(pw)
        if ok:
            return "PW5", conf
    if pr is not None:
        ok, conf = detect_pr_falling(pr, WIN_S)
        if ok:
            return "PR1", conf
        ok, conf = detect_pr_mid_hold(pr)
        if ok:
            return "PR3", conf

    if fr is not None:
        ok, conf = detect_carrier_linear_sweep(fr, WIN_S)
        if ok:
            return "C3", conf
        ok, conf = detect_carrier_static(fr)
        if ok:
            return "C1", conf

    return None, 0.0


# ---------------------------------------------------------------------------
# Per-window feature extraction (used for clustering Phase 2)
# ---------------------------------------------------------------------------

FEATURE_AXES = ["alpha", "beta", "volume", "pulse_frequency", "pulse_width", "pulse_rise_time", "frequency"]


def window_features(samples: dict[str, np.ndarray]) -> np.ndarray:
    """Build a fixed-length feature vector for clustering.

    Per axis: mean, std, slope (per s), max-min span, zero-crossings around mean.
    Missing axis -> zeros.
    """
    feats: list[float] = []
    for ax in FEATURE_AXES:
        s = samples.get(ax)
        if s is None or s.size < 2:
            feats.extend([0.0, 0.0, 0.0, 0.0, 0.0])
            continue
        m = float(s.mean())
        sd = float(s.std())
        slope = _slope_per_s(s, WIN_S)
        span = float(s.max() - s.min())
        zc = float(_zero_crossings(s, m))
        feats.extend([m, sd, slope, span, zc])
    return np.array(feats, dtype=np.float32)


# Map cluster centroid feature signature -> fallback pattern id
def map_cluster_to_pattern(centroid: np.ndarray) -> tuple[str, float]:
    """Heuristic mapping of a KMeans centroid back to a pattern id.

    Centroid layout follows window_features order:
        for ax in FEATURE_AXES: [mean, std, slope, span, zc]
    """
    f = centroid
    # Indices
    idx = {ax: i * 5 for i, ax in enumerate(FEATURE_AXES)}

    a_mean, a_std, a_slope, a_span, a_zc = f[idx["alpha"]:idx["alpha"] + 5]
    v_mean, v_std, v_slope, v_span, v_zc = f[idx["volume"]:idx["volume"] + 5]
    pw_mean, pw_std, pw_slope, _pw_span, _pw_zc = f[idx["pulse_width"]:idx["pulse_width"] + 5]
    pr_mean, pr_std, pr_slope, _pr_span, _pr_zc = f[idx["pulse_rise_time"]:idx["pulse_rise_time"] + 5]
    pf_mean, pf_std, pf_slope, _pf_span, _pf_zc = f[idx["pulse_frequency"]:idx["pulse_frequency"] + 5]
    f_mean, f_std, f_slope, _f_span, _f_zc = f[idx["frequency"]:idx["frequency"] + 5]

    # Position-dominated cluster
    if a_std > 20.0:
        if a_zc > 8.0:
            return "P3", 0.45  # beat-lock
        if a_slope > 3.0:
            return "P6", 0.4   # slow drift / monotone
        return "P9", 0.4  # bow swing
    if a_std > 5.0 and a_std <= 20.0:
        return "P10", 0.4  # asymmetric half-stroke

    # Volume-dominated cluster
    if v_std > 8.0:
        if v_slope > 1.0:
            return "V2", 0.45
        return "V12", 0.4
    if v_mean > 90.0 and v_std < 4.0:
        return "V11", 0.55
    if v_mean < 30.0 and v_std < 4.0:
        return "V5", 0.45

    # Pulse-width / rise-time / frequency activity
    if pw_std > 6.0 and pr_std > 4.0:
        return "PW3", 0.35
    if pw_slope > 0.6:
        return "PW2", 0.45
    if pr_slope < -0.6:
        return "PR1", 0.45
    if pf_slope > 0.6:
        return "PF4", 0.45
    if f_slope > 0.6:
        return "C3", 0.45
    if f_std < 2.0 and v_std < 2.0:
        return "P2", 0.4  # static both axes -> centred neutral
    return "M14", 0.3  # generic "independent multi-stream"


# ---------------------------------------------------------------------------
# Annotate one session
# ---------------------------------------------------------------------------


def annotate_session(name: str, folder: Path, base: str) -> dict:
    t0 = time.perf_counter()
    axes = load_session_axes(folder, base)

    # Determine session length
    if not axes:
        return {"session": name, "skipped": True, "reason": "no axes loaded"}

    end_ms = max(float(arrs[0][-1]) for arrs in axes.values())
    if end_ms < WIN_S * 1000:
        return {"session": name, "skipped": True, "reason": f"too short ({end_ms} ms)"}

    available = sorted(axes.keys())
    has_position = "alpha" in axes and "beta" in axes
    has_volume = "volume" in axes
    if not has_volume and not has_position:
        return {"session": name, "skipped": True, "reason": "no position or volume axes"}

    # Build slot grid
    slots: list[dict] = []
    pending_features: list[tuple[int, np.ndarray, dict[str, np.ndarray]]] = []
    n_samples_per_window = 64  # 12.8 Hz — enough to resolve 1.4 Hz beats
    end_s = end_ms / 1000.0

    # PERF: resample each axis once across the whole session at the per-window
    # sample rate (12.8 Hz). For long Hypno sessions (Liya 136 min, 11M actions
    # per axis) this avoids re-interpolating against 11M-point arrays per window.
    sps = n_samples_per_window / WIN_S  # samples per second
    n_total = max(int(end_s * sps), n_samples_per_window)
    global_grid_ms = np.linspace(0.0, end_s * 1000.0, n_total, dtype=np.float64)
    global_axes: dict[str, np.ndarray] = {}
    for ax, arrs in axes.items():
        times, poses = arrs
        global_axes[ax] = np.interp(global_grid_ms, times, poses).astype(np.float32)

    samples_per_hop = max(int(round(HOP_S * sps)), 1)

    t = 0.0
    slot_idx = 0
    while t < end_s:
        t_end = min(t + WIN_S, end_s)
        if t_end - t < 1.0:
            break
        i0 = int(t * sps)
        i1 = min(i0 + n_samples_per_window, n_total)
        if i1 - i0 < 8:
            break
        samples: dict[str, np.ndarray] = {ax: arr[i0:i1] for ax, arr in global_axes.items()}
        pid, conf = classify_window(samples)
        if pid is None:
            pending_features.append((slot_idx, window_features(samples), samples))
            slots.append({
                "t_start_s": round(t, 3),
                "t_end_s": round(t_end, 3),
                "pattern_id": "unknown",
                "confidence": 0.0,
            })
        else:
            slots.append({
                "t_start_s": round(t, 3),
                "t_end_s": round(t_end, 3),
                "pattern_id": pid,
                "confidence": round(float(conf), 3),
            })
        slot_idx += 1
        t += HOP_S

    # Phase-2 cluster fallback for unknown slots (per session)
    if pending_features and HAVE_SKLEARN and len(pending_features) >= 4:
        feats = np.stack([f for _, f, _ in pending_features])
        # Z-normalise
        mean = feats.mean(axis=0)
        std = feats.std(axis=0) + 1e-6
        feats_z = (feats - mean) / std
        n_clusters = min(6, len(pending_features))
        try:
            km = KMeans(n_clusters=n_clusters, random_state=RNG_SEED, n_init=4)
            labels = km.fit_predict(feats_z)
            centroids_real = km.cluster_centers_ * std + mean
            for (slot_i, _f, _samples), lbl in zip(pending_features, labels):
                pid, conf = map_cluster_to_pattern(centroids_real[lbl])
                slots[slot_i]["pattern_id"] = pid
                slots[slot_i]["confidence"] = round(float(conf), 3)
                slots[slot_i]["source"] = "cluster"
        except Exception as e:
            print(f"WARN cluster failed for {name}: {e}", file=sys.stderr)

    # Collapse overlap: each slot's effective interval is [t_start, t_start+HOP).
    # Then merge adjacent same-pattern slots into contiguous runs. The last slot
    # keeps its full WIN_S extent so the final time still maps to actual data.
    merged: list[dict] = []
    for i, s in enumerate(slots):
        eff_end = s["t_start_s"] + HOP_S if i < len(slots) - 1 else s["t_end_s"]
        eff_end = round(min(eff_end, end_s), 3)
        if merged and merged[-1]["pattern_id"] == s["pattern_id"]:
            merged[-1]["t_end_s"] = eff_end
            merged[-1]["confidence"] = round(max(merged[-1]["confidence"], s["confidence"]), 3)
        else:
            merged.append({
                "t_start_s": s["t_start_s"],
                "t_end_s": eff_end,
                "pattern_id": s["pattern_id"],
                "confidence": s["confidence"],
            })

    pattern_count = Counter(s["pattern_id"] for s in slots)
    unknown_slots = pattern_count.get("unknown", 0)
    elapsed = time.perf_counter() - t0
    stats = {
        "n_slots_raw": len(slots),
        "n_slots_merged": len(merged),
        "axes": available,
        "duration_s": round(end_s, 2),
        "unknown_slots": unknown_slots,
        "annotation_time_s": round(elapsed, 2),
        "pattern_counts": dict(pattern_count),
    }
    return {"session": name, "slots": merged, "stats": stats}


# ---------------------------------------------------------------------------
# Compatibility matrix + frequency
# ---------------------------------------------------------------------------


def build_compatibility_matrix(per_session: list[dict]) -> dict:
    counts: dict[str, Counter] = defaultdict(Counter)
    for ann in per_session:
        if ann.get("skipped"):
            continue
        slots = ann.get("slots", [])
        for a, b in zip(slots, slots[1:]):
            counts[a["pattern_id"]][b["pattern_id"]] += 1
    # Add-1 Laplace smoothing across the canonical ID set + 'unknown'
    target_ids = list(ALL_PATTERN_IDS) + ["unknown"]
    matrix: dict[str, dict[str, float]] = {}
    for from_id in target_ids:
        row_counts = counts.get(from_id, Counter())
        # smoothed counts
        smoothed_total = sum(row_counts.values()) + len(target_ids)
        row: dict[str, float] = {}
        for to_id in target_ids:
            row[to_id] = round((row_counts.get(to_id, 0) + 1) / smoothed_total, 5)
        matrix[from_id] = row
    return matrix


def build_pattern_frequency(per_session: list[dict]) -> Counter:
    freq = Counter()
    for ann in per_session:
        if ann.get("skipped"):
            continue
        for s in ann.get("slots", []):
            # Weight each slot by its duration in seconds
            dur = max(0.0, s["t_end_s"] - s["t_start_s"])
            freq[s["pattern_id"]] += int(round(dur))
    return freq


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def write_report(per_session: list[dict], freq: Counter, matrix: dict, out_path: Path):
    annotated = [a for a in per_session if not a.get("skipped")]
    skipped = [a for a in per_session if a.get("skipped")]
    total_slots = sum(a["stats"]["n_slots_raw"] for a in annotated)
    unknown_slots = sum(a["stats"]["unknown_slots"] for a in annotated)
    total_dur_s = sum(freq.values())  # frequency is duration-weighted
    pct_unknown = (unknown_slots / total_slots * 100.0) if total_slots else 0.0

    top_patterns = freq.most_common(10)

    # Top-5 transitions (excluding self -> self)
    transitions: list[tuple[str, str, float]] = []
    for from_id, row in matrix.items():
        for to_id, prob in row.items():
            if from_id == to_id:
                continue
            transitions.append((from_id, to_id, prob))
    transitions.sort(key=lambda r: -r[2])

    lines = [
        "# Pattern Annotation Report",
        "",
        f"- Sessions discovered: {len(per_session)}",
        f"- Annotated successfully: {len(annotated)}",
        f"- Skipped: {len(skipped)}",
    ]
    if skipped:
        lines.append("")
        lines.append("## Skipped sessions")
        for s in skipped:
            lines.append(f"- `{s['session']}` — {s.get('reason')}")
    lines += [
        "",
        "## Coverage",
        f"- Total raw slots: {total_slots}",
        f"- Unknown slots: {unknown_slots} ({pct_unknown:.1f} %)",
        f"- Total annotated duration (s, dur-weighted): {total_dur_s}",
        "",
        "## Top-10 patterns by total annotated duration",
    ]
    for pid, dur in top_patterns:
        lines.append(f"- `{pid}` — {dur} s")
    lines += [
        "",
        "## Top-5 pattern transitions (smoothed Add-1)",
    ]
    for from_id, to_id, prob in transitions[:5]:
        lines.append(f"- `{from_id}` -> `{to_id}` — {prob:.4f}")

    # Sample 3 slots from 3 different sessions
    sampled = []
    for ann in annotated[:3]:
        slots = ann.get("slots", [])
        if slots:
            sampled.append((ann["session"], slots[len(slots) // 2]))
    lines += ["", "## Sample slots (sanity check)"]
    for sess, slot in sampled:
        lines.append(
            f"- `{sess}` — t={slot['t_start_s']:.1f}..{slot['t_end_s']:.1f}s, id={slot['pattern_id']}, conf={slot['confidence']}"
        )

    lines += ["", "## Per-session axis availability"]
    for ann in annotated:
        st = ann["stats"]
        lines.append(
            f"- `{ann['session']}` — {st['duration_s']}s, {st['n_slots_merged']} slots, axes={','.join(st['axes'])}"
        )

    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("[annotate_patterns] sklearn available:", HAVE_SKLEARN)
    sessions = discover_sessions()
    print(f"[annotate_patterns] Discovered {len(sessions)} sessions")

    per_session: list[dict] = []
    for name, folder, base in sessions:
        print(f"  -> annotating {name!r} (base='{base}')", flush=True)
        try:
            ann = annotate_session(name, folder, base)
        except Exception as e:
            print(f"WARN annotate failed for {name}: {e}", file=sys.stderr)
            ann = {"session": name, "skipped": True, "reason": f"exception: {e}"}
        per_session.append(ann)
        # write per-session JSON immediately
        sess_safe = re.sub(r"[^A-Za-z0-9_.\-]+", "_", name).strip("_") or "session"
        sess_path = PER_SESSION_DIR / f"{sess_safe}.json"
        with open(sess_path, "w", encoding="utf-8") as f:
            json.dump(ann, f, indent=1)

    # Compatibility matrix + frequency
    print("[annotate_patterns] building compatibility matrix...")
    matrix = build_compatibility_matrix(per_session)
    with open(OUT_DIR / "compatibility_matrix.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, indent=1)

    print("[annotate_patterns] building pattern frequency...")
    freq = build_pattern_frequency(per_session)
    with open(OUT_DIR / "pattern_frequency.json", "w", encoding="utf-8") as f:
        json.dump(dict(freq.most_common()), f, indent=1)

    print("[annotate_patterns] writing report...")
    write_report(per_session, freq, matrix, OUT_DIR / "annotation_report.md")

    # Console summary
    annotated = [a for a in per_session if not a.get("skipped")]
    skipped = [a for a in per_session if a.get("skipped")]
    total_slots = sum(a["stats"]["n_slots_raw"] for a in annotated)
    unknown_slots = sum(a["stats"]["unknown_slots"] for a in annotated)
    print()
    print("=" * 60)
    print(f"Sessions annotated: {len(annotated)}")
    print(f"Sessions skipped:   {len(skipped)}")
    if skipped:
        for s in skipped:
            print(f"  - {s['session']}: {s.get('reason')}")
    print(f"Total slots: {total_slots}, unknown: {unknown_slots} ({(unknown_slots / total_slots * 100.0 if total_slots else 0):.1f} %)")
    print("Top-10 patterns by duration:")
    for pid, dur in freq.most_common(10):
        print(f"  {pid:>6}  {dur} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
