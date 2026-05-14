"""
restim_event_converter.py

Standalone, single-shot converter that turns a Senorgif-style 1D funscript +
`.events.yml` event sidecar into the 7-axis Restim funscript bundle plus
prostate variants and the FOC-Stim e1-e4 motion-axis files.

The output bundle mirrors what `funscript-tools` (edger477/funscript-tools)
produces from the GUI/CLI, but the implementation is re-implemented inline so
this file has *no* GUI dependencies (no matplotlib, tkinter, ffpyplayer, Qt).
Only stdlib + numpy + PyYAML are required.

Usage
-----
    python scripts/restim_event_converter.py \\
        --input  references/senorgif-restim-events/CH\\ Audition\\ 3 \\
        --output data/training_funscripts/senorgif/CH_Audition_3

    # Bulk convert every session shipped under references/senorgif-restim-events
    python scripts/restim_event_converter.py --all

The output structure for `--all` is:
    data/training_funscripts/senorgif/<sessionname>/<basename>.<axis>.funscript

Generated axes (7 mandatory + variants):
    alpha, beta, volume, pulse_frequency, pulse_width,
    pulse_rise_time, frequency
    alpha-prostate, beta-prostate, volume-prostate
    e1, e2, e3, e4   (FOC-Stim 4-Phase response curves)

Algorithmic notes / honest assumptions
--------------------------------------
*   `convert_to_speed`, `combine_funscripts`, `make_volume_ramp`,
    `convert_funscript_radial`, `apply_response_curve_to_funscript`,
    `apply_linear_change`, `apply_modulation` were re-implemented from the
    upstream `funscript-tools` modules listed in the task brief (cli.py,
    processor.py, processing/*).  Behaviour matches the upstream code 1:1 for
    the inputs we feed.
*   The upstream pulse_rise_time pipeline pre-maps `ramp_inverted` and
    `speed_inverted` and then linearly remaps to (rise_min, rise_max).  This
    converter does the same with the documented defaults.  The exact pulse
    width *curve* upstream uses a more complex `mirror_up_funscript` step on
    beta — we use the same path as the simplified upstream implementation
    (`limit_funscript(main_inverted)` combined with speed) which is what
    `processor.py` itself uses, see ALGORITHM_REDESIGN notes in the upstream
    repo.  See ASSUMPTION-1 below.
*   Event normalization defaults are taken verbatim from
    `references/funscript-tools/config.event_definitions.yml`:
        pulse_frequency.max = 120.0 Hz
        pulse_width.max     = 100.0 (%)
        frequency.max       = 1200.0 Hz
        volume.max          = 1.0
*   Event handling uses the *simplified* fast/edge/cum/ruin/stay rules from
    the task brief, keyed off the actual `name` field, with the upstream
    config.event_definitions.yml definitions used as the canonical step list
    when the event name appears there (so `mcb_*`, `clutch_*`, `cum`, `lube`,
    `slow`, `medium`, `tranquil` etc. are all handled).  Unknown event names
    fall back to a no-op + warning (see ASSUMPTION-2).
*   FOC-Stim 4-phase e1-e4 default response curves are copied verbatim from
    `references/funscript-tools/config.py::DEFAULT_CONFIG['positional_axes']`.

This script is intentionally self-contained: a single `python <this file>`
call produces the full output set.  No imports from `references/` happen at
runtime; we re-implement the algorithms here so the script remains stable
even if the upstream snapshot changes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML is required.  Install with `pip install pyyaml` and re-run."
    ) from exc


# ---------------------------------------------------------------------------
# Funscript primitive (compatible serialization with restim/upstream)
# ---------------------------------------------------------------------------


class Funscript:
    """Minimal Funscript value object — values internally in 0.0-1.0."""

    def __init__(self, x, y, metadata: Optional[dict] = None):
        self.x = np.asarray(x, dtype=float)
        self.y = np.asarray(y, dtype=float)
        self.metadata: dict = dict(metadata) if metadata else {}

    def copy(self) -> "Funscript":
        return Funscript(self.x.copy(), self.y.copy(), dict(self.metadata))

    @staticmethod
    def from_file(path: Path) -> "Funscript":
        with open(path, "r", encoding="utf-8") as f:
            js = json.load(f)
        actions = js.get("actions") or []
        x = np.array([a["at"] / 1000.0 for a in actions], dtype=float)
        y = np.array([a["pos"] * 0.01 for a in actions], dtype=float)
        meta: dict = {}
        for k in ("title", "creator", "description", "url", "tags", "duration", "metadata"):
            if k in js:
                meta[k] = js[k]
        return Funscript(x, y, meta)

    def save_to_path(self, path: Path) -> None:
        # round to int ms / int 0-100 to match the standard funscript schema
        actions = [
            {"at": int(round(at * 1000.0)), "pos": int(round(float(np.clip(pos, 0.0, 1.0)) * 100))}
            for at, pos in zip(self.x, self.y)
        ]
        out = {"version": "1.0", "actions": actions}
        # always write a metadata block (empty if none provided)
        out["metadata"] = self.metadata if self.metadata else {}
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)


# ---------------------------------------------------------------------------
# Re-implemented primitives from `processing/*`
# ---------------------------------------------------------------------------


def add_interpolated_points(fs: Funscript, interval: float = 0.1) -> Funscript:
    if len(fs.x) < 2:
        raise ValueError("Need at least two points to interpolate.")
    x = fs.x
    start = int(x[0])
    end = int(x[-1])
    target = np.arange(start, end + 1, interval)
    interp = np.interp(target, fs.x, fs.y)
    return Funscript(target, interp, fs.metadata)


def calculate_speed_windowed(fs: Funscript, window_seconds: float = 5.0) -> Funscript:
    """Rolling absolute-position-change-per-second over a sliding window.

    Re-implementation of upstream `processing.speed_processing.calculate_speed_windowed`.
    Vectorised loop kept O(N) by exploiting the post-interpolation uniform grid.
    """
    x = fs.x
    y = fs.y
    n = len(x)
    if n < 3:
        return Funscript(x.copy(), np.zeros(n), fs.metadata)

    # Upstream uses 5 points/sec → shift = window_seconds * 5
    shift = int(window_seconds * 5)

    # Per-step absolute speed (pos change / time delta)
    dt = np.diff(x)
    dy = np.abs(np.diff(y))
    with np.errstate(divide="ignore", invalid="ignore"):
        step_speed = np.where(dt != 0, dy / dt, 0.0)

    # Rolling mean of step_speed inside a window of `window_seconds`
    out_x: List[float] = [float(x[0])]
    out_y: List[float] = [0.0]
    max_speed = 0.0

    # since x is uniform after interpolation we can use a fixed window length
    if n > 1:
        # number of step-speeds per window
        if dt.size > 0:
            avg_dt = float(np.mean(dt))
        else:
            avg_dt = 1.0
        win_steps = max(1, int(round(window_seconds / max(avg_dt, 1e-9))))
        # cumulative sum trick for window mean
        csum = np.concatenate(([0.0], np.cumsum(step_speed)))
        # for each i (1..n-1), avg over indices (i-win_steps..i)
        for i in range(1 + shift, n):
            lo = max(0, i - win_steps)
            count = i - lo
            avg = (csum[i] - csum[lo]) / max(count, 1)
            if avg > max_speed:
                max_speed = avg
            out_x.append(float(x[i - shift]))
            out_y.append(avg)

    out_x.append(float(x[-1]))
    out_y.append(0.0)

    out_y_arr = np.array(out_y)
    if max_speed > 0:
        out_y_arr = out_y_arr / max_speed

    return Funscript(np.array(out_x), out_y_arr, fs.metadata)


def convert_to_speed(fs: Funscript, window_seconds: float = 5.0,
                     interpolation_interval: float = 0.1) -> Funscript:
    fs_interp = add_interpolated_points(fs.copy(), interpolation_interval)
    return calculate_speed_windowed(fs_interp, window_seconds)


def invert_funscript(fs: Funscript) -> Funscript:
    return Funscript(fs.x.copy(), 1.0 - fs.y, fs.metadata)


def map_funscript(fs: Funscript, new_min: float, new_max: float) -> Funscript:
    cur_min = float(np.min(fs.y)) if len(fs.y) else 0.0
    cur_max = float(np.max(fs.y)) if len(fs.y) else 1.0
    if cur_max == cur_min:
        new_y = np.full_like(fs.y, (new_min + new_max) / 2.0)
    else:
        new_y = (fs.y - cur_min) / (cur_max - cur_min) * (new_max - new_min) + new_min
    return Funscript(fs.x.copy(), new_y, fs.metadata)


def limit_funscript(fs: Funscript, new_min: float, new_max: float) -> Funscript:
    return Funscript(fs.x.copy(), np.clip(fs.y, new_min, new_max), fs.metadata)


def normalize_funscript(fs: Funscript) -> Funscript:
    if len(fs.y) == 0:
        return fs.copy()
    shift = 1.0 - float(np.max(fs.y))
    return Funscript(fs.x.copy(), np.minimum(1.0, fs.y + shift), fs.metadata)


def combine_funscripts(left: Funscript, right: Funscript, ratio: float,
                       rest_level: float = 0.5,
                       ramp_up_duration: float = 0.0) -> Funscript:
    x = np.union1d(left.x, right.x)
    y_left = np.interp(x, left.x, left.y)
    y_right = np.interp(x, right.x, right.y)
    y = (y_left * (ratio - 1) + y_right) / ratio
    is_rest = (y_left == 0) | (y_right == 0)
    y_with_rest = np.where(is_rest, y * rest_level, y)
    if ramp_up_duration > 0:
        # find rest -> active transitions, ramp window centered there
        transitions = []
        for i in range(1, len(is_rest)):
            if is_rest[i - 1] and not is_rest[i]:
                transitions.append(x[i])
        time_rel = np.full_like(x, np.inf)
        half = ramp_up_duration / 2.0
        for i, xi in enumerate(x):
            for t in transitions:
                d = xi - t
                if -half <= d <= half:
                    time_rel[i] = d
                    break
        ramp_progress = np.clip((time_rel + half) / ramp_up_duration, 0.0, 1.0)
        ramp_mult = rest_level + (1.0 - rest_level) * ramp_progress
        in_window = np.isfinite(time_rel)
        y_final = np.where(in_window, y * ramp_mult, y_with_rest)
    else:
        y_final = y_with_rest
    return Funscript(x, y_final)


def make_volume_ramp(input_fs: Funscript, ramp_percent_per_hour: float = 15.0) -> Funscript:
    if len(input_fs.x) < 4:
        raise ValueError("Input funscript must have at least 4 actions to create volume ramp.")
    start_t = float(input_fs.x[0])
    second_t = start_t + 10.0
    peak_t = float(input_fs.x[-2])
    end_t = float(input_fs.x[-1])
    file_hours = (peak_t - start_t) / 3600.0
    total_inc = (ramp_percent_per_hour / 100.0) * file_hours
    start_val = max(0.0, 1.0 - total_inc)
    return Funscript(
        np.array([start_t, second_t, peak_t, end_t]),
        np.array([0.0, start_val, 1.0, 0.0]),
    )


# ---- 1D -> 2D (alpha/beta) "circular" algorithm --------------------------------


def convert_funscript_radial(fs: Funscript, speed_fs: Optional[Funscript] = None,
                             points_per_second: int = 25,
                             min_distance_from_center: float = 0.1,
                             speed_threshold_percent: float = 50.0
                             ) -> Tuple[Funscript, Funscript]:
    at = fs.x
    pos = fs.y
    if len(at) < 2:
        return Funscript([], []), Funscript([], [])

    if speed_fs is not None:
        mask = (speed_fs.x >= at[0] - 1e-9) & (speed_fs.x <= at[-1] + 1e-9)
        t_global = speed_fs.x[mask]
    else:
        step = 1.0 / points_per_second
        t_global = np.arange(at[0], at[-1], step)

    if len(t_global) == 0:
        return Funscript(at.copy(), pos.copy()), Funscript(at.copy(), pos.copy())

    seg_idx = np.searchsorted(at, t_global, side="right") - 1
    seg_idx = np.clip(seg_idx, 0, len(at) - 2)

    seg_start_t = at[seg_idx]
    seg_end_t = at[seg_idx + 1]
    seg_start_p = pos[seg_idx]
    seg_end_p = pos[seg_idx + 1]
    seg_dur = seg_end_t - seg_start_t
    progress = np.where(seg_dur > 0, (t_global - seg_start_t) / seg_dur, 0.0)
    progress = np.clip(progress, 0.0, 1.0)
    current_positions = seg_start_p + progress * (seg_end_p - seg_start_p)

    n_segs = len(at) - 1
    if speed_fs is not None:
        seg_start_speeds = np.interp(at[:n_segs], speed_fs.x, speed_fs.y) * 100
    else:
        seg_durations_all = at[1:] - at[:n_segs]
        pos_changes_all = np.abs(pos[1:] - pos[:n_segs])
        seg_start_speeds = np.where(
            seg_durations_all > 0,
            np.minimum(pos_changes_all / seg_durations_all / 2.0, 1.0) * 100,
            0.0,
        )

    speed_thresh = max(float(speed_threshold_percent), 1e-10)
    radius_scale = np.where(
        seg_start_speeds >= speed_threshold_percent,
        1.0,
        min_distance_from_center
        + (1.0 - min_distance_from_center) * seg_start_speeds / speed_thresh,
    )
    target_radius = 0.5 * radius_scale[seg_idx]

    angles = (1.0 - current_positions) * np.pi
    x_out = 0.5 + target_radius * np.cos(angles)
    y_out = 0.5 + target_radius * np.sin(angles)
    return Funscript(t_global, x_out), Funscript(t_global, y_out)


# ---- Linear response curves (motion-axis e1-e4) -------------------------------


def apply_response_curve_to_funscript(fs: Funscript,
                                      control_points: List[Tuple[float, float]]
                                      ) -> Funscript:
    cps = sorted(((float(a), float(b)) for a, b in control_points), key=lambda p: p[0])
    xs = np.array([p[0] for p in cps])
    ys = np.array([p[1] for p in cps])
    in_clamped = np.clip(fs.y, 0.0, 1.0)
    new_y = np.interp(in_clamped, xs, ys)
    return Funscript(fs.x.copy(), np.clip(new_y, 0.0, 1.0), fs.metadata)


# Default response curves copied verbatim from upstream config.py
RESPONSE_CURVES = {
    "e1": [(0.0, 0.0), (1.0, 1.0)],                         # Linear
    "e2": [(0.0, 0.0), (0.5, 0.2), (1.0, 1.0)],             # Ease In
    "e3": [(0.0, 0.0), (0.5, 0.8), (1.0, 1.0)],             # Ease Out
    "e4": [(0.0, 0.0), (0.25, 0.3), (0.5, 1.0),
           (0.75, 0.3), (1.0, 0.0)],                        # Bell
}


# ---------------------------------------------------------------------------
# Event application (subset of FunscriptEditor)
# ---------------------------------------------------------------------------


# normalization config (verbatim from config.event_definitions.yml)
NORMALIZATION = {
    "pulse_frequency": 120.0,
    "pulse_width": 100.0,
    "frequency": 1200.0,
    "volume": 1.0,
}


def _norm_value(axis: str, value: float) -> float:
    """Normalize raw axis values to internal 0-1 representation.

    Mirrors `FunscriptEditor._normalize_value`.  Note that — unlike a plain
    division — the upstream behaviour treats values already inside [0, 1] as
    pre-normalized when the axis max is > 1.0.
    """
    for key, max_val in NORMALIZATION.items():
        if key in axis:
            if max_val == 1.0:
                return value
            if max_val > 1.0 and 0.0 <= value <= 1.0:
                return value
            return value / max_val
    return value


def _indices_for_range(fs: Funscript, start_ms: int, duration_ms: int) -> np.ndarray:
    if duration_ms == 0:
        idx = np.searchsorted(fs.x, start_ms / 1000.0, side="left")
        if idx < len(fs.x):
            return np.array([idx])
        return np.array([], dtype=int)
    start_s = start_ms / 1000.0
    end_s = (start_ms + duration_ms) / 1000.0
    return np.where((fs.x >= start_s) & (fs.x < end_s))[0]


def apply_linear_change(fs: Funscript, axis: str, start_ms: int, duration_ms: int,
                        start_value: float, end_value: float,
                        ramp_in_ms: int = 0, ramp_out_ms: int = 0,
                        mode: str = "additive") -> None:
    """In-place linear change — mirrors upstream
    `FunscriptEditor._apply_linear_change_single`.
    """
    indices = _indices_for_range(fs, start_ms, duration_ms)
    if indices.size == 0:
        return
    nval_start = _norm_value(axis, start_value)
    nval_end = _norm_value(axis, end_value)
    duration_s = duration_ms / 1000.0
    ramp_in_s = ramp_in_ms / 1000.0
    ramp_out_s = ramp_out_ms / 1000.0
    if indices.size > 1:
        linear_values = np.linspace(nval_start, nval_end, indices.size)
    else:
        linear_values = np.full(indices.size, nval_start)

    rel_t = fs.x[indices] - start_ms / 1000.0

    if mode == "additive":
        env = np.ones_like(linear_values)
        if ramp_in_s > 0:
            ri = np.where(rel_t < min(ramp_in_s, duration_s))[0]
            if ri.size > 0:
                env[ri] *= np.linspace(0, 1, ri.size)
        if ramp_out_s > 0:
            ramp_out_start = duration_s - min(ramp_out_s, duration_s)
            ro = np.where(rel_t > ramp_out_start)[0]
            if ro.size > 0:
                env[ro] *= np.linspace(1, 0, ro.size)
        fs.y[indices] = fs.y[indices] + linear_values * env
    elif mode == "overwrite":
        original = fs.y[indices].copy()
        fs.y[indices] = linear_values
        if ramp_in_s > 0:
            ri = np.where(rel_t < min(ramp_in_s, duration_s))[0]
            if ri.size > 0:
                blend = np.linspace(0, 1, ri.size)
                fs.y[indices[ri]] = (1 - blend) * original[ri] + blend * linear_values[ri]
        if ramp_out_s > 0:
            ramp_out_start = duration_s - min(ramp_out_s, duration_s)
            ro = np.where(rel_t > ramp_out_start)[0]
            if ro.size > 0:
                blend = np.linspace(1, 0, ro.size)
                fs.y[indices[ro]] = blend * linear_values[ro] + (1 - blend) * original[ro]
    fs.y[indices] = np.clip(fs.y[indices], 0.0, 1.0)


def apply_modulation(fs: Funscript, axis: str, start_ms: int, duration_ms: int,
                     waveform: str, frequency: float, amplitude: float,
                     max_level_offset: float = 0.0, phase: float = 0.0,
                     ramp_in_ms: int = 0, ramp_out_ms: int = 0,
                     mode: str = "additive", duty_cycle: float = 0.5) -> None:
    indices = _indices_for_range(fs, start_ms, duration_ms)
    if indices.size == 0:
        return
    duration_s = duration_ms / 1000.0
    start_s = start_ms / 1000.0
    ramp_in_s = ramp_in_ms / 1000.0
    ramp_out_s = ramp_out_ms / 1000.0
    rel_t = fs.x[indices] - start_s
    phase_rad = np.deg2rad(phase)
    phase_norm = (phase / 360.0) % 1.0
    wave_phase = (frequency * rel_t + phase_norm) % 1.0
    wf = waveform.lower()
    if wf == "sin":
        base = np.sin(2 * np.pi * frequency * rel_t + phase_rad)
    elif wf == "square":
        dc = float(np.clip(duty_cycle, 0.01, 0.99))
        base = np.where(wave_phase < dc, 1.0, -1.0)
    elif wf == "triangle":
        base = np.where(wave_phase < 0.5, -1.0 + 4.0 * wave_phase, 3.0 - 4.0 * wave_phase)
    elif wf == "sawtooth":
        base = -1.0 + 2.0 * wave_phase
    else:
        return
    n_amp = _norm_value(axis, amplitude)
    n_off = _norm_value(axis, max_level_offset)
    gen = n_off + n_amp * base
    if mode == "additive":
        env = np.ones_like(gen)
        if ramp_in_s > 0 and duration_s > 0:
            ri = np.where(rel_t < min(ramp_in_s, duration_s))[0]
            if ri.size > 0:
                env[ri] *= np.linspace(0, 1, ri.size)
        if ramp_out_s > 0 and duration_s > 0:
            ro_start = duration_s - min(ramp_out_s, duration_s)
            ro = np.where(rel_t > ro_start)[0]
            if ro.size > 0:
                env[ro] *= np.linspace(1, 0, ro.size)
        fs.y[indices] = fs.y[indices] + gen * env
    elif mode == "overwrite":
        original = fs.y[indices].copy()
        fs.y[indices] = gen
        if ramp_in_s > 0 and duration_s > 0:
            ri = np.where(rel_t < min(ramp_in_s, duration_s))[0]
            if ri.size > 0:
                blend = np.linspace(0, 1, ri.size)
                fs.y[indices[ri]] = (1 - blend) * original[ri] + blend * gen[ri]
        if ramp_out_s > 0 and duration_s > 0:
            ro_start = duration_s - min(ramp_out_s, duration_s)
            ro = np.where(rel_t > ro_start)[0]
            if ro.size > 0:
                blend = np.linspace(1, 0, ro.size)
                fs.y[indices[ro]] = blend * gen[ro] + (1 - blend) * original[ro]
    fs.y[indices] = np.clip(fs.y[indices], 0.0, 1.0)


# ---------------------------------------------------------------------------
# Event definitions
# ---------------------------------------------------------------------------


def _load_event_definitions() -> dict:
    """Load upstream config.event_definitions.yml if available; otherwise fall
    back to a minimal hard-coded set covering at least fast/edge/cum/ruin/stay
    that all senorgif scripts use.
    """
    candidates = [
        Path(__file__).resolve().parent.parent / "references" / "funscript-tools" / "config.event_definitions.yml",
    ]
    for c in candidates:
        if c.exists():
            try:
                with open(c, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict) and "definitions" in data:
                    return data["definitions"]
            except Exception:
                pass
    # ASSUMPTION-2: minimal in-line fallback so the script remains usable even
    # if the upstream definitions file goes missing.  Senorgif scripts only
    # use fast / edge / cum / ruin / stay in practice.
    return {
        "fast": {
            "default_params": {
                "duration_ms": 15000, "stroke_freq": 2, "stroke_intensity": 0.5,
                "stroke_offset": 0, "volume_boost": 0.03, "ramp_up_ms": 2500,
            },
            "steps": [
                {"operation": "apply_linear_change", "axis": "volume,volume-prostate",
                 "params": {"start_value": "$volume_boost", "end_value": "$volume_boost",
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "mode": "additive"}},
                {"operation": "apply_linear_change", "axis": "pulse_frequency",
                 "params": {"start_value": 10, "end_value": 10,
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "mode": "additive"}},
                {"operation": "apply_modulation", "axis": "alpha",
                 "params": {"waveform": "sin", "frequency": "$stroke_freq",
                            "amplitude": "$stroke_intensity",
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "max_level_offset": "$stroke_offset", "mode": "additive"}},
                {"operation": "apply_linear_change", "axis": "pulse_width",
                 "params": {"start_value": -20, "end_value": -30,
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "mode": "additive"}},
            ],
        },
        "edge": {
            "default_params": {"duration_ms": 15000, "buzz_freq": 10,
                               "buzz_intensity": 0.07, "volume_boost": 0.15,
                               "ramp_up_ms": 500},
            "steps": [
                {"operation": "apply_linear_change", "axis": "pulse_frequency",
                 "params": {"start_value": 40, "end_value": 50,
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "mode": "additive"}},
                {"operation": "apply_modulation", "axis": "volume,volume-prostate",
                 "params": {"waveform": "sin", "frequency": "$buzz_freq",
                            "amplitude": "$buzz_intensity",
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "max_level_offset": "$volume_boost", "mode": "additive"}},
                {"operation": "apply_linear_change", "axis": "pulse_width",
                 "params": {"start_value": -40, "end_value": -30,
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "mode": "additive"}},
            ],
        },
        "cum": {
            "default_params": {"duration_ms": 15000, "buzz_freq": 1.5,
                               "buzz_intensity": 0.1, "volume_boost": 0.2,
                               "ramp_up_ms": 250},
            "steps": [
                {"operation": "apply_linear_change", "axis": "pulse_frequency",
                 "params": {"start_value": 90, "end_value": 80,
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "mode": "additive"}},
                {"operation": "apply_modulation", "axis": "volume,volume-prostate",
                 "params": {"waveform": "sin", "frequency": "$buzz_freq",
                            "amplitude": "$buzz_intensity",
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "max_level_offset": "$volume_boost", "mode": "additive"}},
                {"operation": "apply_linear_change", "axis": "pulse_width",
                 "params": {"start_value": -50, "end_value": 50,
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "mode": "additive"}},
            ],
        },
        "ruin": {
            "default_params": {"duration_ms": 30000, "ramp_in_ms": 10000},
            "steps": [
                {"operation": "apply_linear_change", "axis": "volume",
                 "params": {"start_value": 0, "end_value": 0,
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_in_ms",
                            "ramp_out_ms": 500, "mode": "overwrite"}},
            ],
        },
        "stay": {
            "default_params": {"duration_ms": 15000, "buzz_freq": 15,
                               "buzz_intensity": 0.05, "volume_boost": 0.1,
                               "ramp_up_ms": 250},
            "steps": [
                {"operation": "apply_linear_change", "axis": "pulse_frequency",
                 "params": {"start_value": 80, "end_value": 80,
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "mode": "additive"}},
                {"operation": "apply_modulation", "axis": "volume,volume-prostate",
                 "params": {"waveform": "sin", "frequency": "$buzz_freq",
                            "amplitude": "$buzz_intensity",
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "max_level_offset": "$volume_boost", "mode": "additive"}},
                {"operation": "apply_linear_change", "axis": "pulse_width",
                 "params": {"start_value": -80, "end_value": -90,
                            "duration_ms": "$duration_ms", "ramp_in_ms": "$ramp_up_ms",
                            "mode": "additive"}},
            ],
        },
    }


def _resolve_token(value, params: dict):
    if isinstance(value, str) and value.startswith("$"):
        token = value[1:]
        if token in params:
            return params[token]
    return value


def apply_events(fs_by_axis: Dict[str, Funscript], events_path: Path,
                 definitions: dict) -> Tuple[int, int]:
    """Apply every event in `events_path` to the funscript bundle in-place.

    Returns (events_applied, events_skipped).
    """
    with open(events_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    events = data.get("events") or []
    applied = 0
    skipped = 0
    for ev in events:
        name = ev.get("name")
        when = ev.get("time")
        if name is None or when is None:
            skipped += 1
            continue
        when_ms = int(when)
        defn = definitions.get(name)
        if defn is None:
            print(f"  WARN: unknown event '{name}' at t={when_ms}ms — skipping")
            skipped += 1
            continue
        merged = dict(defn.get("default_params", {}))
        merged.update(ev.get("params", {}) or {})

        for step in defn.get("steps", []):
            op = step.get("operation")
            axes_str = step.get("axis", "")
            raw_params = step.get("params", {}) or {}
            start_offset = _resolve_token(step.get("start_offset", 0), merged)
            try:
                start_offset_ms = int(start_offset)
            except (TypeError, ValueError):
                start_offset_ms = 0
            event_start_ms = when_ms + start_offset_ms

            resolved = {k: _resolve_token(v, merged) for k, v in raw_params.items()}

            for axis_name in [a.strip() for a in axes_str.split(",") if a.strip()]:
                if axis_name not in fs_by_axis:
                    continue
                fs = fs_by_axis[axis_name]
                try:
                    if op == "apply_linear_change":
                        apply_linear_change(
                            fs, axis_name,
                            event_start_ms,
                            int(resolved.get("duration_ms", 0)),
                            float(resolved.get("start_value", 0.0)),
                            float(resolved.get("end_value", resolved.get("start_value", 0.0))),
                            int(resolved.get("ramp_in_ms", 0)),
                            int(resolved.get("ramp_out_ms", 0)),
                            str(resolved.get("mode", "additive")),
                        )
                    elif op == "apply_modulation":
                        apply_modulation(
                            fs, axis_name,
                            event_start_ms,
                            int(resolved.get("duration_ms", 0)),
                            str(resolved.get("waveform", "sin")),
                            float(resolved.get("frequency", 1.0)),
                            float(resolved.get("amplitude", 0.0)),
                            float(resolved.get("max_level_offset", 0.0)),
                            float(resolved.get("phase", 0.0)),
                            int(resolved.get("ramp_in_ms", 0)),
                            int(resolved.get("ramp_out_ms", 0)),
                            str(resolved.get("mode", "additive")),
                            float(resolved.get("duty_cycle", 0.5)),
                        )
                except Exception as exc:
                    print(f"  WARN: failed to apply step for '{name}' axis '{axis_name}': {exc}")
        applied += 1
    return applied, skipped


# ---------------------------------------------------------------------------
# Per-session pipeline
# ---------------------------------------------------------------------------


# Default config (subset used by this converter). Mirrors upstream config.py.
CONFIG = {
    "general": {
        "rest_level": 0.4,
        "ramp_up_duration_after_rest": 1.0,
        "speed_window_size": 5,
        "accel_window_size": 3,
    },
    "speed": {"interpolation_interval": 0.1},
    "alpha_beta_generation": {
        "points_per_second": 10,           # = 1 / interpolation_interval (default)
        "min_distance_from_center": 0.1,
        "speed_threshold_percent": 50,
    },
    "frequency": {
        "pulse_freq_min": 0.40,
        "pulse_freq_max": 0.95,
        "frequency_ramp_combine_ratio": 2,
        "pulse_frequency_combine_ratio": 3,
    },
    "volume": {
        "volume_ramp_combine_ratio": 20.0,
        "prostate_volume_multiplier": 1.5,
        "prostate_rest_level": 0.7,
        "ramp_percent_per_hour": 15,
    },
    "pulse": {
        "pulse_width_min": 0.1,
        "pulse_width_max": 0.45,
        "pulse_width_combine_ratio": 3,
        "pulse_rise_min": 0.0,
        "pulse_rise_max": 0.80,
        "pulse_rise_combine_ratio": 2,
    },
}


def _find_session_files(session_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """Find the base funscript and matching .events.yml inside `session_dir`.

    Recursively descends one level (Shibby/The-Box style nesting) and prefers
    a file pair where the funscript name is the events.yml name minus the
    `.events.yml` suffix.  Generated axis files (`.alpha.`, `.beta.`, etc.)
    are excluded.
    """
    for root, _dirs, files in os.walk(session_dir):
        events = [Path(root) / f for f in files if f.endswith((".events.yml", ".events.yaml"))]
        if not events:
            continue
        for ev in events:
            base = ev.name
            for suf in (".events.yml", ".events.yaml"):
                if base.endswith(suf):
                    base = base[: -len(suf)]
                    break
            candidate = Path(root) / f"{base}.funscript"
            if candidate.exists():
                return candidate, ev
        # fallback: any non-axis funscript in the same folder
        funs = [Path(root) / f for f in files if f.endswith(".funscript")
                and "." in f[: -len(".funscript")] is False]
        # the heuristic above is unreliable; do a stricter one:
        funs = []
        for f in files:
            if not f.endswith(".funscript"):
                continue
            stem = f[: -len(".funscript")]
            # exclude generated axis-suffixed files
            if "." in stem:
                last = stem.rsplit(".", 1)[1]
                if last in {"alpha", "beta", "volume", "pulse_frequency",
                            "pulse_width", "pulse_rise_time", "frequency",
                            "alpha-prostate", "beta-prostate", "volume-prostate",
                            "speed", "ramp", "accel", "e1", "e2", "e3", "e4"}:
                    continue
            funs.append(Path(root) / f)
        if funs and events:
            return funs[0], events[0]
    return None, None


def convert_session(session_dir: Path, output_dir: Path) -> dict:
    """Convert a single session.  Returns a small report dict."""
    base_funscript, events_file = _find_session_files(session_dir)
    if base_funscript is None or events_file is None:
        return {"session": session_dir.name, "error": "no funscript+events pair found",
                "axes": {}, "duration_s": 0.0}

    print(f"Session: {session_dir.name}")
    print(f"  base funscript: {base_funscript.name}")
    print(f"  events file:    {events_file.name}")

    main_fs = Funscript.from_file(base_funscript)
    duration_s = float(main_fs.x[-1]) if len(main_fs.x) else 0.0
    print(f"  base actions:   {len(main_fs.x)}    duration: {duration_s:.1f}s")

    # ---- Phase 1: derived primitives -------------------------------------------
    speed_fs = convert_to_speed(main_fs,
                                CONFIG["general"]["speed_window_size"],
                                CONFIG["speed"]["interpolation_interval"])
    speed_inverted = invert_funscript(speed_fs)

    alpha_fs, beta_fs = convert_funscript_radial(
        main_fs, speed_fs,
        points_per_second=CONFIG["alpha_beta_generation"]["points_per_second"],
        min_distance_from_center=CONFIG["alpha_beta_generation"]["min_distance_from_center"],
        speed_threshold_percent=CONFIG["alpha_beta_generation"]["speed_threshold_percent"],
    )

    ramp_fs = make_volume_ramp(main_fs, CONFIG["volume"]["ramp_percent_per_hour"])
    ramp_inverted = invert_funscript(ramp_fs)

    # ---- Phase 2: composite outputs --------------------------------------------
    pulse_freq_combined = combine_funscripts(
        speed_fs, alpha_fs, CONFIG["frequency"]["pulse_frequency_combine_ratio"]
    )
    pulse_frequency = map_funscript(
        pulse_freq_combined,
        CONFIG["frequency"]["pulse_freq_min"],
        CONFIG["frequency"]["pulse_freq_max"],
    )

    frequency = combine_funscripts(
        ramp_fs, speed_fs, CONFIG["frequency"]["frequency_ramp_combine_ratio"]
    )

    volume = combine_funscripts(
        ramp_fs, speed_fs,
        CONFIG["volume"]["volume_ramp_combine_ratio"],
        CONFIG["general"]["rest_level"],
        CONFIG["general"]["ramp_up_duration_after_rest"],
    )
    volume = normalize_funscript(volume)

    main_inverted = invert_funscript(main_fs)
    # ASSUMPTION-1: pulse_width built from limit(main_inverted) × speed combine,
    # matching the simplified path in upstream processor.py (no beta mirror).
    pulse_width_main = limit_funscript(
        main_inverted,
        CONFIG["pulse"]["pulse_width_min"],
        CONFIG["pulse"]["pulse_width_max"],
    )
    pulse_width = combine_funscripts(
        speed_fs, pulse_width_main,
        CONFIG["pulse"]["pulse_width_combine_ratio"],
    )

    pulse_rise_time_combined = combine_funscripts(
        ramp_inverted, speed_inverted,
        CONFIG["pulse"]["pulse_rise_combine_ratio"],
    )
    pulse_rise_time = map_funscript(
        pulse_rise_time_combined,
        CONFIG["pulse"]["pulse_rise_min"],
        CONFIG["pulse"]["pulse_rise_max"],
    )

    # ---- Phase 3: prostate variants -------------------------------------------
    alpha_prostate = invert_funscript(main_fs)  # upstream uses inverted main as alpha-prostate
    beta_prostate = invert_funscript(beta_fs)
    volume_prostate = combine_funscripts(
        ramp_fs, speed_fs,
        CONFIG["volume"]["volume_ramp_combine_ratio"]
        * CONFIG["volume"]["prostate_volume_multiplier"],
        CONFIG["volume"]["prostate_rest_level"],
        CONFIG["general"]["ramp_up_duration_after_rest"],
    )
    volume_prostate = normalize_funscript(volume_prostate)

    # ---- Phase 4: motion-axis e1-e4 --------------------------------------------
    e_axes = {
        f"e{i}": apply_response_curve_to_funscript(main_fs, RESPONSE_CURVES[f"e{i}"])
        for i in (1, 2, 3, 4)
    }

    fs_by_axis: Dict[str, Funscript] = {
        "alpha": alpha_fs,
        "beta": beta_fs,
        "volume": volume,
        "pulse_frequency": pulse_frequency,
        "pulse_width": pulse_width,
        "pulse_rise_time": pulse_rise_time,
        "frequency": frequency,
        "alpha-prostate": alpha_prostate,
        "beta-prostate": beta_prostate,
        "volume-prostate": volume_prostate,
        **e_axes,
    }

    # ---- Phase 5: events overlay -----------------------------------------------
    definitions = _load_event_definitions()
    applied, skipped = apply_events(fs_by_axis, events_file, definitions)
    print(f"  events applied: {applied}    skipped: {skipped}")

    # ---- Phase 6: write -------------------------------------------------------
    base_stem = base_funscript.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    axes_report: Dict[str, int] = {}
    for axis_name, fs in fs_by_axis.items():
        out_path = output_dir / f"{base_stem}.{axis_name}.funscript"
        fs.metadata = {
            "creator": "Restim Web Extension - restim_event_converter",
            "title": axis_name,
            "metadata": {
                "axis": axis_name,
                "source_session": session_dir.name,
                "source_funscript": base_funscript.name,
                "source_events": events_file.name,
            },
        }
        fs.save_to_path(out_path)
        axes_report[axis_name] = int(len(fs.x))

    return {
        "session": session_dir.name,
        "error": None,
        "axes": axes_report,
        "duration_s": duration_s,
        "events_applied": applied,
        "events_skipped": skipped,
        "output_dir": str(output_dir),
        "base_funscript": base_funscript.name,
    }


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    """Make a safe directory name from a session folder name."""
    safe = []
    for ch in name:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        elif ch == " ":
            safe.append("_")
        else:
            safe.append("_")
    out = "".join(safe).strip("._")
    return out or "session"


def main():
    parser = argparse.ArgumentParser(
        description=("Convert Senorgif-style funscript+events sessions into the "
                     "full 7-axis Restim funscript bundle."),
    )
    parser.add_argument("--input", help="Path to a single session directory")
    parser.add_argument("--output", help="Path to output directory for a single session")
    parser.add_argument("--all", action="store_true",
                        help="Bulk convert all sessions in references/senorgif-restim-events")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    senorgif_root = repo_root / "references" / "senorgif-restim-events"
    default_output_root = repo_root / "data" / "training_funscripts" / "senorgif"

    sessions: List[Tuple[Path, Path]] = []  # (session_dir, output_dir)

    if args.all:
        if not senorgif_root.exists():
            print(f"ERROR: {senorgif_root} not found", file=sys.stderr)
            sys.exit(1)
        for entry in sorted(senorgif_root.iterdir()):
            if not entry.is_dir():
                continue
            # skip dotfile/git/cache dirs
            if entry.name.startswith(".") or entry.name in {"__pycache__", "node_modules"}:
                continue
            sessions.append((entry, default_output_root / _slugify(entry.name)))
    else:
        if not args.input or not args.output:
            parser.error("Provide --input + --output, or --all")
        sessions.append((Path(args.input), Path(args.output)))

    reports = []
    for session_dir, out_dir in sessions:
        try:
            report = convert_session(session_dir, out_dir)
        except Exception as exc:
            traceback.print_exc()
            report = {"session": session_dir.name, "error": str(exc),
                      "axes": {}, "duration_s": 0.0}
        reports.append(report)
        print()

    # ---------- final summary ----------
    print("=" * 70)
    print(" CONVERSION REPORT")
    print("=" * 70)
    total_axes = 0
    total_files = 0
    ok_sessions = 0
    failed_sessions = 0
    for r in reports:
        if r.get("error"):
            failed_sessions += 1
            print(f"  [FAIL] {r['session']}: {r['error']}")
            continue
        ok_sessions += 1
        n_axes = len(r["axes"])
        total_axes += n_axes
        total_files += n_axes
        avg_actions = int(np.mean(list(r["axes"].values()))) if r["axes"] else 0
        print(f"  [OK]   {r['session']:<40s}  "
              f"{n_axes:2d} axes  duration={r['duration_s']:7.1f}s  "
              f"avg_actions/axis={avg_actions:6d}  "
              f"events={r.get('events_applied',0)}/{r.get('events_applied',0)+r.get('events_skipped',0)}")
        # per-axis action count, compact
        for ax, count in r["axes"].items():
            print(f"           - {ax:<18s} {count:6d} actions")
    print("-" * 70)
    print(f"  Sessions OK:     {ok_sessions}")
    print(f"  Sessions FAIL:   {failed_sessions}")
    print(f"  Files generated: {total_files}")
    print("=" * 70)


if __name__ == "__main__":
    main()
